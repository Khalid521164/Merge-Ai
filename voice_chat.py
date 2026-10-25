"""Browser-based voice interface for Merge AI (Streamlit components v2).

Speech recognition and speech synthesis run in the visitor's browser.
No audio recording is uploaded by this component, although the browser's speech
recognition provider may process speech remotely. Transcript is sent to Streamlit.
Requires a Streamlit version supporting st.components.v2.component.
"""
from __future__ import annotations

import streamlit as st

HTML = '''
<div class="mv">
  <div class="mv-title"><span class="mv-orb">✦</span><div><b>Merge AI Voice</b><small>Talk to Merge AI naturally</small></div></div>
  <div class="mv-controls"><button class="mv-start" type="button">🎙 Start talking</button><button class="mv-stop" type="button">■ Stop</button><label><input class="mv-auto" type="checkbox" checked> Hands-free</label></div>
  <div class="mv-status" aria-live="polite">Voice is off</div><div class="mv-heard"></div>
  <p class="mv-note">Uses your browser's speech recognition and voice. Allow microphone access when asked.</p>
</div>
'''
CSS = '''
.mv{box-sizing:border-box;background:#fff;border:1px solid #dfebe1;border-radius:17px;padding:14px;color:#193e35;font:14px system-ui,sans-serif}.mv-title{display:flex;gap:10px;align-items:center}.mv-title b{display:block;font-size:16px}.mv-title small{display:block;color:#708178;margin-top:2px}.mv-orb{display:grid;place-items:center;border-radius:12px;background:#f1f7f2;color:#326957;width:39px;height:39px;font-size:23px}.mv-controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:14px}.mv button{border-radius:10px;border:1px solid #b7d0c2;background:white;color:#193e35;padding:10px 13px;cursor:pointer;font-weight:650}.mv button.mv-start{background:#326957;color:#fff;border-color:#326957}.mv label{color:#536b5e;font-size:12px}.mv-status{color:#326957;font-size:13px;margin-top:12px}.mv-heard{color:#536b5e;font-size:12px;min-height:1.2em;margin-top:5px;overflow-wrap:anywhere}.mv-note{color:#708178;font-size:11px;margin:11px 0 0}
'''
JS = r'''
export default function(component) {
  const { parentElement: root, data, setTriggerValue } = component;
  const startButton = root.querySelector('.mv-start');
  const stopButton = root.querySelector('.mv-stop');
  const autoBox = root.querySelector('.mv-auto');
  const status = root.querySelector('.mv-status');
  const heard = root.querySelector('.mv-heard');
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const key = 'merge_ai_voice_session';
  const state = window[key] || (window[key] = {
    enabled:false, listening:false, awaiting:false, speaking:false,
    recognition:null, responseId:null, lang:'en-US', owner:null
  });
  state.owner = {status, heard, startButton, stopButton, autoBox, setTriggerValue};
  state.lang = data.language || 'en-US';
  const ui = () => {
    const r = state.owner;
    r.status.textContent = !SpeechRecognition ? 'Live recognition is unavailable in this browser.' :
      state.speaking ? '🔊 Merge AI is speaking…' : state.awaiting ? '⏳ Merge AI is thinking…' :
      state.listening ? '🔴 Listening… speak now' : state.enabled ? 'Microphone paused' : 'Voice is off';
    r.startButton.disabled = !SpeechRecognition || state.listening || state.awaiting || state.speaking;
  };
  const stopListen = () => {
    if(state.recognition){try{state.recognition.abort();}catch(_){}}
    state.listening=false;
  };
  const listen = () => {
    if(!state.enabled || state.listening || state.awaiting || state.speaking || !SpeechRecognition) return;
    const rec = new SpeechRecognition();
    rec.lang=state.lang; rec.continuous=false; rec.interimResults=true; rec.maxAlternatives=1;
    state.recognition=rec;
    rec.onresult=(event) => {
      let finalText='', partial='';
      for(let i=event.resultIndex;i<event.results.length;i++){
        const value=event.results[i][0].transcript;
        if(event.results[i].isFinal) finalText+=value;
        else partial+=value;
      }
      state.owner.heard.textContent=finalText || partial;
      if(finalText.trim() && !state.awaiting){
        state.awaiting=true;
        state.listening=false;
        state.recognition=null;
        try{rec.abort();}catch(_){}
        state.owner.setTriggerValue('transcript',{text:finalText.trim().slice(0,1000),id:Date.now()+'-'+Math.random()});
        ui();
      }
    };
    rec.onerror=(event) => {
      state.listening=false;
      if(['not-allowed','service-not-allowed'].includes(event.error)) state.enabled=false;
      state.owner.status.textContent='Microphone: '+event.error;
    };
    rec.onend=()=>{state.listening=false;ui();};
    try{rec.start();state.listening=true;ui();}
    catch(e){state.listening=false;state.owner.status.textContent='Could not start microphone.';}
  };
  startButton.onclick=()=>{
    if(window.speechSynthesis){window.speechSynthesis.cancel();}
    state.enabled=true;state.awaiting=false;state.speaking=false;listen();
  };
  stopButton.onclick=()=>{
    state.enabled=false;state.awaiting=false;state.speaking=false;
    stopListen();if(window.speechSynthesis)window.speechSynthesis.cancel();ui();
  };
  autoBox.checked=state.auto !== false;
  autoBox.onchange=()=>{state.auto=autoBox.checked;};
  // A new response ID means Python finished another spoken question.
  if(data.reply_id && state.responseId!==data.reply_id){
    state.responseId=data.reply_id;
    state.awaiting=false;
    if(state.enabled && data.reply && window.speechSynthesis){
      stopListen();
      const msg=new SpeechSynthesisUtterance(String(data.reply).slice(0,4000));
      msg.lang=state.lang;msg.rate=1;
      state.speaking=true;
      msg.onend=()=>{state.speaking=false;ui();if(state.enabled && state.auto!==false)listen();};
      msg.onerror=()=>{state.speaking=false;ui();};
      window.speechSynthesis.cancel();window.speechSynthesis.speak(msg);
    } else if(state.enabled && state.auto!==false){listen();}
  }
  if(data.failed_id && state.failedId!==data.failed_id){
    state.failedId=data.failed_id;state.awaiting=false;
    state.owner.heard.textContent='Sorry, that question could not be answered. Try again.';
    ui();
  }
  ui();
  return ()=>{ /* Browser-level voice state intentionally survives Streamlit reruns. */ };
}
'''

voice_component = st.components.v2.component(
    "merge_ai_live_voice", html=HTML, css=CSS, js=JS
)


def voice_chat(*, reply: str = "", reply_id: str = "", failed_id: str = "", language: str = "en-US") -> str | None:
    """Render the voice controls and return a new spoken question, if any."""
    result = voice_component(
        key="merge_ai_voice_widget",
        data={"reply": reply, "reply_id": reply_id,
              "failed_id": failed_id, "language": language},
        on_transcript_change=lambda: None,
    )
    event = getattr(result, "transcript", None)
    if not isinstance(event, dict):
        return None
    transcript = event.get("text", "")
    event_id = event.get("id")
    if not isinstance(transcript, str) or not transcript.strip() or not event_id:
        return None
    if st.session_state.get("ma_last_voice_event") == event_id:
        return None
    st.session_state.ma_last_voice_event = event_id
    return transcript.strip()[:1000]
