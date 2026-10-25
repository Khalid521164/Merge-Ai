"""Merge AI browser live conversation modal, using Streamlit custom components v2.

Browser speech recognition / synthesis are device-dependent. Audio may be processed
by the browser vendor. Only transcripts are sent to Merge AI's Python backend.
"""
from __future__ import annotations

import streamlit as st

HTML = r'''
<div class="mv-mount">
  <button class="mv-open" type="button"><span>🎙</span> Live conversation</button>
  <div class="mv-overlay" hidden>
    <section class="mv-dialog" role="dialog" aria-modal="true" aria-label="Merge AI live voice conversation">
      <header class="mv-header"><div class="mv-logo">▥</div><div class="mv-heading"><b>Merge AI Voice</b><span>Talk naturally with Merge AI</span></div><button class="mv-close" aria-label="Close voice conversation" type="button">×</button></header>
      <div class="mv-language-row"><label for="mv-language">Conversation language</label><select id="mv-language" class="mv-language"></select></div>
      <div class="mv-status" aria-live="polite">Ready to talk</div>
      <div class="mv-orb-wrap"><div class="mv-orb"><div class="mv-orb-core"></div></div></div>
      <div class="mv-conversation">
        <div class="mv-caption">You</div><div class="mv-user-text">Your words will appear here…</div>
        <div class="mv-caption">Merge AI</div><div class="mv-ai-text">I’m ready to listen.</div>
      </div>
      <div class="mv-controls"><div class="mv-control"><button class="mv-mic" aria-label="Mute or unmute microphone" type="button">🎙</button><small class="mv-mic-label">Mute</small></div><div class="mv-control"><button class="mv-hang" aria-label="End voice conversation" type="button">☎</button><small>End</small></div></div>
      <p class="mv-note">Voice recognition and playback depend on your browser and installed voices. Audio may be processed by your browser’s speech provider.</p>
    </section>
  </div>
</div>
'''

CSS = r'''
.mv-mount{font-family:system-ui,-apple-system,'Segoe UI',sans-serif}
.mv-open{min-height:42px;cursor:pointer;border:1px solid #d9e8dd;border-radius:12px;background:#fff;color:#193e35;padding:9px 15px;font-weight:650;width:100%;font-size:13px}
.mv-open:hover{background:#f1f7f2;border-color:#90b5a1}
.mv-overlay[hidden]{display:none!important}
.mv-overlay{position:fixed;inset:0;z-index:2147482000;background:rgba(7,12,21,.78);backdrop-filter:blur(10px);display:grid;place-items:center;padding:12px;box-sizing:border-box}
.mv-dialog{box-sizing:border-box;width:min(460px,100%);height:min(780px,calc(100dvh - 24px));overflow:hidden;display:flex;flex-direction:column;border:1px solid #2b3549;background:radial-gradient(ellipse at 50% 40%,#0e1d3a 0%,#090e17 48%,#080b10 100%);color:#f7faff;border-radius:28px;box-shadow:0 22px 80px #0009;padding:18px 21px 14px}
.mv-header{display:flex;align-items:center;gap:12px}.mv-logo{font-size:26px;font-weight:850;background:linear-gradient(130deg,#21ceff,#435dff);color:transparent;background-clip:text}.mv-heading{display:flex;flex-direction:column;gap:2px;flex:1;min-width:0}.mv-heading b{font-size:20px;letter-spacing:-.6px}.mv-heading span{font-size:11px;color:#97a4ba}.mv-close{width:34px;height:34px;border:0;background:#1d2636;color:#dbe8ff;border-radius:10px;font-size:24px;cursor:pointer}
.mv-language-row{margin:20px 0 14px;display:flex;gap:9px;align-items:center;justify-content:space-between}.mv-language-row label{font-size:12px;color:#aebbd0}.mv-language{width:min(225px,62%);background:#141d2c;border:1px solid #354154;color:#e9f4ff;border-radius:9px;font-size:12px;padding:9px 7px;outline:none}
.mv-status{text-align:center;color:#adc7ef;font-size:14px;min-height:23px}
.mv-orb-wrap{flex:1;min-height:125px;display:grid;place-items:center;overflow:hidden}.mv-orb{width:clamp(125px,27vh,235px);aspect-ratio:1;border-radius:50%;background:conic-gradient(from 30deg,#31ffff,#0157fd,#031442,#0a28b2,#04d6ff,#0057ed,#31ffff);filter:drop-shadow(0 0 25px #087fff99);display:grid;place-items:center;animation:mv-pulse 4s ease-in-out infinite, mv-spin 14s linear infinite;box-shadow:0 0 30px #0055ff, inset 0 0 26px #10dfff}.mv-orb-core{width:83%;aspect-ratio:1;border-radius:50%;background:radial-gradient(ellipse at 55% 50%,#060b28 18%,#002282 65%,#04123a 90%);box-shadow:inset 0 0 35px #05264e}.mv-dialog[data-mode="speaking"] .mv-orb{animation-duration:2s,7s}.mv-dialog[data-mode="listening"] .mv-orb{animation-duration:2.5s,10s}@keyframes mv-pulse{50%{transform:scale(1.065);filter:drop-shadow(0 0 32px #08baff)}}@keyframes mv-spin{to{rotate:360deg}}
.mv-conversation{flex:0 1 185px;min-height:80px;overflow:auto;font-size:13px;line-height:1.5}.mv-caption{color:#a4b5d0;margin:8px 0 4px;font-size:12px}.mv-user-text,.mv-ai-text{border:1px solid #293445;border-radius:13px;padding:9px 11px;white-space:pre-wrap;overflow-wrap:anywhere;background:#1b2230;color:#f3f7fd}.mv-ai-text{color:#ccd7ec;background:#141c2c}
.mv-controls{display:flex;justify-content:center;gap:48px;padding:13px 0 0}.mv-control{display:flex;flex-direction:column;align-items:center;gap:5px}.mv-control button{width:61px;height:61px;border:0;border-radius:50%;font-size:26px;color:#fff;cursor:pointer}.mv-mic{background:#0677f9;box-shadow:0 0 19px #0068ef99}.mv-hang{background:#ff2d52}.mv-control small{font-size:12px;color:#afbed8}.mv-mic[aria-pressed="true"]{background:#37435b;box-shadow:none}
.mv-note{text-align:center;color:#78869b;font-size:9px;line-height:1.35;margin:11px 0 0}
@media(max-width:500px){.mv-dialog{padding:15px;border-radius:20px;height:calc(100dvh - 16px)}.mv-heading b{font-size:17px}.mv-overlay{padding:8px}.mv-orb{width:clamp(120px,24vh,195px)}}
@media(prefers-reduced-motion:reduce){.mv-orb{animation:none}}
'''

JS = r'''
export default function(component) {
  const {parentElement:root, data, setTriggerValue} = component;
  const q = s => root.querySelector(s);
  const overlay=q('.mv-overlay'), dialog=q('.mv-dialog'), openBtn=q('.mv-open'), closeBtn=q('.mv-close');
  const mic=q('.mv-mic'), micLabel=q('.mv-mic-label'), hang=q('.mv-hang');
  const status=q('.mv-status'), userText=q('.mv-user-text'), aiText=q('.mv-ai-text'), langSelect=q('.mv-language');
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  const langs = [
    ['en-US','English (US)'],['en-GB','English (UK)'],['bn-BD','বাংলা / Bengali'],['hi-IN','हिन्दी / Hindi'],['ur-PK','اردو / Urdu'],
    ['ar-SA','العربية / Arabic'],['es-ES','Español'],['es-MX','Español (México)'],['fr-FR','Français'],['de-DE','Deutsch'],
    ['it-IT','Italiano'],['pt-BR','Português (Brasil)'],['pt-PT','Português (Portugal)'],['ru-RU','Русский'],['zh-CN','中文 (Mandarin)'],
    ['ja-JP','日本語'],['ko-KR','한국어'],['tr-TR','Türkçe'],['nl-NL','Nederlands'],['id-ID','Bahasa Indonesia'],
    ['ms-MY','Bahasa Melayu'],['th-TH','ไทย'],['vi-VN','Tiếng Việt'],['ta-IN','தமிழ்'],['te-IN','తెలుగు'],
    ['pa-IN','ਪੰਜਾਬੀ'],['fa-IR','فارسی'],['sw-KE','Kiswahili'],['fil-PH','Filipino'],['pl-PL','Polski'],
    ['uk-UA','Українська'],['he-IL','עברית'],['el-GR','Ελληνικά'],['sv-SE','Svenska'],['da-DK','Dansk'],
    ['no-NO','Norsk'],['fi-FI','Suomi'],['ro-RO','Română'],['cs-CZ','Čeština'],['hu-HU','Magyar']
  ];
  langs.forEach(([code,label])=>{const opt=document.createElement('option');opt.value=code;opt.textContent=label;langSelect.append(opt)});
  const state=window.__mergeVoice || (window.__mergeVoice={open:false,enabled:false,muted:false,listening:false,awaiting:false,speaking:false,lang:'en-US',rec:null,seenReply:'',seenFail:'',speech:null,lastUser:'',lastAi:''});
  state.ui={overlay,dialog,mic,micLabel,status,userText,aiText,langSelect,setTriggerValue};
  langSelect.value=state.lang;
  userText.textContent=state.lastUser||'Your words will appear here…';
  aiText.textContent=state.lastAi||'I’m ready to listen.';
  const synth=window.speechSynthesis;
  const stopRecognition=()=>{const r=state.rec;state.rec=null;state.listening=false;if(r){try{r.abort()}catch(e){}}};
  const refresh=()=>{const u=state.ui;u.overlay.hidden=!state.open;const mode=state.speaking?'speaking':state.awaiting?'thinking':state.listening?'listening':'idle';u.dialog.dataset.mode=mode;u.status.textContent=!Rec?'Speech recognition unavailable in this browser':state.speaking?'🔊 Merge AI is speaking…':state.awaiting?'⏳ Merge AI is thinking…':state.listening?'🔵 Listening… speak now':state.muted?'Microphone muted':'Ready to talk';u.mic.setAttribute('aria-pressed',String(state.muted));u.micLabel.textContent=state.muted?'Unmute':'Mute';};
  const listen=()=>{
    if(!state.open||!state.enabled||state.muted||state.listening||state.awaiting||state.speaking||!Rec)return;
    const rec=new Rec();state.rec=rec;rec.lang=state.lang;rec.continuous=false;rec.interimResults=true;rec.maxAlternatives=1;
    rec.onresult=(event)=>{let final='',partial='';for(let i=event.resultIndex;i<event.results.length;i++){const part=event.results[i][0].transcript;if(event.results[i].isFinal)final+=part;else partial+=part;}
      state.ui.userText.textContent=final||partial||'Listening…';
      if(final.trim()&&!state.awaiting){state.lastUser=final.trim();state.awaiting=true;stopRecognition();state.ui.aiText.textContent='Thinking…';state.ui.setTriggerValue('transcript',{id:Date.now()+'-'+Math.random(),text:state.lastUser.slice(0,1000),language:state.lang,language_name:langs.find(v=>v[0]===state.lang)?.[1]||state.lang});refresh()}
    };
    rec.onerror=event=>{state.listening=false;if(['not-allowed','service-not-allowed'].includes(event.error))state.muted=true;state.ui.status.textContent='Microphone: '+event.error;};
    rec.onend=()=>{if(state.rec===rec)state.rec=null;state.listening=false;refresh();};
    try{rec.start();state.listening=true;refresh()}catch(e){state.listening=false;state.ui.status.textContent='Could not open the microphone.';}
  };
  const close=()=>{state.open=false;state.enabled=false;state.awaiting=false;state.speaking=false;stopRecognition();if(synth)synth.cancel();refresh()};
  const open=()=>{state.open=true;state.enabled=true;state.muted=false;refresh();listen()};
  openBtn.onclick=open;closeBtn.onclick=close;hang.onclick=close;
  mic.onclick=()=>{state.muted=!state.muted;if(state.muted){stopRecognition();if(synth)synth.cancel();state.speaking=false}else{listen()}refresh()};
  langSelect.onchange=()=>{state.lang=langSelect.value;stopRecognition();if(synth)synth.cancel();state.speaking=false;if(state.enabled&&!state.awaiting&&!state.muted)listen();refresh()};
  if(data.reply_id&&data.reply_id!==state.seenReply){state.seenReply=data.reply_id;state.awaiting=false;state.lastAi=String(data.reply||'');state.ui.aiText.textContent=state.lastAi;stopRecognition();
    if(state.enabled&&state.open&&synth&&state.lastAi){const spoken=new SpeechSynthesisUtterance(state.lastAi.slice(0,3500));spoken.lang=state.lang;spoken.rate=1;const voices=synth.getVoices();const match=voices.find(v=>v.lang?.toLowerCase()===state.lang.toLowerCase())||voices.find(v=>v.lang?.split('-')[0]===state.lang.split('-')[0]);if(match)spoken.voice=match;state.speaking=true;spoken.onend=()=>{state.speaking=false;refresh();if(state.enabled&&!state.muted)listen()};spoken.onerror=()=>{state.speaking=false;refresh();if(state.enabled&&!state.muted)listen()};synth.cancel();synth.speak(spoken);}else if(state.open&&state.enabled&&!state.muted){listen()}
  }
  if(data.failed_id&&data.failed_id!==state.seenFail){state.seenFail=data.failed_id;state.awaiting=false;state.ui.aiText.textContent='I could not complete that answer. Please try again.';if(state.enabled&&!state.muted)listen()}
  refresh();
  return ()=>{};
}
'''

voice_component = st.components.v2.component('merge_ai_voice_modal', html=HTML, css=CSS, js=JS)


def voice_chat(*, reply: str = '', reply_id: str = '', failed_id: str = '') -> dict | None:
    """Render button/popup and return {text, language, language_name} for a new utterance."""
    result = voice_component(
        key='merge_ai_voice_modal',
        data={'reply': reply, 'reply_id': reply_id, 'failed_id': failed_id},
        on_transcript_change=lambda: None,
    )
    event = getattr(result, 'transcript', None)
    if not isinstance(event, dict) or not isinstance(event.get('text'), str):
        return None
    event_id = str(event.get('id') or '')
    if not event_id or st.session_state.get('ma_last_voice_event') == event_id:
        return None
    st.session_state.ma_last_voice_event = event_id
    return {
        'text': event['text'].strip()[:1000],
        'language': str(event.get('language') or 'en-US')[:20],
        'language_name': str(event.get('language_name') or 'English')[:70],
    }
