"""Merge AI browser live conversation modal, using Streamlit custom components v2.

Browser speech recognition / synthesis are device-dependent. Audio may be processed
by the browser vendor. Only transcripts are sent to Merge AI's Python backend.
"""
from __future__ import annotations

import streamlit as st
from voice_text import check_final_answer, prepare_speech_text, browser_chunks, UnsafeSpeechText
from voice_config import VoiceConfig

HTML = r'''
<div class="mv-mount">
  <button class="mv-open" type="button"><span>🎙</span> Live conversation</button>
  <div class="mv-overlay" hidden>
    <section class="mv-dialog" role="dialog" aria-modal="true" aria-label="Merge AI live voice conversation">
      <header class="mv-header"><div class="mv-logo">▥</div><div class="mv-heading"><b>Merge AI Voice</b><span>Talk naturally with Merge AI</span></div><button class="mv-close" aria-label="Close voice conversation" type="button">×</button></header>
      <div class="mv-language-row"><label for="mv-language">Conversation language</label><select id="mv-language" class="mv-language"></select></div>
      <div class="mv-voice-row"><label for="mv-voice-provider">Voice</label><select id="mv-voice-provider" class="mv-voice-provider"><option value="kokoro">✦ Kokoro · Natural Male</option><option value="browser">Browser voice · Free fallback</option></select></div>
      <div class="mv-provider-status" aria-live="polite"></div>
      <div class="mv-status" aria-live="polite">Ready to talk</div>
      <div class="mv-orb-wrap"><div class="mv-orb"><div class="mv-orb-core"></div></div></div>
      <div class="mv-conversation">
        <div class="mv-caption">You</div><div class="mv-user-text">Your words will appear here…</div>
        <div class="mv-caption">Merge AI</div><div class="mv-ai-text">I’m ready to listen.</div><button type="button" class="mv-play" hidden>🔊 Play answer</button>
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
.mv-voice-row{display:flex;justify-content:space-between;align-items:center;gap:9px;margin:-5px 0 6px}.mv-voice-row label{font-size:12px;color:#aebbd0}.mv-voice-provider{width:min(245px,66%);background:#141d2c;border:1px solid #354154;color:#e9f4ff;border-radius:9px;font-size:12px;padding:9px 7px}.mv-provider-status{text-align:center;color:#93b8db;font-size:11px;min-height:16px;margin-bottom:6px}.mv-status{text-align:center;color:#adc7ef;font-size:14px;min-height:23px}
.mv-orb-wrap{flex:1;min-height:125px;display:grid;place-items:center;overflow:hidden}.mv-orb{width:clamp(125px,27vh,235px);aspect-ratio:1;border-radius:50%;background:conic-gradient(from 30deg,#31ffff,#0157fd,#031442,#0a28b2,#04d6ff,#0057ed,#31ffff);filter:drop-shadow(0 0 25px #087fff99);display:grid;place-items:center;animation:mv-pulse 4s ease-in-out infinite, mv-spin 14s linear infinite;box-shadow:0 0 30px #0055ff, inset 0 0 26px #10dfff}.mv-orb-core{width:83%;aspect-ratio:1;border-radius:50%;background:radial-gradient(ellipse at 55% 50%,#060b28 18%,#002282 65%,#04123a 90%);box-shadow:inset 0 0 35px #05264e}.mv-dialog[data-mode="speaking"] .mv-orb{animation-duration:2s,7s}.mv-dialog[data-mode="listening"] .mv-orb{animation-duration:2.5s,10s}@keyframes mv-pulse{50%{transform:scale(1.065);filter:drop-shadow(0 0 32px #08baff)}}@keyframes mv-spin{to{rotate:360deg}}
.mv-conversation{flex:0 1 185px;min-height:80px;overflow:auto;font-size:13px;line-height:1.5}.mv-caption{color:#a4b5d0;margin:8px 0 4px;font-size:12px}.mv-user-text,.mv-ai-text{border:1px solid #293445;border-radius:13px;padding:9px 11px;white-space:pre-wrap;overflow-wrap:anywhere;background:#1b2230;color:#f3f7fd}.mv-ai-text{color:#ccd7ec;background:#141c2c}
.mv-play{margin:8px 0 2px;background:#182c49;color:#d7efff;border:1px solid #348ff1;border-radius:10px;padding:9px 13px;cursor:pointer;font-weight:650}.mv-play:hover{background:#24406c}.mv-play[hidden]{display:none!important}
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
  const voiceSelect=q('.mv-voice-provider'), providerStatus=q('.mv-provider-status');
  const status=q('.mv-status'), userText=q('.mv-user-text'), aiText=q('.mv-ai-text'), langSelect=q('.mv-language'), play=q('.mv-play');
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
  langSelect.replaceChildren();
  langs.forEach(([code,label])=>{const opt=document.createElement('option');opt.value=code;opt.textContent=label;langSelect.append(opt)});
  const synth=window.speechSynthesis;
  const previous=window.__mergeVoice;
  if(previous&&previous.conversation!==data.conversation_id){
    previous.enabled=false;previous.token++;
    if(previous.rec)previous.rec.abort();
    if(previous.audioPlayer)previous.audioPlayer.pause();
    if(synth)synth.cancel();window.__mergeVoice=null;
  }
  const state=window.__mergeVoice||(window.__mergeVoice={conversation:data.conversation_id,
    open:false,enabled:false,muted:false,listening:false,awaiting:false,speaking:false,
    lang:'en-US',rec:null,seenReply:'',seenFail:'',lastUser:'',lastAi:'',audioB64:'',
    audioPlayer:null,voiceProvider:'kokoro',audioError:'',token:0,pending:'',chunks:[],allowFallback:true,speechStopped:false});
  state.ui={overlay,dialog,mic,micLabel,status,userText,aiText,langSelect,play,providerStatus,setTriggerValue};
  langSelect.value=state.lang;
  // Availability affects playback, not the user's ability to select Kokoro.
  voiceSelect.querySelector('option[value=kokoro]').disabled=false;
  state.kokoroAvailable=Boolean(data.kokoro_available);
  voiceSelect.value=state.voiceProvider;
  userText.textContent=state.lastUser||'Your words will appear here…';
  aiText.textContent=state.lastAi||'I’m ready to listen.';
  const stopRecognition=()=>{const rec=state.rec;state.rec=null;state.listening=false;if(rec){rec.onend=null;rec.abort();}};
  const stopAudio=()=>{state.token++;if(state.audioPlayer){state.audioPlayer.pause();state.audioPlayer=null;}
    if(window.__mergeAudioOwner==='live'){if(synth)synth.cancel();window.__mergeStopAudio=null;window.__mergeAudioOwner=null;}state.speaking=false;};
  const claimAudio=()=>{if(window.__mergeStopAudio&&window.__mergeAudioOwner!=='live')window.__mergeStopAudio();window.__mergeStopAudio=stopAudio;window.__mergeAudioOwner='live';};
  const refresh=()=>{const u=state.ui;u.overlay.hidden=!state.open;u.play.hidden=!state.lastAi||!state.open;
    u.dialog.dataset.mode=state.speaking?'speaking':state.awaiting?'thinking':state.listening?'listening':'idle';
    u.status.textContent=state.speaking?'🔊 Merge AI is speaking…':state.awaiting?'⏳ Merge AI is thinking…':state.listening?'🔵 Listening… speak now':state.muted?'Microphone muted':!Rec?'Speech recognition unavailable in this browser':'Ready to talk';
    u.mic.setAttribute('aria-pressed',String(state.muted));u.micLabel.textContent=state.muted?'Unmute':'Mute';
    u.providerStatus.textContent=state.audioError||(state.voiceProvider==='kokoro'?(state.kokoroAvailable?'✦ Kokoro · Liam · American English':'Kokoro selected · browser fallback until available'):'Browser text-to-speech');};
  const listen=()=>{
    if(!state.open||!state.enabled||state.muted||state.listening||state.awaiting||state.speaking||!Rec)return;
    const rec=new Rec();state.rec=rec;rec.lang=state.lang;rec.continuous=false;rec.interimResults=true;rec.maxAlternatives=1;
    rec.onresult=event=>{if(state.rec!==rec||!state.open)return;let final='',partial='';
      for(let i=event.resultIndex;i<event.results.length;i++){const part=event.results[i][0].transcript;if(event.results[i].isFinal)final+=part;else partial+=part;}
      state.ui.userText.textContent=final||partial||'Listening…';
      if(final.trim()&&!state.awaiting){state.speechStopped=false;state.lastUser=final.trim();state.awaiting=true;stopRecognition();state.ui.aiText.textContent='Thinking…';
        state.pending=Date.now()+'-'+Math.random();
        state.ui.setTriggerValue('transcript',{id:state.pending,text:state.lastUser.slice(0,1000),language:state.lang,language_name:langs.find(v=>v[0]===state.lang)?.[1]||state.lang,voice_provider:state.voiceProvider});refresh();}
    };
    rec.onerror=event=>{if(state.rec!==rec)return;state.listening=false;
      if(['not-allowed','service-not-allowed','audio-capture'].includes(event.error))state.muted=true;
      refresh();state.ui.status.textContent='Microphone: '+event.error;};
    rec.onend=()=>{if(state.rec!==rec)return;state.rec=null;state.listening=false;refresh();
      if(state.open&&state.enabled&&!state.muted&&!state.awaiting&&!state.speaking)setTimeout(listen,250);};
    try{rec.start();state.listening=true;refresh();}catch(e){state.listening=false;state.ui.status.textContent='Could not open the microphone.';}
  };
  const speakAnswer=()=>{
    if(!state.open||!state.enabled||!state.lastAi)return;
    stopRecognition();stopAudio();claimAudio();const token=state.token;
    const finished=()=>{if(token!==state.token)return;state.speaking=false;state.audioPlayer=null;refresh();listen();};
    const browserSpeech=()=>{
      if(!synth){finished();state.ui.status.textContent='Speech playback is unavailable on this browser.';return;}
      if(!state.allowFallback){state.audioError=state.audioError||'Speech playback is unavailable.';finished();return;}
      const chunks=state.chunks;
      let index=0;state.speaking=true;refresh();
      const next=()=>{if(token!==state.token||!state.open||!state.enabled)return;if(index>=chunks.length){finished();return;}
        const utter=new SpeechSynthesisUtterance(chunks[index++]);utter.lang=state.lang;utter.rate=Number(data.speed||1.03);
        const voices=synth.getVoices(), desired=state.lang.toLowerCase();
        const voice=voices.find(v=>v.lang?.toLowerCase()===desired)||voices.find(v=>v.lang?.split('-')[0]===desired.split('-')[0]);
        if(voice)utter.voice=voice;utter.onend=next;
        utter.onerror=()=>{if(token!==state.token)return;state.speaking=false;refresh();state.ui.status.textContent='Click Play answer to retry speech.';};
        try{synth.speak(utter);if(synth.paused)synth.resume();}catch(e){state.speaking=false;refresh();}
      };next();
    };
    if(state.voiceProvider==='kokoro'&&state.lang.startsWith('en')&&state.audioB64){
      const player=new Audio('data:audio/wav;base64,'+state.audioB64);state.audioPlayer=player;state.speaking=true;refresh();
      player.onended=finished;
      let failed=false;
      player.onerror=()=>{if(token!==state.token||failed)return;failed=true;player.pause();state.audioB64='';state.audioPlayer=null;state.speaking=false;state.audioError=state.allowFallback?'Kokoro playback failed — using browser voice':'Kokoro playback failed';browserSpeech();};
      player.play().catch(error=>{if(token!==state.token)return;state.speaking=false;refresh();
        if(error.name==='NotAllowedError')state.ui.status.textContent='Click 🔊 Play answer to hear Kokoro.';
        else player.onerror();});return;
    }
    if(state.voiceProvider==='kokoro')state.audioError=state.audioError||(state.lang.startsWith('en')?'Kokoro unavailable — browser fallback':'Browser voice for this language');
    browserSpeech();
  };
  play.onclick=()=>{state.speechStopped=false;speakAnswer();};
  voiceSelect.onchange=()=>{stopAudio();state.voiceProvider=voiceSelect.value;state.audioError='';refresh();listen();};
  const close=()=>{state.open=false;state.enabled=false;state.awaiting=false;state.pending='';stopRecognition();stopAudio();refresh();};
  const open=()=>{state.open=true;state.enabled=true;state.muted=false;refresh();listen();};
  openBtn.onclick=open;closeBtn.onclick=close;hang.onclick=close;
  mic.onclick=()=>{state.muted=!state.muted;if(state.muted){stopRecognition();stopAudio();state.speechStopped=true;}else listen();refresh();};
  langSelect.onchange=()=>{stopRecognition();stopAudio();state.pending='';state.awaiting=false;state.speechStopped=true;state.lang=langSelect.value;state.audioError='';listen();refresh();};
  if(data.audio_pending&&data.reply_id===state.pending){
    state.ui.aiText.textContent=String(data.reply||'');
    state.audioError='Preparing Kokoro voice…';
  }
  if(!data.audio_pending&&data.reply_id&&data.reply_id!==state.seenReply&&data.reply_id===state.pending){
    state.seenReply=data.reply_id;state.awaiting=false;state.pending='';state.lastAi=String(data.reply||'');
    state.audioB64=String(data.audio_b64||'');state.chunks=Array.isArray(data.speech_chunks)?data.speech_chunks:[];
    state.allowFallback=data.allow_fallback!==false;state.audioError=String(data.audio_error||'');state.ui.aiText.textContent=state.lastAi;
    stopRecognition();refresh();if(state.open&&state.enabled&&!state.muted&&!state.speechStopped)speakAnswer();else listen();
  }
  if(data.failed_id&&data.failed_id!==state.seenFail&&data.failed_id===state.pending){
    state.seenFail=data.failed_id;state.awaiting=false;state.pending='';state.ui.aiText.textContent='I could not complete that answer. Please try again.';listen();}
  refresh();
  return ()=>{};
}

'''

voice_component = st.components.v2.component('merge_ai_voice_modal', html=HTML, css=CSS, js=JS)


def voice_chat(*, reply: str = '', reply_id: str = '', failed_id: str = '', audio_b64: str = '',
               kokoro_available: bool = False, conversation_id: str = '', audio_pending: bool = False,
               audio_error: str = '', allow_fallback: bool = True, config: VoiceConfig | None = None) -> dict | None:
    """Existing interface, extended with request-scoped delayed audio metadata."""
    config = config or VoiceConfig()
    try:
        check_final_answer(reply)
        chunks = browser_chunks(prepare_speech_text(reply))
    except UnsafeSpeechText as exc:
        chunks, audio_b64, allow_fallback, audio_error = [], '', False, str(exc)
    result = voice_component(
        key='merge_ai_voice_modal',
        data={'reply': reply, 'reply_id': reply_id, 'failed_id': failed_id, 'audio_b64': audio_b64,
              'kokoro_available': kokoro_available, 'conversation_id': conversation_id,
              'audio_pending': audio_pending, 'audio_error': audio_error,
              'allow_fallback': allow_fallback and config.browser_fallback, 'speech_chunks': chunks,
              'speed': config.speed},
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
        'id': event_id,
        'text': event['text'].strip()[:1000],
        'language': str(event.get('language') or 'en-US')[:20],
        'language_name': str(event.get('language_name') or 'English')[:70],
        'voice_provider': 'kokoro' if event.get('voice_provider') == 'kokoro' else 'browser',
    }
