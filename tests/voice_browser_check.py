"""Opt-in Chromium test of the real Streamlit UI, with fake STT/provider calls.

Run: python tests/voice_browser_check.py --chromium /path/to/chromium --wav /path/to/kokoro-smoke.wav
The supplied WAV is decoded and played by Chromium. Microphone input and browser
speech are simulated; this does NOT verify physical speakers or a real mic.
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
INIT = r'''
window._played=[];window._speech=[];
const NativeAudio=window.Audio;
window.Audio=class extends NativeAudio {
  constructor(src){super(src);window._played.push(this);this.addEventListener('ended',()=>this._ended=true);}
  play(){if(window._blockAudio){window._blockAudio=false;return Promise.reject(new DOMException('blocked','NotAllowedError'));}return super.play();}
};
window.SpeechRecognition=class {
  start(){this.started=true;}abort(){this.started=false;}
};
window.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
Object.defineProperty(window,'speechSynthesis',{value:{paused:false,getVoices:()=>[],cancel(){},resume(){},
  speak(u){window._speech.push(u.text);setTimeout(()=>{if(u.onend)u.onend();},50);}}});
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chromium", required=True)
    parser.add_argument("--wav", required=True)
    args = parser.parse_args()
    wav = Path(args.wav).resolve()
    assert wav.is_file(), "Generate a real Kokoro WAV first."
    with tempfile.TemporaryDirectory() as folder:
        fixture = Path(folder, "fixture.py")
        fixture.write_text(
            "import sys,runpy,os,time\nfrom pathlib import Path\n"
            f"sys.path.insert(0,{str(ROOT)!r})\n"
            "import merge_ai,kokoro_tts\n"
            "merge_ai.default_providers=lambda: (merge_ai.Provider('groq','test','test'),)\n"
            "merge_ai.call_provider=lambda *args: 'Rain falls when cloud droplets grow heavy enough.'\n"
            "merge_ai.search_tavily=lambda *args: ('Rain evidence',[{'title':'Source','url':'https://example.org'}])\n"
            "def wav_fixture(text, **kwargs):\n"
            "    time.sleep(0.4)\n"
            "    if text.startswith('FAIL'): raise kokoro_tts.KokoroError('test failure')\n"
            f"    return Path({str(wav)!r}).read_bytes()\n"
            "kokoro_tts.synthesize=wav_fixture\n"
            "kokoro_tts.configured=lambda *args: True\n"
            f"runpy.run_path({str(ROOT / 'app.py')!r},run_name='__main__')\n"
        )
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
        env = dict(os.environ, TAVILY_API_KEY="fixture", BRAVE_SEARCH_API_KEY="", BRAVE_API_KEY="")
        log = open(Path(folder, "streamlit.log"), "w+")
        server = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", str(fixture), "--server.address", "127.0.0.1",
            "--browser.serverAddress", "127.0.0.1", "--server.port", str(port),
            "--server.headless", "true", "--browser.gatherUsageStats", "false",
        ], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=args.chromium, headless=True,
                                            args=["--no-sandbox", "--disable-gpu", "--autoplay-policy=no-user-gesture-required"])
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.add_init_script(INIT)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for _ in range(50):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2): break
                    except OSError: time.sleep(.1)
                page.goto(f"http://127.0.0.1:{port}")
                page.get_by_placeholder("Ask Merge AI anything…").wait_for(timeout=20000)
                page.get_by_placeholder("Ask Merge AI anything…").fill("Hi")
                page.get_by_placeholder("Ask Merge AI anything…").press("Enter")
                page.get_by_text("Hey! How can I help you today?", exact=True).wait_for()
                print("Browser instrumentation:", page.evaluate("({played:typeof window._played,frames:window.frames.length,voice:typeof window.__mergeVoice})"), errors, flush=True)
                page.get_by_role("button", name="Listen to this answer").click()
                page.wait_for_function("window._played.length>0 && window._played[0]._ended", timeout=20000)
                assert page.evaluate("window._played[0].duration>0 && window._played[0].error===null")
                print("PASS: chat Listen decoded and played the supplied real Kokoro WAV", flush=True)
                page.get_by_role("button", name="Live conversation").click()
                page.wait_for_function("window.__mergeVoice?.listening")

                def say(text):
                    page.evaluate("text=>{const rec=window.__mergeVoice.rec;const r=[{transcript:text}];r.isFinal=true;rec.onresult({resultIndex:0,results:[r]});}", text)

                before = page.evaluate("window._played.length")
                say("Hi")
                page.wait_for_function("n=>window._played.length>n && window.__mergeVoice.speaking", arg=before, timeout=20000)
                page.wait_for_function("window.__mergeVoice.listening && !window.__mergeVoice.awaiting", timeout=20000)
                assert page.evaluate("window.__mergeVoice.lastAi") == "Hey! How can I help you today?"
                assert page.evaluate("window._played.at(-1)._ended")
                print("PASS: Live Voice response, WAV playback, and microphone resumption", flush=True)

                before = page.evaluate("window._played.length")
                say("Hi")
                page.wait_for_function("n=>window._played.length>n && window.__mergeVoice.speaking", arg=before, timeout=20000)
                page.get_by_role("button", name="Mute or unmute microphone").click()
                assert page.evaluate("window._played.at(-1).paused && !window.__mergeVoice.speaking && window.__mergeVoice.muted")
                print("PASS: identical spoken questions are accepted, and mute stops audio", flush=True)
                page.get_by_role("button", name="Mute or unmute microphone").click()
                page.evaluate("window._blockAudio=true")
                say("Hello")
                page.get_by_text("Click 🔊 Play answer to hear Kokoro.", exact=True).wait_for(timeout=20000)
                page.get_by_role("button", name="Play answer").click()
                page.wait_for_function("window.__mergeVoice.speaking")
                page.wait_for_function("window.__mergeVoice.listening", timeout=20000)
                print("PASS: autoplay denial exposes manual playback, which succeeds", flush=True)

                page.get_by_label("Conversation language").select_option("bn-BD")
                before = page.evaluate("window._speech.length")
                say("Hi")
                page.wait_for_function("n=>window._speech.length>n", arg=before, timeout=20000)
                print("PASS: other-language browser speech fallback", flush=True)
                page.get_by_role("button", name="End voice conversation").click()
                assert page.evaluate("!window.__mergeVoice.open && !window.__mergeVoice.speaking")
                for width in (390, 768, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    assert page.evaluate("document.documentElement.scrollWidth<=window.innerWidth+1")
                assert not errors, errors
                print("PASS: phone, tablet and desktop widths; no browser JS errors", flush=True)
                browser.close()
        except Exception:
            log.flush();log.seek(0)
            print(log.read()[-4000:])
            raise
        finally:
            server.terminate();server.wait(timeout=10);log.close()


if __name__ == "__main__":
    main()
