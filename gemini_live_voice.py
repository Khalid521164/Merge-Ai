"""Gemini Live API full-screen voice experience for Merge AI.

The permanent Gemini API key stays server-side. The browser receives only a
single-use ephemeral token and connects directly to Gemini over WebSocket.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests
import streamlit as st


MODEL = "models/gemini-3.8-live"
VOICE_NAME = "Puck"
TOKEN_URL = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"


def create_ephemeral_token(api_key: str, system_instruction: str = "") -> tuple[str | None, str | None]:
    """Create a one-use, short-lived Live API token without exposing the API key."""
    if not api_key:
        return None, "GEMINI_API_KEY is missing. Add it to Streamlit Secrets."

    now = datetime.now(timezone.utc)
    # Mint a short-lived token only. The full Live API setup is sent as the
    # first WebSocket message, which is the standard BidiGenerateContent flow.
    payload = {
        "uses": 1,
        "expireTime": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + timedelta(minutes=3)).isoformat().replace("+00:00", "Z"),
    }

    try:
        response = requests.post(
            TOKEN_URL,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("name")
        if not isinstance(token, str) or not token:
            return None, "Google did not return a Live API session token."
        return token, None
    except requests.RequestException as exc:
        detail = ""
        if getattr(exc, "response", None) is not None:
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                detail = ""
        return None, detail or "Could not create a Gemini Live session. Check the API key and Gemini API access."


HTML = r'''
<div class="gl-shell">
  <div class="gl-card">
    <header class="gl-header">
      <div class="gl-brand"><span class="gl-mark">M</span><div><b>Merge AI</b><small>Live voice conversation</small></div></div>
      <button class="gl-exit" type="button" aria-label="Back to chat">Back to chat</button>
    </header>
    <main class="gl-main">
      <div class="gl-eyebrow">GEMINI LIVE</div>
      <h1>Talk naturally.</h1>
      <p class="gl-subtitle">A real-time conversation with Merge AI</p>
      <div class="gl-orb-area"><div class="gl-orb"><div class="gl-orb-inner"></div><div class="gl-orb-glow"></div></div></div>
      <div class="gl-status" aria-live="polite">Ready when you are</div>
      <div class="gl-transcript">
        <div class="gl-line"><span>You</span><p class="gl-user">Your words will appear here.</p></div>
        <div class="gl-line"><span>Merge AI</span><p class="gl-assistant">I’m listening.</p></div>
      </div>
      <div class="gl-actions">
        <button class="gl-mute" type="button" disabled><span>🎙</span><small>Mute</small></button>
        <button class="gl-start" type="button"><span>Start talking</span></button>
        <button class="gl-end" type="button" disabled><span>■</span><small>End</small></button>
      </div>
      <p class="gl-footnote">Microphone access is required. Audio is streamed to Google Gemini Live to generate responses.</p>
    </main>
  </div>
</div>
'''

CSS = r'''
.gl-shell{position:fixed;inset:0;z-index:2147483000;background:radial-gradient(ellipse at 50% 38%,#102d43 0%,#09131f 44%,#070b12 100%);color:#f5f8fc;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}
.gl-card{width:min(760px,100%);height:min(900px,calc(100dvh - 32px));display:flex;flex-direction:column;border:1px solid #24394b;border-radius:28px;background:linear-gradient(155deg,rgba(14,30,45,.96),rgba(7,14,24,.97));box-shadow:0 24px 90px #0008;overflow:hidden}
.gl-header{display:flex;align-items:center;justify-content:space-between;padding:19px 23px;border-bottom:1px solid #243443}
.gl-brand{display:flex;align-items:center;gap:11px}.gl-mark{width:39px;height:39px;border-radius:12px;display:grid;place-items:center;background:#147353;color:#fff;font-weight:850;font-size:21px}.gl-brand div{display:flex;flex-direction:column;gap:2px}.gl-brand b{font-size:16px}.gl-brand small{font-size:11px;color:#91a6b8}
.gl-exit{border:1px solid #34485a;background:#172838;color:#dce8f2;border-radius:11px;padding:9px 13px;font-size:12px;font-weight:650;cursor:pointer}.gl-exit:hover{background:#20384c}
.gl-main{flex:1;min-height:0;display:flex;flex-direction:column;align-items:center;padding:28px 28px 18px;text-align:center;overflow:auto}
.gl-eyebrow{font-size:10px;letter-spacing:3px;font-weight:800;color:#66d8bd}.gl-main h1{font-size:clamp(28px,5vw,42px);letter-spacing:-1.6px;margin:8px 0 3px}.gl-subtitle{font-size:13px;color:#94a8ba;margin:0}
.gl-orb-area{flex:1;min-height:170px;display:grid;place-items:center;width:100%;overflow:hidden}
.gl-orb{width:clamp(145px,26vh,230px);aspect-ratio:1;border-radius:50%;position:relative;display:grid;place-items:center;background:conic-gradient(from 15deg,#75ffe0,#168dff,#4153dc,#0e345e,#20c6bb,#75ffe0);box-shadow:0 0 34px #1e9dd877,inset 0 0 26px #a8fff4aa;animation:gl-breathe 4s ease-in-out infinite}
.gl-orb-inner{width:82%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle at 48% 38%,#153d59 0%,#071a30 58%,#06101e 100%);box-shadow:inset 0 0 38px #0b8b9b88}
.gl-orb-glow{position:absolute;inset:-13%;border-radius:50%;border:1px solid #5ce9d533;filter:blur(7px)}
.gl-card[data-state="listening"] .gl-orb{animation:gl-breathe 1.6s ease-in-out infinite;box-shadow:0 0 48px #21d8bd88,inset 0 0 26px #a8fff4aa}
.gl-card[data-state="speaking"] .gl-orb{animation:gl-breathe .9s ease-in-out infinite;box-shadow:0 0 56px #3c9bff99,inset 0 0 30px #b6e8ffbb}
@keyframes gl-breathe{50%{transform:scale(1.07);filter:saturate(1.25)}}
.gl-status{min-height:23px;font-size:14px;color:#a9c8dc;margin:2px 0 14px}
.gl-transcript{width:min(560px,100%);display:grid;grid-template-columns:1fr 1fr;gap:12px;text-align:left}
.gl-line{min-width:0;border:1px solid #263d4f;background:#0d1c2b;border-radius:14px;padding:11px 13px}.gl-line span{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#6ed7c4;font-weight:800}.gl-line p{font-size:12px;line-height:1.5;color:#d6e1e9;margin:6px 0 0;white-space:pre-wrap;overflow-wrap:anywhere;max-height:96px;overflow:auto}
.gl-actions{display:flex;align-items:center;justify-content:center;gap:27px;margin:19px 0 8px}
.gl-actions button{cursor:pointer;border:0;color:white}.gl-actions button:disabled{opacity:.38;cursor:not-allowed}
.gl-mute,.gl-end{width:55px;height:55px;border-radius:50%;background:#20374a;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px}.gl-mute span{font-size:20px}.gl-end span{font-size:18px;color:#ff9eab}.gl-actions small{font-size:9px;color:#c3d3df}
.gl-start{min-width:150px;padding:15px 22px;border-radius:999px;background:linear-gradient(110deg,#087d78,#1473b8);font-size:13px;font-weight:750;box-shadow:0 7px 24px #087d7855}.gl-start:hover{filter:brightness(1.12)}
.gl-footnote{font-size:9px;line-height:1.4;color:#70869a;max-width:490px;margin:7px 0 0}
@media(max-width:560px){.gl-shell{padding:0}.gl-card{height:100dvh;border-radius:0;border:0}.gl-header{padding:14px 15px}.gl-main{padding:26px 15px 15px}.gl-transcript{grid-template-columns:1fr;gap:8px}.gl-line p{max-height:68px}.gl-orb-area{min-height:145px}.gl-actions{gap:20px}}
@media(prefers-reduced-motion:reduce){.gl-orb{animation:none!important}}
'''

JS = r'''
export default function(component) {
  const root = component.parentElement;
  const data = component.data || {};
  const q = (s) => root.querySelector(s);
  const card=q(".gl-card"), startBtn=q(".gl-start"), muteBtn=q(".gl-mute"), endBtn=q(".gl-end"), exitBtn=q(".gl-exit");
  const status=q(".gl-status"), userEl=q(".gl-user"), assistantEl=q(".gl-assistant");
  const state = window.__mergeGeminiLive || (window.__mergeGeminiLive = {
    ws:null,stream:null,ctx:null,source:null,processor:null,muted:false,connected:false,
    starting:false,playAt:0,playing:new Set(),userText:"",assistantText:"",
    lastEvent:"",token:"",closed:false,connectTimer:null
  });
  const setStatus=(text,mode)=>{
    status.textContent=text;
    card.dataset.state=mode||"idle";
  };
  const stopPlayback=()=>{
    state.playing.forEach((node)=>{try{node.stop()}catch(e){}});
    state.playing.clear();
    state.playAt=state.ctx?state.ctx.currentTime:0;
  };
  const closeMic=()=>{
    if(state.processor){try{state.processor.disconnect()}catch(e){}state.processor.onaudioprocess=null;state.processor=null;}
    if(state.source){try{state.source.disconnect()}catch(e){}state.source=null;}
    if(state.stream){state.stream.getTracks().forEach(t=>t.stop());state.stream=null;}
  };
  const closeAll=()=>{
    state.closed=true;state.connected=false;state.starting=false;
    closeMic();stopPlayback();
    if(state.ws){try{state.ws.close(1000,"User ended voice session")}catch(e){}state.ws=null;}
    if(state.ctx){try{state.ctx.close()}catch(e){}state.ctx=null;}
    state.muted=false;muteBtn.disabled=true;endBtn.disabled=true;startBtn.disabled=false;
    startBtn.querySelector("span").textContent="Start talking";
    muteBtn.querySelector("small").textContent="Mute";
    setStatus("Voice session ended","idle");
  };
  const floatToPcm16=(input,fromRate,toRate)=>{
    const ratio=fromRate/toRate;
    const length=Math.floor(input.length/ratio);
    const pcm=new Int16Array(length);
    for(let i=0;i<length;i++){
      const start=Math.floor(i*ratio),end=Math.min(Math.floor((i+1)*ratio),input.length);
      let sum=0,count=0;
      for(let j=start;j<end;j++){sum+=input[j];count++;}
      let sample=count?sum/count:0;
      sample=Math.max(-1,Math.min(1,sample));
      pcm[i]=sample<0?sample*32768:sample*32767;
    }
    return pcm;
  };
  const pcmToBase64=(pcm)=>{
    const bytes=new Uint8Array(pcm.buffer);
    let binary="";
    const step=0x8000;
    for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode.apply(null,bytes.subarray(i,Math.min(i+step,bytes.length)));
    return btoa(binary);
  };
  const playPcm=(base64)=>{
    if(!state.ctx)return;
    const binary=atob(base64),samples=new Int16Array(Math.floor(binary.length/2));
    for(let i=0;i<samples.length;i++)samples[i]=(binary.charCodeAt(i*2)&255)|(binary.charCodeAt(i*2+1)<<8);
    const buffer=state.ctx.createBuffer(1,samples.length,24000);
    const channel=buffer.getChannelData(0);
    for(let i=0;i<samples.length;i++)channel[i]=samples[i]/32768;
    const node=state.ctx.createBufferSource();node.buffer=buffer;node.connect(state.ctx.destination);
    const start=Math.max(state.ctx.currentTime+0.025,state.playAt);
    state.playAt=start+buffer.duration;state.playing.add(node);
    node.onended=()=>state.playing.delete(node);
    node.start(start);
    card.dataset.state="speaking";
  };
  const startMicrophone=async()=>{
    state.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    state.ctx=new (window.AudioContext||window.webkitAudioContext)();
    await state.ctx.resume();
    state.source=state.ctx.createMediaStreamSource(state.stream);
    state.processor=state.ctx.createScriptProcessor(4096,1,1);
    state.processor.onaudioprocess=(event)=>{
      event.outputBuffer.getChannelData(0).fill(0);
      if(!state.connected||state.muted||!state.ws||state.ws.readyState!==WebSocket.OPEN)return;
      const pcm=floatToPcm16(event.inputBuffer.getChannelData(0),state.ctx.sampleRate,16000);
      if(!pcm.length)return;
      state.ws.send(JSON.stringify({realtimeInput:{audio:{mimeType:"audio/pcm;rate=16000",data:pcmToBase64(pcm)}}}));
    };
    state.source.connect(state.processor);
    state.processor.connect(state.ctx.destination);
  };
  const onMessage=(event)=>{
    let message;
    try{message=JSON.parse(event.data)}catch(e){return;}
    if(message.setupComplete){
      if(state.connectTimer){clearTimeout(state.connectTimer);state.connectTimer=null;}
      state.connected=true;state.starting=false;startBtn.disabled=true;endBtn.disabled=false;muteBtn.disabled=false;
      setStatus("Listening — speak naturally","listening");
      startMicrophone().catch((err)=>{setStatus("Microphone error: "+(err.message||"permission denied"),"error");closeAll();});
      return;
    }
    if(message.error){
      const msg=message.error.message||"Gemini Live returned an error.";
      setStatus(msg,"error");closeAll();return;
    }
    const server=message.serverContent||{};
    if(server.interrupted){stopPlayback();setStatus("Listening — you can interrupt anytime","listening");}
    if(server.inputTranscription&&server.inputTranscription.text){
      state.userText+=server.inputTranscription.text;
      userEl.textContent=state.userText;
    }
    if(server.outputTranscription&&server.outputTranscription.text){
      state.assistantText+=server.outputTranscription.text;
      assistantEl.textContent=state.assistantText;
    }
    const parts=(server.modelTurn&&server.modelTurn.parts)||[];
    parts.forEach((part)=>{
      if(part.inlineData&&part.inlineData.data&&String(part.inlineData.mimeType||"").includes("audio/pcm")){
        playPcm(part.inlineData.data);
      }
    });
    if(server.turnComplete){
      const user=state.userText.trim(),assistant=state.assistantText.trim();
      if(user||assistant){
        const id=Date.now().toString()+"-"+Math.random().toString(36).slice(2);
        component.setTriggerValue("turn",{id:id,user:user,assistant:assistant});
      }
      state.userText="";state.assistantText="";
      if(state.connected)setStatus("Listening — speak naturally","listening");
    }
  };
  const connect=async()=>{
    if(state.starting||state.connected)return;
    if(!data.token){setStatus("Missing Gemini session token. Reload and try again.","error");return;}
    if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){setStatus("Microphone access requires a supported browser and HTTPS.","error");return;}
    state.starting=true;state.closed=false;state.token=data.token;
    startBtn.disabled=true;setStatus("Connecting securely to Gemini…","thinking");
    const url="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token="+encodeURIComponent(data.token);
    const ws=new WebSocket(url);state.ws=ws;
    // Timeout covers both the WebSocket handshake and Gemini's setup response.
    state.connectTimer=setTimeout(()=>{
      if(state.starting&&!state.connected){
        closeAll();
        setStatus("Gemini connection timed out. Tap Start talking to try again.","error");
      }
    },20000);
    ws.onopen=()=>{
      const setup={
        model:"models/gemini-3.8-live",
        generationConfig:{
          responseModalities:["AUDIO"],
          speechConfig:{voiceConfig:{prebuiltVoiceConfig:{voiceName:"Puck"}}}
        },
        systemInstruction:{parts:[{text:String(data.systemInstruction||"You are Merge AI, a warm, natural conversational assistant. Speak clearly and naturally in the language the user uses.")}]},
        inputAudioTranscription:{},
        outputAudioTranscription:{},
        realtimeInputConfig:{automaticActivityDetection:{disabled:false},activityHandling:"START_OF_ACTIVITY_INTERRUPTS"},
        sessionResumption:{}
      };
      ws.send(JSON.stringify({setup:setup}));
    };
    ws.onmessage=onMessage;
    ws.onerror=()=>{
      setStatus("Gemini WebSocket connection error. Check the network and try again.","error");
    };
    ws.onclose=(event)=>{
      if(state.connectTimer){clearTimeout(state.connectTimer);state.connectTimer=null;}
      state.connected=false;state.starting=false;closeMic();stopPlayback();
      if(state.ctx){try{state.ctx.close()}catch(e){}state.ctx=null;}
      startBtn.disabled=false;endBtn.disabled=true;muteBtn.disabled=true;
      if(!state.closed)setStatus(event.reason||("Gemini connection closed (code "+event.code+"). You can reconnect."),"error");
    };
  };
  startBtn.onclick=()=>connect();
  muteBtn.onclick=()=>{
    if(!state.connected)return;
    state.muted=!state.muted;
    if(state.muted)closeMic();
    else startMicrophone().catch((e)=>setStatus("Could not restart microphone: "+e.message,"error"));
    muteBtn.querySelector("small").textContent=state.muted?"Unmute":"Mute";
    muteBtn.setAttribute("aria-pressed",String(state.muted));
    if(!state.muted)setStatus("Listening — speak naturally","listening");
    else setStatus("Microphone muted","idle");
  };
  endBtn.onclick=closeAll;
  exitBtn.onclick=()=>{
    closeAll();
    component.setTriggerValue("exit",{id:Date.now().toString()});
  };
  if(state.connected){startBtn.disabled=true;endBtn.disabled=false;muteBtn.disabled=false;setStatus("Connected — speak naturally","listening");}
}
'''

voice_component = st.components.v2.component(
    "merge_ai_gemini_live",
    html=HTML,
    css=CSS,
    js=JS,
)


def gemini_live_voice(*, token: str, system_instruction: str, key: str = "merge_ai_gemini_live") -> dict | None:
    """Render the full-screen Live API UI and return completed transcript turns."""
    result = voice_component(
        key=key,
        data={
            "token": token,
            "systemInstruction": system_instruction,
        },
        on_turn_change=lambda: None,
        on_exit_change=lambda: None,
    )
    turn = getattr(result, "turn", None)
    if isinstance(turn, dict):
        event_id = str(turn.get("id") or "")
        last_id = st.session_state.get("ma_gemini_last_turn", "")
        if event_id and event_id != last_id:
            st.session_state.ma_gemini_last_turn = event_id
            return {"type": "turn", "user": str(turn.get("user") or "").strip(), "assistant": str(turn.get("assistant") or "").strip()}
    exit_event = getattr(result, "exit", None)
    if isinstance(exit_event, dict) and exit_event.get("id"):
        return {"type": "exit"}
    return None
