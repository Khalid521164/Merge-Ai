"""Compact per-answer Listen control with the same Kokoro/browser fallback."""
import streamlit as st
from kokoro_tts import KokoroError, audio_base64, speech_text

HTML = '<button type="button" aria-label="Listen to this answer">🔊 Listen</button><span role="status"></span>'
CSS = 'button{background:transparent;border:1px solid #d9e8dd;border-radius:8px;padding:5px 10px;color:#193e35;cursor:pointer}span{font:12px system-ui;color:#66766f;margin-left:8px}'
JS = r'''
export default function({parentElement:root,data,setTriggerValue}) {
  const button=root.querySelector('button'), status=root.querySelector('span');
  const state=root.__listenState||(root.__listenState={seen:'',audio:null,busy:false,token:0});
  const stop=()=>{state.token++;if(state.audio)state.audio.pause();state.audio=null;
    if(window.speechSynthesis)window.speechSynthesis.cancel();state.busy=false;button.textContent='🔊 Listen';};
  const playBrowser=()=>{
    if(!window.speechSynthesis){status.textContent='Speech playback is unavailable in this browser.';return;}
    const token=++state.token;
    const chunks=String(data.text||'').match(/[^.!?]+(?:[.!?]+|$)/g)||[];
    let index=0;state.busy=true;button.textContent='⏹ Stop';
    status.textContent='Browser voice';
    const next=()=>{if(token!==state.token)return;if(index>=chunks.length){stop();return;}
      const utter=new SpeechSynthesisUtterance(chunks[index++]);utter.lang='en-US';utter.rate=1.03;
      utter.onend=next;utter.onerror=()=>{stop();status.textContent='Click Listen to retry playback.';};
      window.speechSynthesis.speak(utter);};next();
  };
  const play=()=>{stop();if(!data.audio_b64){playBrowser();return;}
    const player=new Audio('data:audio/wav;base64,'+data.audio_b64);state.audio=player;
    state.busy=true;button.textContent='⏹ Stop';status.textContent='Kokoro · Liam';
    player.onended=()=>{stop();status.textContent='';};
    player.onerror=()=>{stop();playBrowser();};
    player.play().catch(e=>{stop();status.textContent='Click Listen to play the answer.';});
  };
  button.onclick=()=>{if(state.busy){stop();return;}
    if(data.reply_id){play();return;}
    status.textContent='Preparing voice…';setTriggerValue('play_request',Date.now()+'-'+Math.random());};
  if(data.reply_id&&data.reply_id!==state.seen){state.seen=data.reply_id;play();}
  return ()=>{stop();};
}
'''

_component = st.components.v2.component("merge_ai_listen", html=HTML, css=CSS, js=JS)


def listen_button(text: str, key: str, **tts_options):
    cached = st.session_state.get("ma_listen_audio", {})
    entry = cached if cached.get("key") == key else {}
    result = _component(
        key="listen_" + key,
        data={"text": speech_text(text), "audio_b64": entry.get("audio", ""),
              "reply_id": entry.get("request", "")},
        on_play_request_change=lambda: None,
    )
    request = getattr(result, "play_request", None)
    if request and request != entry.get("request"):
        try:
            audio = audio_base64(text, **tts_options)
        except KokoroError:
            audio = ""
        # One private session entry bounds memory; never a process-global audio cache.
        st.session_state.ma_listen_audio = {"key": key, "request": request, "audio": audio}
        st.rerun()
