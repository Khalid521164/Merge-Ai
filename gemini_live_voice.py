"""Gemini Live API full-screen voice experience for Merge AI.

The permanent Gemini API key remains on the server. The browser receives a
short-lived, limited-use token and connects directly to Gemini over WebSocket.
The microphone is prepared from the user's Start talking click so mobile
browsers can unlock audio before the Live handshake completes.
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
    # The current v1beta AuthToken schema accepts a complete
    # BidiGenerateContentSetup under bidiGenerateContentSetup.
    # It does not accept the older liveConnectConstraints property.
    bidi_setup = {
        "model": MODEL,
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": VOICE_NAME}
                }
            },
        },
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "realtimeInputConfig": {
            "automaticActivityDetection": {"disabled": False},
            "activityHandling": "START_OF_ACTIVITY_INTERRUPTS",
        },
        "sessionResumption": {},
    }
    if system_instruction:
        bidi_setup["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    payload = {
        "uses": 3,
        "expireTime": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
        "newSessionExpireTime": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "bidiGenerateContentSetup": bidi_setup,
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
  const q = (selector) => root.querySelector(selector);
  const card = q(".gl-card");
  const startBtn = q(".gl-start");
  const muteBtn = q(".gl-mute");
  const endBtn = q(".gl-end");
  const exitBtn = q(".gl-exit");
  const status = q(".gl-status");
  const userEl = q(".gl-user");
  const assistantEl = q(".gl-assistant");

  if (!card || !startBtn || !muteBtn || !endBtn || !exitBtn || !status) return;

  const defaults = {
    ws: null,
    stream: null,
    ctx: null,
    source: null,
    processor: null,
    muted: false,
    connected: false,
    starting: false,
    playAt: 0,
    playing: new Set(),
    userText: "",
    assistantText: "",
    token: "",
    closed: false,
    connectTimer: null,
    micRequestId: 0
  };
  const { setTriggerValue } = component;
  const state = window.__mergeGeminiLive ||
    (window.__mergeGeminiLive = defaults);
  Object.keys(defaults).forEach((key) => {
    if (!(key in state)) state[key] = defaults[key];
  });

  const setStatus = (message, mode) => {
    status.textContent = message;
    card.dataset.state = mode || "idle";
  };

  const stopPlayback = () => {
    state.playing.forEach((node) => {
      try { node.stop(); } catch (error) {}
    });
    state.playing.clear();
    state.playAt = state.ctx ? state.ctx.currentTime : 0;
  };

  const closeMic = () => {
    // Invalidate any permission request that is still pending.
    state.micRequestId = (state.micRequestId || 0) + 1;
    if (state.processor) {
      try { state.processor.disconnect(); } catch (error) {}
      state.processor.onaudioprocess = null;
      state.processor = null;
    }
    if (state.source) {
      try { state.source.disconnect(); } catch (error) {}
      state.source = null;
    }
    if (state.stream) {
      state.stream.getTracks().forEach((track) => track.stop());
      state.stream = null;
    }
  };

  const closeAll = (message, mode) => {
    state.closed = true;
    state.connected = false;
    state.starting = false;

    if (state.connectTimer) {
      clearTimeout(state.connectTimer);
      state.connectTimer = null;
    }

    closeMic();
    stopPlayback();

    const socket = state.ws;
    state.ws = null;
    if (socket && socket.readyState < WebSocket.CLOSING) {
      try { socket.close(1000, "Voice session ended"); } catch (error) {}
    }

    if (state.ctx) {
      try { state.ctx.close(); } catch (error) {}
      state.ctx = null;
    }

    state.muted = false;
    muteBtn.disabled = true;
    endBtn.disabled = true;
    startBtn.disabled = false;
    startBtn.querySelector("span").textContent = "Start talking";
    muteBtn.querySelector("small").textContent = "Mute";
    setStatus(message || "Voice session ended", mode || "idle");
  };

  const floatToPcm16 = (input, fromRate, toRate) => {
    const ratio = fromRate / toRate;
    const length = Math.floor(input.length / ratio);
    const pcm = new Int16Array(length);

    for (let i = 0; i < length; i++) {
      const first = Math.floor(i * ratio);
      const last = Math.min(Math.floor((i + 1) * ratio), input.length);
      let sum = 0;
      let count = 0;

      for (let j = first; j < last; j++) {
        sum += input[j];
        count++;
      }

      let sample = count ? sum / count : 0;
      sample = Math.max(-1, Math.min(1, sample));
      pcm[i] = sample < 0 ? sample * 32768 : sample * 32767;
    }
    return pcm;
  };

  const pcmToBase64 = (pcm) => {
    const bytes = new Uint8Array(pcm.buffer);
    let binary = "";
    const step = 0x8000;

    for (let i = 0; i < bytes.length; i += step) {
      binary += String.fromCharCode.apply(
        null,
        bytes.subarray(i, Math.min(i + step, bytes.length))
      );
    }
    return btoa(binary);
  };

  const playPcm = (base64) => {
    if (!state.ctx) return;

    const binary = atob(base64);
    const samples = new Int16Array(Math.floor(binary.length / 2));

    for (let i = 0; i < samples.length; i++) {
      samples[i] =
        (binary.charCodeAt(i * 2) & 255) |
        (binary.charCodeAt(i * 2 + 1) << 8);
    }

    const buffer = state.ctx.createBuffer(1, samples.length, 24000);
    const channel = buffer.getChannelData(0);

    for (let i = 0; i < samples.length; i++) {
      channel[i] = samples[i] / 32768;
    }

    const node = state.ctx.createBufferSource();
    node.buffer = buffer;
    node.connect(state.ctx.destination);

    const start = Math.max(state.ctx.currentTime + 0.025, state.playAt);
    state.playAt = start + buffer.duration;
    state.playing.add(node);
    node.onended = () => state.playing.delete(node);
    node.start(start);
    card.dataset.state = "speaking";
  };

  // Call this directly from the user's click, before opening the socket.
  // This lets iOS/Safari request mic permission and unlock AudioContext early.
  const startMicrophone = async () => {
    const requestId = (state.micRequestId || 0) + 1;
    state.micRequestId = requestId;

    if (!state.ctx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) throw new Error("This browser does not support audio.");
      state.ctx = new AudioContextClass();
    }

    if (state.stream && state.source && state.processor) {
      await state.ctx.resume();
      return;
    }

    // Request the mic synchronously from the Start/Unmute click, before the
    // first await, so iOS Safari can show its permission prompt reliably.
    const streamPromise = navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
    const resumePromise = state.ctx.resume();
    const [stream] = await Promise.all([streamPromise, resumePromise]);

    // A timeout, mute, or End action may have happened while permission was open.
    if (state.closed || state.micRequestId !== requestId) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    state.stream = stream;
    state.source = state.ctx.createMediaStreamSource(state.stream);
    // 2048 frames at 48 kHz is about 43 ms per packet, reducing input latency.
    state.processor = state.ctx.createScriptProcessor(2048, 1, 1);

    state.processor.onaudioprocess = (event) => {
      event.outputBuffer.getChannelData(0).fill(0);

      if (
        !state.connected ||
        state.muted ||
        !state.ws ||
        state.ws.readyState !== WebSocket.OPEN
      ) return;

      const inputSamples = event.inputBuffer.getChannelData(0);
      let sumSquares = 0;
      for (let i = 0; i < inputSamples.length; i++) {
        sumSquares += inputSamples[i] * inputSamples[i];
      }
      state.lastMicRms = Math.sqrt(sumSquares / Math.max(1, inputSamples.length));

      const pcm = floatToPcm16(
        inputSamples,
        state.ctx.sampleRate,
        16000
      );
      if (!pcm.length) return;

      try {
        state.ws.send(JSON.stringify({
          realtimeInput: {
            audio: {
              mimeType: "audio/pcm;rate=16000",
              data: pcmToBase64(pcm)
            }
          }
        }));
        state.audioFramesSent = (state.audioFramesSent || 0) + 1;
        const now = Date.now();
        if (now - (state.lastMicStatusAt || 0) > 700) {
          state.lastMicStatusAt = now;
          setStatus(
            state.lastMicRms > 0.006
              ? "Microphone detected — listening"
              : "Microphone active — speak now",
            "listening"
          );
        }
      } catch (error) {
        closeAll("Audio could not be sent to Gemini: " + error.message, "error");
      }
    };

    state.source.connect(state.processor);
    state.processor.connect(state.ctx.destination);
  };

  const onMessage = (event) => {
    let message;
    try {
      message = JSON.parse(event.data);
    } catch (error) {
      return;
    }

    if (message.setupComplete) {
      if (state.connectTimer) {
        clearTimeout(state.connectTimer);
        state.connectTimer = null;
      }

      state.connected = true;
      state.starting = false;
      startBtn.disabled = true;
      endBtn.disabled = false;
      muteBtn.disabled = false;
      setStatus("Listening — speak naturally", "listening");
      return;
    }

    if (message.error) {
      const detail = message.error.message || "Gemini Live returned an error.";
      closeAll(detail, "error");
      return;
    }

    const server = message.serverContent || {};

    if (server.interrupted) {
      stopPlayback();
      setStatus("Listening — you can interrupt anytime", "listening");
    }

    if (server.interimInputTranscription && server.interimInputTranscription.text) {
      userEl.textContent =
        state.userText + server.interimInputTranscription.text;
    }
    if (server.inputTranscription && server.inputTranscription.text) {
      state.userText += server.inputTranscription.text;
      userEl.textContent = state.userText;
    }

    if (server.outputTranscription && server.outputTranscription.text) {
      state.assistantText += server.outputTranscription.text;
      assistantEl.textContent = state.assistantText;
    }

    const parts = (server.modelTurn && server.modelTurn.parts) || [];
    parts.forEach((part) => {
      if (
        part.inlineData &&
        part.inlineData.data &&
        String(part.inlineData.mimeType || "").includes("audio/pcm")
      ) {
        playPcm(part.inlineData.data);
      }
    });

    if (server.turnComplete) {
      const userText = state.userText.trim();
      const assistantText = state.assistantText.trim();

      if (userText || assistantText) {
        const id = Date.now().toString() + "-" +
          Math.random().toString(36).slice(2);
        setTriggerValue("turn", {
          id: id,
          user: userText,
          assistant: assistantText
        });
      }

      state.userText = "";
      state.assistantText = "";
      if (state.connected) setStatus("Listening — speak naturally", "listening");
    }
  };

  const connect = async () => {
    if (state.starting || state.connected) return;

    if (!data.token) {
      setStatus("Gemini token is missing. Reload this page and try again.", "error");
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Microphone access requires a supported browser and HTTPS.", "error");
      return;
    }

    state.starting = true;
    state.closed = false;
    state.token = data.token;
    startBtn.disabled = true;
    setStatus("Allow microphone access to start…", "thinking");

    // A permission prompt can remain pending indefinitely in some browsers.
    // Bound that wait and invalidate any late getUserMedia result.
    let microphoneTimer = null;
    try {
      const microphoneReady = startMicrophone();
      const permissionTimeout = new Promise((_, reject) => {
        microphoneTimer = setTimeout(() => {
          reject(new Error(
            "Microphone permission is still pending. Allow microphone access in your browser, then tap Start talking again."
          ));
        }, 15000);
      });
      await Promise.race([microphoneReady, permissionTimeout]);
    } catch (error) {
      closeAll(
        "Microphone setup failed: " + (error.message || "permission denied"),
        "error"
      );
      return;
    } finally {
      if (microphoneTimer) clearTimeout(microphoneTimer);
    }

    if (state.closed) return;
    setStatus("Opening Gemini Live…", "thinking");

    const url =
      "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token=" +
      encodeURIComponent(state.token);

    let socket;
    try {
      socket = new WebSocket(url);
    } catch (error) {
      closeAll("Could not open Gemini Live: " + error.message, "error");
      return;
    }

    state.ws = socket;
    let socketOpened = false;

    // First measure the WebSocket handshake separately from Gemini session setup.
    state.connectTimer = setTimeout(() => {
      if (state.starting && !state.connected && !socketOpened) {
        closeAll(
          "Could not open a WebSocket connection to Gemini within 15 seconds. This points to a network, browser, or authentication handshake problem.",
          "error"
        );
      }
    }, 15000);

    socket.onopen = () => {
      if (state.closed) {
        try { socket.close(); } catch (error) {}
        return;
      }

      socketOpened = true;
      if (state.connectTimer) clearTimeout(state.connectTimer);
      setStatus("Connected — configuring Gemini Live…", "thinking");

      // A separate timer now waits for Google's setupComplete acknowledgement.
      state.connectTimer = setTimeout(() => {
        if (state.starting && !state.connected) {
          closeAll(
            "The WebSocket opened, but Gemini did not confirm the session setup within 15 seconds. The server may be rejecting the model, token, or setup configuration.",
            "error"
          );
        }
      }, 15000);

      const setup = {
        model: "models/gemini-3.8-live",
        generationConfig: {
          responseModalities: ["AUDIO"],
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: { voiceName: "Puck" }
            }
          }
        },
        systemInstruction: {
          parts: [{
            text: String(
              data.systemInstruction ||
              "You are Merge AI, a warm, natural conversational assistant. Speak clearly and naturally in the language the user uses."
            )
          }]
        },
        inputAudioTranscription: {},
        outputAudioTranscription: {},
        realtimeInputConfig: {
          automaticActivityDetection: { disabled: false },
          activityHandling: "START_OF_ACTIVITY_INTERRUPTS"
        },
        sessionResumption: {}
      };

      try {
        socket.send(JSON.stringify({ setup: setup }));
      } catch (error) {
        closeAll("Gemini setup could not be sent: " + error.message, "error");
      }
    };

    socket.onmessage = onMessage;

    socket.onerror = () => {
      // Browsers intentionally hide detailed WebSocket errors. Keep the socket
      // alive briefly so onclose can report its close code and reason.
      if (!state.closed) {
        setStatus(
          "WebSocket error — waiting for Gemini connection details…",
          "error"
        );
      }
    };

    socket.onclose = (event) => {
      if (state.connectTimer) {
        clearTimeout(state.connectTimer);
        state.connectTimer = null;
      }

      const wasClosed = state.closed;
      state.ws = null;
      state.connected = false;
      state.starting = false;
      closeMic();
      stopPlayback();

      if (state.ctx) {
        try { state.ctx.close(); } catch (error) {}
        state.ctx = null;
      }

      state.muted = false;
      startBtn.disabled = false;
      endBtn.disabled = true;
      muteBtn.disabled = true;
      startBtn.querySelector("span").textContent = "Start talking";
      muteBtn.querySelector("small").textContent = "Mute";

      if (!wasClosed) {
        state.closed = true;
        let reason = event.reason ||
          ("WebSocket closed with code " + event.code + ".");
        if (event.code === 1006) {
          reason += " Code 1006 means the connection ended abnormally before a normal close; the browser cannot expose the server's private handshake detail.";
        } else if (event.code === 1008) {
          reason += " Code 1008 usually indicates an authentication, policy, or setup rejection.";
        }
        setStatus(reason + " Tap Start talking to retry.", "error");
      }
    };
  };

  startBtn.onclick = () => connect();

  muteBtn.onclick = async () => {
    if (!state.connected) return;

    state.muted = !state.muted;

    if (state.muted) {
      // Tell Gemini the audio stream ended so server-side voice detection
      // can finalize the current utterance before the mic track is stopped.
      if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        try {
          state.ws.send(JSON.stringify({
            realtimeInput: { audioStreamEnd: true }
          }));
        } catch (error) {}
      }
      closeMic();
      muteBtn.querySelector("small").textContent = "Unmute";
      muteBtn.setAttribute("aria-pressed", "true");
      setStatus("Microphone muted", "idle");
    } else {
      try {
        await startMicrophone();
        muteBtn.querySelector("small").textContent = "Mute";
        muteBtn.setAttribute("aria-pressed", "false");
        setStatus("Listening — speak naturally", "listening");
      } catch (error) {
        closeAll(
          "Could not restart the microphone: " + error.message,
          "error"
        );
      }
    }
  };

  endBtn.onclick = () => closeAll("Voice session ended", "idle");

  exitBtn.onclick = () => {
    closeAll("Voice session ended", "idle");
    setTriggerValue("exit", { id: Date.now().toString() });
  };

  if (state.connected) {
    startBtn.disabled = true;
    endBtn.disabled = false;
    muteBtn.disabled = false;
    setStatus("Connected — speak naturally", "listening");
  } else if (!state.starting) {
    startBtn.disabled = false;
  }
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
