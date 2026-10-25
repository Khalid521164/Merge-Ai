
"""Merge AI - Web App with Live Voice Conversation."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

# PAGE SETUP
ICON_FILE = Path(__file__).parent / "merge_ai_favicon.png"
ICON = str(ICON_FILE) if ICON_FILE.is_file() else "🟢"
AVATAR = ICON if ICON_FILE.is_file() else "🤖"

st.set_page_config(
    page_title="Merge AI | Think Together",
    page_icon=ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from merge_ai import MergeAI, default_providers, safe_source_url
from cloud_history import CloudHistory, CloudHistoryError
from voice_chat import voice_chat

MAX_CHATS = 20
MAX_PER_HOUR = 20

# DESIGN
st.markdown("""
<style>
:root {
  --cream:#faf8f4;
  --green:#326957;
  --forest:#193e35;
  --line:#dfebe1;
  --mint:#f1f7f2;
  --muted:#708178;
}
html,body,.stApp,[data-testid="stAppViewContainer"] {
  background:var(--cream)!important;
  color:var(--forest)!important;
  color-scheme:light!important;
  font-family:system-ui,sans-serif!important;
}
[data-testid="stMainBlockContainer"] {
  max-width:950px!important;
  padding:1rem clamp(.6rem,3vw,1.6rem)!important;
}
[data-testid="stHeader"] {
  background:transparent!important;
}
[data-testid="stToolbar"],#MainMenu,
[data-testid="stDecoration"],footer {
  display:none!important;
}
.ma-brand {
  display:flex;
  align-items:center;
  gap:12px;
  padding:8px 0;
}
.ma-logo {
  display:grid;
  place-items:center;
  background:var(--green);
  color:white;
  width:48px;
  height:48px;
  border-radius:14px;
  font-size:26px;
  font-weight:850;
}
.ma-title {
  font-size:27px;
  font-weight:800;
  color:var(--forest);
  letter-spacing:-1px;
}
.ma-sub {
  font-size:10px;
  color:var(--muted);
  letter-spacing:1px;
}
.ma-line {
  height:1px;
  background:var(--line);
  margin:10px 0;
}
.stButton>button,
[data-testid="stPopover"] button {
  background:white!important;
  color:var(--forest)!important;
  border:1px solid var(--line)!important;
  border-radius:12px!important;
  min-height:41px!important;
}
.stButton>button:hover,
[data-testid="stPopover"] button:hover {
  border-color:#9fbbab!important;
  background:var(--mint)!important;
}
.st-key-ma_toolbar [data-testid="stHorizontalBlock"] {
  flex-wrap:nowrap!important;
  gap:.4rem!important;
}
.st-key-ma_toolbar [data-testid="column"] {
  min-width:0!important;
  flex:1 1 0!important;
  width:0!important;
}
.st-key-ma_conversation {
  background:white!important;
  border:1px solid var(--line)!important;
  border-radius:20px!important;
  box-shadow:0 8px 25px #173c3510;
}
[data-testid="stChatMessage"] {
  background:white!important;
  border:1px solid var(--line)!important;
  border-radius:15px!important;
  padding:12px!important;
  margin-bottom:8px!important;
}
[data-testid="stChatMessageContent"] {
  min-width:0;
  overflow-wrap:anywhere;
}
.ma-welcome {
  text-align:center;
  padding:85px 10px 65px;
  color:var(--forest);
}
.ma-spark {
  display:grid;
  place-items:center;
  width:56px;
  height:56px;
  margin:0 auto 20px;
  border-radius:18px;
  background:var(--mint);
  color:var(--green);
  font-size:29px;
}
.ma-welcome h2 {
  font-size:clamp(23px,4vw,30px);
}
.ma-welcome p {
  color:var(--muted);
  font-size:13px;
  line-height:1.7;
}
.ma-foot {
  text-align:center;
  color:var(--muted);
  font-size:11px;
  margin-top:14px;
}
[data-testid="stChatInput"] {
  border-radius:15px!important;
  border:1px solid #cbded0!important;
  background:white!important;
}
@media(max-width:650px) {
  [data-testid="stMainBlockContainer"] {
    padding:.8rem .55rem!important;
  }
  .ma-title {font-size:22px;}
  .ma-logo {width:42px;height:42px;}
  .ma-sub {font-size:8px;}
  .ma-welcome {padding:50px 8px 40px;}
  .st-key-ma_toolbar button {
    font-size:11px!important;
    padding-left:3px!important;
    padding-right:3px!important;
  }
}
</style>
""", unsafe_allow_html=True)


# SECRETS
def secret(name):
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


for name in (
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "TAVILY_API_KEY",
):
    value = secret(name)
    if value:
        os.environ[name] = value


# GOOGLE LOGIN
def user():
    try:
        return st.user if st.user.is_logged_in else None
    except (AttributeError, KeyError):
        return None


def owner():
    account = user()
    if account is None:
        return None
    subject = str(account.get("sub") or "")
    return "google:" + subject if subject else None


def auth_ready():
    try:
        config = st.secrets.get("auth", {})
        return all(config.get(k) for k in (
            "redirect_uri", "cookie_secret",
            "client_id", "client_secret",
            "server_metadata_url",
        ))
    except Exception:
        return False


def clear_session():
    for key in (
        "ma_chats_v2", "ma_active_v2",
        "ma_identity", "ma_cloud_loaded",
        "ma_cloud_error", "ma_request_times",
        "ma_voice_reply", "ma_voice_reply_id",
        "ma_voice_failed_id",
    ):
        st.session_state.pop(key, None)


def account_menu():
    account = user()
    with st.popover(
        "My account" if account else "Account",
        use_container_width=True,
    ):
        if account:
            st.markdown(
                "**Signed in as "
                + str(account.get("name") or "Merge AI user")
                + "**"
            )
            if account.get("email"):
                st.caption(str(account.get("email")))
            if cloud_client():
                st.caption("Cloud history configured.")
            else:
                st.warning("Cloud history is unavailable.")
            if st.button("Log out", key="logout", use_container_width=True):
                clear_session()
                st.logout()
        else:
            st.markdown("#### Welcome to Merge AI")
            if st.button(
                "Continue with Google",
                disabled=not auth_ready(),
                use_container_width=True,
            ):
                st.login()
            st.button(
                "Continue with Apple",
                disabled=True,
                use_container_width=True,
            )
            st.caption("Guests can chat without an account.")


# AI ENGINE
def make_engine():
    return MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
    )


def restore_context(engine, messages):
    turns = []
    pending = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = str(message.get("content", ""))
        if role == "user":
            pending = content
        elif role == "assistant" and pending is not None:
            turns.append((pending, content))
            pending = None
    engine._turns = turns[-12:]


# SUPABASE HISTORY
def cloud_client():
    identity = owner()
    if not identity:
        return None
    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_SECRET_KEY")
    if not url or not key:
        return None
    try:
        return CloudHistory(url, key, identity)
    except CloudHistoryError:
        return None


def new_chat():
    return {
        "id": uuid.uuid4().hex,
        "title": "New conversation",
        "messages": [],
        "updated": time.time(),
        "engine": make_engine(),
    }


def ensure_chats():
    chats = st.session_state.get("ma_chats_v2")
    if not isinstance(chats, dict) or not chats:
        record = new_chat()
        st.session_state.ma_chats_v2 = {record["id"]: record}
        st.session_state.ma_active_v2 = record["id"]
    elif st.session_state.get("ma_active_v2") not in chats:
        st.session_state.ma_active_v2 = next(iter(chats))


def load_history():
    if st.session_state.get("ma_cloud_loaded"):
        return
    st.session_state.ma_cloud_loaded = True
    client = cloud_client()
    if not client:
        if owner():
            st.session_state.ma_cloud_error = (
                "Cloud history isn't configured. "
                "Check your Supabase settings."
            )
        return
    try:
        rows = client.list_chats()
        restored = {}
        for row in rows[:MAX_CHATS]:
            chat_id = uuid.UUID(str(row["id"])).hex
            messages = row.get("messages", [])
            if not isinstance(messages, list):
                messages = []
            engine = make_engine()
            restore_context(engine, messages)
            restored[chat_id] = {
                "id": chat_id,
                "title": str(row.get("title") or "New conversation"),
                "messages": messages,
                "updated": time.time(),
                "engine": engine,
            }
        if restored:
            st.session_state.ma_chats_v2.update(restored)
            st.session_state.ma_active_v2 = next(iter(restored))
        st.session_state.ma_cloud_error = ""
    except (CloudHistoryError, KeyError, ValueError, TypeError):
        logging.exception("Cloud history load failed")
        st.session_state.ma_cloud_error = (
            "Cloud history could not be loaded. "
            "Chats may not be saved."
        )


def save_chat(record):
    client = cloud_client()
    if not owner():
        return
    if not client:
        st.session_state.ma_cloud_error = (
            "Cloud history is unavailable. "
            "This chat is temporary."
        )
        return
    try:
        client.upsert(record)
        st.session_state.ma_cloud_error = ""
    except CloudHistoryError:
        logging.exception("Cloud history save failed")
        st.session_state.ma_cloud_error = (
            "Could not save the chat to your account."
        )


def remove_cloud(chat_id):
    if not owner():
        return True
    client = cloud_client()
    if client is None:
        return False
    try:
        client.delete(chat_id)
        return True
    except CloudHistoryError:
        logging.exception("Cloud delete failed")
        return False


def initialize():
    identity = owner() or "guest"
    if st.session_state.get("ma_identity") != identity:
        clear_session()
        st.session_state.ma_identity = identity
    ensure_chats()
    st.session_state.setdefault("ma_cloud_error", "")
    st.session_state.setdefault("ma_web_on", True)
    st.session_state.setdefault("ma_answer_mode", "Fast")
    st.session_state.setdefault("ma_request_times", [])
    load_history()
    ensure_chats()


def current_chat():
    ensure_chats()
    return st.session_state.ma_chats_v2[
        st.session_state.ma_active_v2
    ]


def start_chat():
    if not current_chat()["messages"]:
        return True
    if len(st.session_state.ma_chats_v2) >= MAX_CHATS:
        return False
    record = new_chat()
    st.session_state.ma_chats_v2[record["id"]] = record
    st.session_state.ma_active_v2 = record["id"]
    return True


def add_message(role, content, sources=None):
    record = current_chat()
    message = {"role": role, "content": content}
    if sources and role == "assistant":
        message["sources"] = sources
    record["messages"].append(message)
    record["updated"] = time.time()
    if role == "user":
        count = sum(
            m.get("role") == "user"
            for m in record["messages"]
        )
        if count == 1:
            title = " ".join(content.split())
            record["title"] = title[:42]
    if role == "assistant":
        save_chat(record)


def backup():
    return json.dumps(
        {
            "app": "Merge AI",
            "exported": datetime.now(timezone.utc).isoformat(),
            "chats": [
                {
                    "title": c["title"],
                    "messages": c["messages"],
                }
                for c in st.session_state.ma_chats_v2.values()
                if c["messages"]
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


# HISTORY UI
def history_menu():
    with st.popover("History", use_container_width=True):
        st.markdown("#### Chat history")
        search = st.text_input(
            "Search",
            placeholder="Search previous chats...",
            key="history_search",
        ).strip().casefold()
        chats = sorted(
            st.session_state.ma_chats_v2.values(),
            key=lambda c: c["updated"],
            reverse=True,
        )
        if search:
            chats = [
                c for c in chats
                if search in c["title"].casefold()
                or any(
                    search in str(m.get("content", "")).casefold()
                    for m in c["messages"]
                )
            ]
        with st.container(height=220, border=False):
            if not chats:
                st.caption("No matching chats.")
            for c in chats:
                label = (
                    ("● " if c["id"] == st.session_state.ma_active_v2 else "")
                    + c["title"]
                )
                if st.button(
                    label,
                    key="open_" + c["id"],
                    use_container_width=True,
                ):
                    st.session_state.ma_active_v2 = c["id"]
                    st.rerun()

        with st.expander("Rename or delete"):
            record = current_chat()
            title = st.text_input(
                "Chat title",
                value=record["title"],
                key="rename_" + record["id"],
            )
            if st.button("Save name", key="save_name"):
                record["title"] = title.strip()[:60] or record["title"]
                save_chat(record)
                st.rerun()

            if st.button("Delete chat", key="delete_chat"):
                if remove_cloud(record["id"]):
                    chats_state = st.session_state.ma_chats_v2
                    chats_state.pop(record["id"], None)
                    ensure_chats()
                    st.session_state.ma_active_v2 = next(iter(chats_state))
                    st.rerun()
                else:
                    st.error("Could not delete this cloud chat.")

        st.download_button(
            "Download backup",
            data=backup(),
            file_name="merge_ai_history.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption(
            "Cloud sync for Google accounts when Supabase is available."
        )


# SOURCE LINKS
def show_sources(sources):
    if not isinstance(sources, list):
        return
    entries = []
    for source in sources[:8]:
        if not isinstance(source, dict):
            continue
        url = safe_source_url(source.get("url"))
        if url:
            label = str(
                source.get("title")
                or urlsplit(url).hostname
                or "Source"
            )[:90]
            entries.append((label, url))
    if entries:
        with st.expander(f"Research sources ({len(entries)})"):
            for label, url in entries:
                st.link_button(label, url)


# INITIALIZE
initialize()

if st.session_state.get("ma_cloud_error"):
    st.warning(st.session_state.ma_cloud_error)


# HEADER
with st.container():
    left, right = st.columns(
        [5, 2],
        gap="small",
        vertical_alignment="center",
    )
    with left:
        st.markdown("""
        <div class="ma-brand">
          <div class="ma-logo">M</div>
          <div>
            <div class="ma-title">Merge AI</div>
            <div class="ma-sub">
              THINK TOGETHER. ANSWER BETTER.
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with right:
        account_menu()

st.markdown('<div class="ma-line"></div>', unsafe_allow_html=True)


# TOOLBAR
with st.container(key="ma_toolbar"):
    history_col, new_col, settings_col = st.columns(
        [1, 1, 1], gap="small"
    )
    with history_col:
        history_menu()
    with new_col:
        if st.button(
            "＋ New chat",
            use_container_width=True,
            key="new_chat",
        ):
            if start_chat():
                st.rerun()
            else:
                st.warning("Delete an old chat first.")
    with settings_col:
        with st.popover("Settings", use_container_width=True):
            st.toggle("Tavily web research", key="ma_web_on")
            st.radio(
                "Answer mode",
                ("Fast", "Thorough"),
                key="ma_answer_mode",
            )
            st.caption("Gemini · OpenRouter · Groq")


# CHAT SCREEN
st.markdown(
    "**Conversation** · Gemini · OpenRouter · Groq · Tavily research"
)

with st.container(height=420, border=True, key="ma_conversation"):
    chat = current_chat()
    if not chat["messages"]:
        st.markdown("""
        <div class="ma-welcome">
          <div class="ma-spark">✦</div>
          <h2>What's on your mind?</h2>
          <p>
            Ask anything. Multiple AI models work together
            <br>to produce one thoughtful answer.
          </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for message in chat["messages"]:
            role = message.get("role", "assistant")
            if role not in ("user", "assistant"):
                continue
            with st.chat_message(
                role,
                avatar="👤" if role == "user" else AVATAR,
            ):
                st.markdown(str(message.get("content", "")))
                if role == "assistant":
                    show_sources(message.get("sources"))
    answer_space = st.empty()


# LIVE VOICE COMPONENT
# The voice_chat.py file supplies the dark
# popup, glowing orb, listening and TTS.

st.session_state.setdefault("ma_voice_reply", "")
st.session_state.setdefault("ma_voice_reply_id", "")
st.session_state.setdefault("ma_voice_failed_id", "")

voice_event = voice_chat(
    reply=st.session_state.ma_voice_reply,
    reply_id=st.session_state.ma_voice_reply_id,
    failed_id=st.session_state.ma_voice_failed_id,
)

spoken_question = voice_event.get("text") if voice_event else None


# MESSAGE INPUT
with st.container():
    typed_question = st.chat_input(
        "Ask Merge AI anything...",
        max_chars=1000,
        key="ma_question",
    )

st.markdown("""
<div class="ma-foot">
  One answer from multiple AI models ·
  Chat history syncs when cloud storage is connected
</div>
""", unsafe_allow_html=True)


# PROCESS THE QUESTION
question = typed_question or spoken_question

if question and question.strip():
    is_voice = bool(spoken_question and not typed_question)
    question = question.strip()

    now = time.monotonic()
    st.session_state.ma_request_times = [
        t for t in st.session_state.ma_request_times
        if now - t < 3600
    ]

    if len(st.session_state.ma_request_times) >= MAX_PER_HOUR:
        st.warning("Hourly question limit reached.")
        if is_voice:
            st.session_state.ma_voice_failed_id = uuid.uuid4().hex
            st.rerun()
    else:
        st.session_state.ma_request_times.append(now)

        with answer_space.container():
            with st.chat_message("user", avatar="👤"):
                st.markdown(question)

            with st.chat_message("assistant", avatar=AVATAR):
                with st.spinner("Researching and merging..."):
                    try:
                        engine = current_chat()["engine"]
                        ask_text = question

                        if is_voice and voice_event:
                            language = voice_event.get(
                                "language_name", "English"
                            )
                            ask_text += (
                                "\n\n[Voice preference: "
                                "Reply naturally in "
                                + language
                                + ".]"
                            )

                        answer = str(engine.ask(
                            ask_text,
                            fast=(
                                st.session_state.ma_answer_mode
                                == "Fast"
                            ),
                            web_search=st.session_state.ma_web_on,
                        ))

                        report = getattr(engine, "last_report", {})
                        sources = report.get("sources", [])

                    except Exception:
                        logging.exception("Merge AI failed")
                        if is_voice:
                            st.session_state.ma_voice_failed_id = (
                                uuid.uuid4().hex
                            )
                        st.error(
                            "Sorry, I couldn't complete "
                            "that answer. Please try again."
                        )
                    else:
                        st.markdown(answer)
                        show_sources(sources)

                        add_message("user", question)
                        add_message("assistant", answer, sources)

                        if is_voice:
                            st.session_state.ma_voice_reply = answer
                            st.session_state.ma_voice_reply_id = (
                                uuid.uuid4().hex
                            )

                        st.rerun()
