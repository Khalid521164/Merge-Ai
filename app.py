
"""Merge AI — ChatGPT-inspired Streamlit UI.
Expected siblings: merge_ai.py, voice_chat.py; optional elevenlabs_tts.py,
voice_trainer.py, cloud_history.py. Keep credentials in Streamlit Secrets.
"""
from __future__ import annotations

import base64
import html
import inspect
import json
import os
import re
import uuid
from datetime import datetime
from typing import Any

import streamlit as st

st.set_page_config(page_title="Merge AI", page_icon="🟢", layout="wide", initial_sidebar_state="expanded")

# -------- Credentials --------
def secret(key: str, default: str = "") -> str:
    try:
        value = st.secrets.get(key, default)
        return str(value) if value is not None else default
    except Exception:
        return os.environ.get(key, default)

for _key in (
    "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY",
    "GEMINI_MODEL", "GROQ_MODEL", "OPENROUTER_MODEL",
):
    if secret(_key):
        os.environ[_key] = secret(_key)

EL_KEY = secret("ELEVENLABS_API_KEY")
EL_VOICE = secret("ELEVENLABS_VOICE_ID")

# -------- Backend imports --------
try:
    from merge_ai import MergeAI, default_providers
    BACKEND_ERROR = ""
except Exception as exc:
    MergeAI = default_providers = None
    BACKEND_ERROR = f"merge_ai.py could not be loaded: {exc}"

try:
    from voice_chat import voice_chat
except Exception:
    voice_chat = None

try:
    from elevenlabs_tts import synthesize
except Exception:
    synthesize = None

try:
    from voice_trainer import (
        init_voice_trainer, trainer_panel, apply_pronunciations,
        parse_correction, save_pronunciation,
    )
    HAS_TRAINER = True
except Exception:
    HAS_TRAINER = False

try:
    from cloud_history import CloudHistory
except Exception:
    CloudHistory = None

# -------- State --------
def new_chat(title="New chat"):
    return {"id": str(uuid.uuid4()), "title": title, "messages": [], "created": datetime.now().isoformat()}

def init():
    defaults = {
        "chats": [], "chat_id": None, "show_search": False,
        "pending_voice_question": None,
        "ma_voice_reply": "", "ma_voice_reply_id": "",
        "ma_voice_failed_id": "", "ma_voice_audio_b64": "",
        "ma_voice_audio_error": "", "ma_voice_provider": "elevenlabs",
        "ma_audio_bytes": None, "ma_audio_for": "",
        "mode": "Fast", "web_enabled": True,
    }
    for name, value in defaults.items():
        if name not in st.session_state:
            st.session_state[name] = value
    if not st.session_state.chats:
        c = new_chat()
        st.session_state.chats = [c]
        st.session_state.chat_id = c["id"]
    if st.session_state.chat_id not in [c["id"] for c in st.session_state.chats]:
        st.session_state.chat_id = st.session_state.chats[0]["id"]

init()
if HAS_TRAINER:
    init_voice_trainer()


def current_chat():
    return next(c for c in st.session_state.chats if c["id"] == st.session_state.chat_id)


def create_chat():
    c = new_chat()
    st.session_state.chats.insert(0, c)
    st.session_state.chat_id = c["id"]
    st.session_state.ma_audio_bytes = None


def delete_chat(cid):
    st.session_state.chats = [c for c in st.session_state.chats if c["id"] != cid]
    if not st.session_state.chats:
        st.session_state.chats = [new_chat()]
    if st.session_state.chat_id == cid:
        st.session_state.chat_id = st.session_state.chats[0]["id"]

# -------- CSS --------
st.markdown("""
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility:hidden;}
.block-container {max-width:870px; padding-top:1.3rem; padding-bottom:7rem;}
[data-testid="stSidebar"] {background:#f7f8f7;border-right:1px solid #eceeed;}
[data-testid="stSidebar"] .block-container {padding-top:1.25rem;}
.stApp {background:#fff;color:#202522;}
.m-brand{display:flex;align-items:center;gap:11px;margin:1px 0 17px;}
.m-logo{width:35px;height:35px;display:grid;place-items:center;background:#126d4e;color:#fff;border-radius:12px;font-size:20px;font-weight:800;}
.m-brandname{font-size:18px;font-weight:750;letter-spacing:-.5px;}
.m-top{display:flex;justify-content:space-between;align-items:center;margin:0 0 22px;}
.m-heading{font-size:21px;font-weight:650;letter-spacing:-.7px;}
.m-sub{font-size:12px;color:#8e9891;}
.m-welcome{display:flex;justify-content:center;align-items:center;min-height:220px;flex-direction:column;gap:12px;text-align:center;}
.m-welcome-icon{border-radius:18px;background:#126d4e;color:white;width:55px;height:55px;display:grid;place-items:center;font-weight:bold;font-size:29px;}
.m-welcome-label{font-size:28px;font-weight:650;letter-spacing:-1px;}
.m-welcome-help{color:#89928c;font-size:13px;}
.m-user{display:flex;justify-content:flex-end;margin:16px 0 10px;}
.m-user-bubble{background:#f1f3f2;border-radius:20px;padding:11px 16px;max-width:83%;white-space:pre-wrap;overflow-wrap:anywhere;}
.m-assistant-tag{color:#177658;font-weight:700;font-size:13px;margin:18px 0 5px;}
.m-source{font-size:12px;margin-top:9px;color:#777;}
.m-footer{font-size:11px;color:#969e99;text-align:center;padding-top:17px;}
[data-testid="stChatInput"]{max-width:870px;margin:auto;}
[data-testid="stChatInput"] textarea{border-radius:20px !important;}
.stButton>button{border-radius:12px !important;}
[data-testid="stSidebar"] .stButton>button{width:100%;text-align:left;justify-content:flex-start;}
[data-testid="stSidebar"] hr{margin:12px 0;}
@media(prefers-color-scheme:dark){
 [data-testid="stSidebar"]{background:#181b1a;border-right-color:#333;}
 .stApp{background:#161918;color:#ebeeec;}
 .m-user-bubble{background:#303633;color:#f2f3f2;}
}
@media(max-width:720px){.block-container{padding:1rem .65rem 7rem;}.m-welcome-label{font-size:23px;}.m-user-bubble{max-width:95%;}}
</style>
""", unsafe_allow_html=True)

# -------- Optional Google sign in --------
def get_user():
    try:
        if st.user.is_logged_in:
            return dict(st.user)
    except Exception:
        pass
    return None

# -------- Sidebar --------
with st.sidebar:
    st.markdown('<div class="m-brand"><div class="m-logo">M</div><div class="m-brandname">Merge AI</div></div>', unsafe_allow_html=True)
    if st.button("✏️  New chat", use_container_width=True):
        create_chat()
        st.rerun()
    if st.button("🔎  Search chats", use_container_width=True):
        st.session_state.show_search = not st.session_state.show_search
    keyword = st.text_input("Search", placeholder="Search your conversations", label_visibility="collapsed") if st.session_state.show_search else ""
    st.divider()
    st.caption("YOUR CHATS")
    for c in st.session_state.chats:
        if keyword and keyword.casefold() not in (c["title"] + " " + " ".join(m["content"] for m in c["messages"])).casefold():
            continue
        label = ("🟢  " if c["id"] == st.session_state.chat_id else "💬  ") + c["title"][:30]
        if st.button(label, key=f"chat_{c['id']}", use_container_width=True):
            st.session_state.chat_id = c["id"]
            st.rerun()
    with st.expander("Manage current chat"):
        new_title = st.text_input("Rename chat", value=current_chat()["title"], key=f"rename_{st.session_state.chat_id}")
        if st.button("Save title"):
            current_chat()["title"] = new_title.strip() or "New chat"
            st.rerun()
        if st.button("Delete this chat"):
            delete_chat(st.session_state.chat_id)
            st.rerun()
        st.download_button("Export all chats", data=json.dumps(st.session_state.chats, ensure_ascii=False, indent=2), file_name="merge_ai_chats.json", mime="application/json")
    st.divider()
    st.session_state.mode = st.selectbox("Response speed", ["Fast", "Deep"], index=0 if st.session_state.mode == "Fast" else 1)
    st.session_state.web_enabled = st.toggle("🌐 Web search", value=st.session_state.web_enabled)
    if HAS_TRAINER:
        trainer_panel()
    person = get_user()
    if person:
        st.caption("Signed in: " + (person.get("email") or person.get("name") or "Account"))
        if st.button("Sign out"):
            st.logout()
    else:
        st.caption("Chat history is saved for this browser session.")
        if st.button("Sign in with Google", help="Requires Streamlit OAuth configuration"):
            try:
                st.login("google")
            except Exception as exc:
                st.warning(f"Google login not configured: {exc}")

# -------- AI --------
@st.cache_resource(show_spinner=False)
def get_engine():
    if MergeAI is None:
        raise RuntimeError(BACKEND_ERROR)
    providers = default_providers()
    return MergeAI(providers=providers, tavily_api_key=secret("TAVILY_API_KEY"))


def unpack_answer(result: Any) -> tuple[str, list]:
    if isinstance(result, str):
        return result, []
    if isinstance(result, dict):
        answer = next((result.get(k) for k in ("answer", "final_answer", "final", "response", "text") if result.get(k)), None)
        sources = result.get("sources") or []
    else:
        answer = next((getattr(result, k, None) for k in ("answer", "final_answer", "final", "response", "text") if getattr(result, k, None)), None)
        sources = getattr(result, "sources", []) or []
    return str(answer or result), sources if isinstance(sources, list) else []


def get_answer(question):
    eng = get_engine()
    try:
        result = eng.ask(question, fast=(st.session_state.mode == "Fast"), web_search=st.session_state.web_enabled)
    except TypeError as exc:
        # Only support an older backend lacking web_search; do not mask other failures.
        if "web_search" not in str(exc):
            raise
        result = eng.ask(question, fast=(st.session_state.mode == "Fast"))
    return unpack_answer(result)


def correction_command(text):
    if not HAS_TRAINER:
        return None
    return parse_correction(text)

# -------- ElevenLabs --------
def mp3_for(text: str) -> bytes | None:
    st.session_state.ma_voice_audio_error = ""
    if not (EL_KEY and EL_VOICE and synthesize):
        st.session_state.ma_voice_audio_error = "ElevenLabs isn't configured. Add ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, and elevenlabs_tts.py."
        return None
    try:
        speak_text = apply_pronunciations(text) if HAS_TRAINER else text
        settings = st.session_state.get("vt_settings", {})
        # Compatible with the old synthesize(text, api_key, voice_id) signature.
        params = inspect.signature(synthesize).parameters
        kwargs = {}
        if "speed" in params:
            kwargs["speed"] = float(settings.get("speed", 0.95))
        if "stability" in params:
            kwargs["stability"] = float(settings.get("stability", 0.55))
        audio = synthesize(speak_text, EL_KEY, EL_VOICE, **kwargs)
        if not isinstance(audio, bytes) or not audio:
            raise RuntimeError("No MP3 audio returned")
        return audio
    except Exception as exc:
        st.session_state.ma_voice_audio_error = str(exc)
        return None


def display_sources(sources):
    urls = []
    for item in sources[:6]:
        value = item if isinstance(item, str) else (item.get("url") or item.get("link") or "" if isinstance(item, dict) else "")
        if isinstance(value, str) and value.startswith(("https://", "http://")) and value not in urls:
            urls.append(value)
    if urls:
        with st.expander(f"Sources ({len(urls)})"):
            for url in urls:
                st.markdown(f"- {url}")

# -------- Main --------
st.markdown('<div class="m-top"><div class="m-heading">Merge AI <span style="color:#939a96;font-size:15px">⌄</span></div><div class="m-sub">Gemini + Groq + OpenRouter</div></div>', unsafe_allow_html=True)
chat = current_chat()
if not chat["messages"]:
    st.markdown('<div class="m-welcome"><div class="m-welcome-icon">M</div><div class="m-welcome-label">What can I help with?</div><div class="m-welcome-help">Ask a question, search the web, or talk with Merge AI.</div></div>', unsafe_allow_html=True)

for index, msg in enumerate(chat["messages"]):
    if msg["role"] == "user":
        st.markdown('<div class="m-user"><div class="m-user-bubble">' + html.escape(msg["content"]) + '</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="m-assistant-tag">✦ Merge AI</div>', unsafe_allow_html=True)
        st.markdown(msg["content"])
        display_sources(msg.get("sources", []))
        tools = st.columns([1, 1, 7])
        with tools[0]:
            if st.button("🔊", key=f"speak_{chat['id']}_{index}", help="Speak this answer"):
                st.session_state.ma_audio_bytes = mp3_for(msg["content"])
                st.session_state.ma_audio_for = f"{chat['id']}_{index}"
        with tools[1]:
            if st.button("📋", key=f"copy_{chat['id']}_{index}", help="Show copyable text"):
                st.code(msg["content"], language=None)
        if st.session_state.ma_audio_for == f"{chat['id']}_{index}" and st.session_state.ma_audio_bytes:
            st.audio(st.session_state.ma_audio_bytes, format="audio/mp3")
        if st.session_state.ma_audio_for == f"{chat['id']}_{index}" and st.session_state.ma_voice_audio_error:
            st.caption(st.session_state.ma_voice_audio_error)

# Always render the voice component (Streamlit component state needs a stable position).
# Existing voice_chat.py is expected to display the glowing-orb voice control.
st.caption("🎙️ LIVE VOICE — tap the microphone/orb control below to start a conversation")
voice_event = None
if voice_chat:
    try:
        voice_event = voice_chat(
            reply=st.session_state.ma_voice_reply,
            reply_id=st.session_state.ma_voice_reply_id,
            failed_id=st.session_state.ma_voice_failed_id,
            audio_b64=st.session_state.ma_voice_audio_b64,
            elevenlabs_available=bool(EL_KEY and EL_VOICE and synthesize),
        )
    except Exception as exc:
        st.caption(f"Live voice couldn't start: {exc}")
else:
    st.info("🎙️ To enable the glowing Live Voice popup, keep your existing voice_chat.py in this folder.")

spoken_question = None
is_voice = False
provider = "browser"
if isinstance(voice_event, dict):
    spoken_question = (voice_event.get("text") or "").strip()
    provider = voice_event.get("voice_provider") or "browser"
    is_voice = bool(spoken_question)

question = st.chat_input("Ask Merge AI anything…")
if not question and is_voice:
    # Avoid duplicate event reprocessing on later Streamlit reruns.
    fingerprint = str(voice_event.get("request_id") or voice_event.get("id") or spoken_question)
    if st.session_state.get("last_voice_fingerprint") != fingerprint:
        st.session_state.last_voice_fingerprint = fingerprint
        question = spoken_question
if question:
    question = question.strip()
    if question:
        command = correction_command(question)
        if command:
            a, b = command
            if save_pronunciation(a, b):
                st.toast(f"Saved pronunciation: {a} → {b}")
            else:
                st.warning("Could not save the pronunciation correction.")
            st.stop()

        chat = current_chat()
        chat["messages"].append({"role": "user", "content": question})
        if chat["title"] == "New chat":
            chat["title"] = (question[:43] + "…") if len(question) > 43 else question
        with st.spinner("Searching, consulting models and merging answers…"):
            try:
                response, sources = get_answer(question)
            except Exception as exc:
                response = f"I couldn't get a response from the AI providers. Details: {exc}"
                sources = []
        chat["messages"].append({"role": "assistant", "content": response, "sources": sources})

        if is_voice:
            st.session_state.ma_voice_reply = response
            st.session_state.ma_voice_reply_id = str(uuid.uuid4())
            st.session_state.ma_voice_audio_b64 = ""
            st.session_state.ma_voice_failed_id = ""
            st.session_state.ma_voice_provider = provider
            if provider == "elevenlabs":
                audio = mp3_for(response)
                if audio:
                    st.session_state.ma_voice_audio_b64 = base64.b64encode(audio).decode("ascii")
                else:
                    st.session_state.ma_voice_failed_id = st.session_state.ma_voice_reply_id
        st.rerun()

st.markdown('<div class="m-footer">Merge AI can make mistakes. Check important information.</div>', unsafe_allow_html=True)
