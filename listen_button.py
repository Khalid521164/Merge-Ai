"""Per-answer Listen uses the same asynchronous Kokoro backend as Live Voice."""
import streamlit as st
from kokoro_tts import SpeechResult, start_audio
from voice_config import VoiceConfig
from voice_text import check_final_answer, prepare_speech_text, browser_chunks, UnsafeSpeechText

HTML = '<button type="button" aria-label="Listen to this answer">🔊 Listen</button><span role="status"></span>'
CSS = 'button{background:transparent;border:1px solid #d9e8dd;border-radius:8px;padding:5px 10px;color:#193e35;cursor:pointer}span{font:12px system-ui;color:#66766f;margin-left:8px}'
JS = r'''
export default function({parentElement:root,data,setTriggerValue}) {
  const button=root.querySelector('button'), status=root.querySelector('span');
  const state=root.__listenState||(root.__listenState={seen:'',audio:null,busy:false,token:0});
  const owner='listen-'+data.key;
  const stop=()=>{state.token++;if(state.audio)state.audio.pause();state.audio=null;
    if(window.__mergeAudioOwner===owner){if(window.speechSynthesis)window.speechSynthesis.cancel();
      window.__mergeStopAudio=null;window.__mergeAudioOwner=null;}
    state.busy=false;button.textContent='🔊 Listen';};
  const claim=()=>{if(window.__mergeStopAudio&&window.__mergeAudioOwner!==owner)window.__mergeStopAudio();
    window.__mergeStopAudio=stop;window.__mergeAudioOwner=owner;};
  const browserSpeech=()=>{
    if(!data.allow_fallback){status.textContent=data.message||'Speech is unavailable.';return;}
    if(!window.speechSynthesis){status.textContent='Speech playback is unavailable in this browser.';return;}
    const token=++state.token;const chunks=data.chunks||[];
    let index=0;state.busy=true;button.textContent='⏹ Stop';status.textContent='Browser voice';
    const next=()=>{if(token!==state.token)return;if(index>=chunks.length){stop();return;}
      const utter=new SpeechSynthesisUtterance(chunks[index++]);utter.lang='en-US';utter.rate=data.speed;
      utter.onend=next;utter.onerror=()=>{if(token!==state.token)return;stop();status.textContent='Click Listen to retry playback.';};
      window.speechSynthesis.speak(utter);};next();
  };
  const play=()=>{stop();claim();if(!data.audio_b64){browserSpeech();return;}
    const token=state.token, player=new Audio('data:audio/wav;base64,'+data.audio_b64);state.audio=player;
    state.busy=true;button.textContent='⏹ Stop';status.textContent='Kokoro · '+data.voice;
    player.onended=()=>{if(token!==state.token)return;stop();status.textContent='';};
    let failed=false;
    player.onerror=()=>{if(token!==state.token||failed)return;failed=true;stop();claim();browserSpeech();};
    player.play().catch(e=>{if(token!==state.token)return;
      if(e.name==='NotAllowedError'){stop();status.textContent='Click Listen to play the answer.';}
      else player.onerror();});
  };
  button.onclick=()=>{if(state.busy){stop();return;}if(data.pending)return;
    if(data.reply_id){play();return;}
    status.textContent='Preparing voice…';setTriggerValue('play_request',Date.now()+'-'+Math.random());};
  if(data.pending)status.textContent='Preparing voice…';
  if(data.reply_id&&data.reply_id!==state.seen){state.seen=data.reply_id;play();}
  return ()=>{stop();};
}
'''
_component = st.components.v2.component("merge_ai_listen", html=HTML, css=CSS, js=JS)


def listen_button(text: str, key: str, config: VoiceConfig):
    cache = st.session_state.get("ma_listen_job") or {}

    @st.fragment(run_every=0.5 if cache.get("key") == key and cache.get("future") else None)
    def render():
        current = st.session_state.get("ma_listen_job") or {}
        entry = current if current.get("key") == key else {}
        future = entry.get("future")
        if future and future.done():
            entry["result"] = future.result()
            entry["future"] = None
            st.rerun()
        speech = entry.get("result") or SpeechResult()
        chunks = browser_chunks(prepare_speech_text(text))
        allow_fallback = config.browser_fallback and speech.allow_fallback
        try:
            check_final_answer(text)
        except UnsafeSpeechText as exc:
            chunks, allow_fallback = [], False
            speech = SpeechResult(status="blocked", message=str(exc), allow_fallback=False)
        result = _component(
            key="listen_" + key,
            data={"key": key, "chunks": chunks, "audio_b64": speech.audio_b64,
                  "reply_id": entry.get("request", "") if not future else "", "pending": bool(future),
                  "allow_fallback": allow_fallback, "message": speech.message,
                  "voice": config.name, "speed": config.speed},
            on_play_request_change=lambda: None,
        )
        request = getattr(result, "play_request", None)
        if request and request != entry.get("request"):
            st.session_state.ma_listen_job = {
                "key": key, "request": request, "future": start_audio(text, config=config),
            }
            st.rerun()
    render()
