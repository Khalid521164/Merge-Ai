
"""Merge AI - Streamlit Web App with ElevenLabs Live Voice."""

from __future__ import annotations

import os
import json
import time
import uuid
import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

# ==================================================
# PAGE CONFIGURATION
# ==================================================

ICON_FILE = Path(__file__).parent / "merge_ai_favicon.png"
ICON = str(ICON_FILE) if ICON_FILE.exists() else "🟢"
AVATAR = ICON if ICON_FILE.exists() else "🤖"

st.set_page_config(
    page_title="Merge AI | Think Together",
    page_icon=ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

from merge_ai import MergeAI, default_providers, safe_source_url
from cloud_history import CloudHistory, CloudHistoryError
from voice_chat import voice_chat
from elevenlabs_tts import synthesize, VoiceGenerationError

MAX_CHATS = 20
MAX_PER_HOUR = 20
MAX_INPUT = 1000

# ==================================================
# PROFESSIONAL UI
# ==================================================

st.markdown("""
<style>
:root {
    --cream:#faf8f4;
    --green:#326957;
    --dark:#193e35;
    --mint:#f1f7f2;
    --line:#dfebe1;
    --muted:#708178;
}

html,body,.stApp,
[data-testid="stAppViewContainer"] {
    background:var(--cream)!important;
    color:var(--dark)!important;
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

[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,footer {
    display:none!important;
}

.ma-brand {
    display:flex;
    align-items:center;
    gap:12px;
    padding:8px 0;
}

.ma-logo {
    width:48px;
    height:48px;
    border-radius:14px;
    background:var(--green);
    color:white;
    display:grid;
    place-items:center;
    font-size:26px;
    font-weight:850;
}

.ma-title {
    color:var(--dark);
    font-size:27px;
    font-weight:800;
    letter-spacing:-1px;
}

.ma-sub {
    color:var(--muted);
    font-size:10px;
    letter-spacing:1px;
}

.ma-line {
    height:1px;
    background:var(--line);
    margin:10px 0 15px;
}

.stButton>button,
[data-testid="stPopover"] button {
    background:white!important;
    color:var(--dark)!important;
    border:1px solid var(--line)!important;
    border-radius:12px!important;
    min-height:41px!important;
    font-weight:600!important;
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
    padding:80px 10px 60px;
}

.ma-spark {
    width:56px;
    height:56px;
    display:grid;
    place-items:center;
    margin:0 auto 20px;
    border-radius:18px;
    background:var(--mint);
    color:var(--green);
    font-size:30px;
}

.ma-welcome h2 {
    color:var(--dark);
    font-size:clamp(22px,4vw,30px);
}

.ma-welcome p {
    color:var(--muted);
    font-size:13px;
    line-height:1.7;
}

[data-testid="stChatInput"] {
    border-radius:15px!important;
    border:1px solid #cbded0!important;
    background:white!important;
}

.ma-foot {
    text-align:center;
    color:var(--muted);
    font-size:11px;
    margin-top:12px;
}

@media(max-width:650px) {
    [data-testid="stMainBlockContainer"] {
        padding:.8rem .55rem!important;
    }
    .ma-title {font-size:22px;}
    .ma-logo {width:42px;height:42px;}
    .ma-sub {font-size:8px;}
    .ma-welcome {padding:45px 8px 35px;}
    .st-key-ma_toolbar button {
        font-size:11px!important;
        padding-left:3px!important;
        padding-right:3px!important;
    }
    [data-testid="stChatMessage"] {
        padding:9px!important;
    }
}
</style>
""", unsafe_allow_html=True)

# ==================================================
# SECURE API KEY LOADING
# ==================================================

def secret(name):
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


for name in (
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
):
    value = secret(name)
    if value:
        os.environ[name] = value

# ==================================================
# GOOGLE LOGIN
# ==================================================

def current_user():
    try:
        return st.user if st.user.is_logged_in else None
    except (AttributeError, KeyError):
        return None


def owner_id():
    user = current_user()
    if user is None:
        return None

    subject = str(user.get("sub") or "").strip()
    return "google:" + subject if subject else None


def google_ready():
    try:
        config = st.secrets.get("auth", {})
        return all(config.get(k) for k in (
            "redirect_uri",
            "cookie_secret",
            "client_id",
            "client_secret",
            "server_metadata_url",
        ))
    except Exception:
        return False


def reset_session():
    for key in (
        "ma_chats_v2",
        "ma_active_v2",
        "ma_identity",
        "ma_cloud_loaded",
        "ma_cloud_error",
        "ma_request_times",
        "ma_voice_reply",
        "ma_voice_reply_id",
        "ma_voice_failed_id",
        "ma_voice_audio_b64",
    ):
        st.session_state.pop(key, None)


def account_menu():
    user = current_user()

    with st.popover(
        "My account" if user else "Account",
        use_container_width=True,
    ):
        if user:
            st.markdown(
                "**Signed in as "
                + str(user.get("name") or "Merge AI user")
                + "**"
            )

            if user.get("email"):
                st.caption(str(user.get("email")))

            st.caption(
                "Your chats sync when Supabase is connected."
            )

            if st.button(
                "Log out",
                key="ma_logout",
                use_container_width=True,
            ):
                reset_session()
                st.logout()

        else:
            st.markdown("#### Welcome to Merge AI")

            if st.button(
                "Continue with Google",
                disabled=not google_ready(),
                key="ma_google_login",
                use_container_width=True,
            ):
                st.login()

            st.button(
                "Continue with Apple",
                key="ma_apple_login",
                disabled=True,
                use_container_width=True,
            )

            st.caption(
                "Guest access is available without login."
            )

# ==================================================
# MERGE AI ENGINE
# ==================================================

def make_engine():
    return MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get(
            "TAVILY_API_KEY", ""
        ),
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

# ==================================================
# SUPABASE DATABASE
# ==================================================

def cloud_client():
    owner = owner_id()

    if not owner:
        return None

    url = secret("SUPABASE_URL")
    key = secret("SUPABASE_SECRET_KEY")

    if not url or not key:
        return None

    try:
        return CloudHistory(url, key, owner)
    except CloudHistoryError:
        logging.warning("Cloud history configuration failed")
        return None


def save_cloud(chat):
    if not owner_id():
        return True

    client = cloud_client()

    if client is None:
        st.session_state.ma_cloud_error = (
            "Cloud history is unavailable. "
            "This chat was not saved to your account."
        )
        return False

    try:
        client.upsert(chat)
        st.session_state.ma_cloud_error = ""
        return True

    except CloudHistoryError:
        logging.exception("Cloud history save failed")
        st.session_state.ma_cloud_error = (
            "Cloud history could not save this conversation."
        )
        return False


def load_cloud():
    if st.session_state.get("ma_cloud_loaded"):
        return

    st.session_state.ma_cloud_loaded = True

    client = cloud_client()

    if client is None:
        if owner_id():
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
                "title": str(
                    row.get("title") or "New conversation"
                )[:60],
                "messages": messages,
                "updated": time.time(),
                "engine": engine,
            }

        if restored:
            st.session_state.ma_chats_v2.update(restored)
            st.session_state.ma_active_v2 = next(
                iter(restored)
            )

        st.session_state.ma_cloud_error = ""

    except (CloudHistoryError, ValueError, KeyError, TypeError):
        logging.exception("Cloud history load failed")
        st.session_state.ma_cloud_error = (
            "Cloud history could not be loaded."
        )


def delete_cloud(chat_id):
    if not owner_id():
        return True

    client = cloud_client()

    if client is None:
        return False

    try:
        client.delete(chat_id)
        return True

    except CloudHistoryError:
        logging.exception("Cloud history delete failed")
        return False

# ==================================================
# CONVERSATION HISTORY
# ==================================================

def make_chat():
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
        chat = make_chat()
        st.session_state.ma_chats_v2 = {
            chat["id"]: chat
        }
        st.session_state.ma_active_v2 = chat["id"]

    elif st.session_state.get("ma_active_v2") not in chats:
        st.session_state.ma_active_v2 = next(
            iter(chats)
        )


def initialize():
    identity = owner_id() or "guest"

    if st.session_state.get("ma_identity") != identity:
        reset_session()
        st.session_state.ma_identity = identity

    ensure_chats()

    st.session_state.setdefault("ma_web_on", True)
    st.session_state.setdefault("ma_answer_mode", "Fast")
    st.session_state.setdefault("ma_cloud_error", "")
    st.session_state.setdefault("ma_request_times", [])

    load_cloud()
    ensure_chats()


def active_chat():
    ensure_chats()
    return st.session_state.ma_chats_v2[
        st.session_state.ma_active_v2
    ]


def create_chat():
    if not active_chat()["messages"]:
        return True

    if len(st.session_state.ma_chats_v2) >= MAX_CHATS:
        return False

    chat = make_chat()
    st.session_state.ma_chats_v2[chat["id"]] = chat
    st.session_state.ma_active_v2 = chat["id"]
    return True


def append_message(role, content, sources=None):
    chat = active_chat()

    item = {
        "role": role,
        "content": content,
    }

    if role == "assistant" and sources:
        item["sources"] = sources

    chat["messages"].append(item)
    chat["updated"] = time.time()

    if role == "user":
        count = sum(
            m.get("role") == "user"
            for m in chat["messages"]
        )

        if count == 1:
            text = " ".join(content.split())
            chat["title"] = text[:42]

    if role == "assistant":
        save_cloud(chat)


def remove_chat(chat_id):
    if not delete_cloud(chat_id):
        return False

    chats = st.session_state.ma_chats_v2
    chats.pop(chat_id, None)
    ensure_chats()

    if st.session_state.ma_active_v2 not in chats:
        st.session_state.ma_active_v2 = next(iter(chats))

    return True


def history_backup():
    return json.dumps(
        {
            "app": "Merge AI",
            "exported_at": datetime.now(
                timezone.utc
            ).isoformat(),
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


def history_menu():
    with st.popover(
        "History",
        use_container_width=True,
    ):
        st.markdown("#### Chat history")

        search = st.text_input(
            "Search chats",
            placeholder="Search previous conversations...",
            key="ma_history_search",
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
                    search in str(
                        m.get("content", "")
                    ).casefold()
                    for m in c["messages"]
                )
            ]

        with st.container(height=230, border=False):
            if not chats:
                st.caption("No matching conversations.")

            for chat in chats:
                selected = (
                    chat["id"] ==
                    st.session_state.ma_active_v2
                )

                label = (
                    ("● " if selected else "")
                    + chat["title"]
                )

                if st.button(
                    label,
                    key="open_" + chat["id"],
                    use_container_width=True,
                ):
                    st.session_state.ma_active_v2 = chat["id"]
                    st.rerun()

        with st.expander("Rename or delete"):
            chat = active_chat()

            title = st.text_input(
                "Chat title",
                value=chat["title"],
                max_chars=60,
                key="rename_" + chat["id"],
            )

            if st.button(
                "Save name",
                key="save_" + chat["id"],
            ):
                chat["title"] = (
                    title.strip()[:60]
                    or chat["title"]
                )
                save_cloud(chat)
                st.rerun()

            if st.button(
                "Delete chat",
                key="delete_" + chat["id"],
            ):
                if remove_chat(chat["id"]):
                    st.rerun()
                else:
                    st.error(
                        "Could not delete this saved chat."
                    )

        st.download_button(
            "Download backup",
            data=history_backup(),
            file_name="merge_ai_history.json",
            mime="application/json",
            use_container_width=True,
        )

        if owner_id():
            st.caption(
                "Cloud sync when Supabase is available."
            )
        else:
            st.caption(
                "Guest history is temporary."
            )

# ==================================================
# RESEARCH SOURCES
# ==================================================

def show_sources(sources):
    if not isinstance(sources, list):
        return

    links = []

    for source in sources[:8]:
        if not isinstance(source, dict):
            continue

        url = safe_source_url(source.get("url"))

        if url:
            title = str(
                source.get("title")
                or urlsplit(url).hostname
                or "Source"
            )[:90]

            links.append((title, url))

    if links:
        with st.expander(
            f"Research sources ({len(links)})"
        ):
            for title, url in links:
                st.link_button(title, url)

# ==================================================
# INITIALIZATION
# ==================================================

initialize()

if st.session_state.ma_cloud_error:
    st.warning(st.session_state.ma_cloud_error)

# ==================================================
# WEBSITE HEADER
# ==================================================

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

st.markdown(
    '<div class="ma-line"></div>',
    unsafe_allow_html=True,
)

# ==================================================
# MAIN TOOLBAR
# ==================================================

with st.container(key="ma_toolbar"):
    history_col, new_col, settings_col = st.columns(
        [1, 1, 1],
        gap="small",
    )

    with history_col:
        history_menu()

    with new_col:
        if st.button(
            "＋ New chat",
            key="ma_new_chat",
            use_container_width=True,
        ):
            if create_chat():
                st.rerun()
            else:
                st.warning(
                    "Maximum chat limit reached."
                )

    with settings_col:
        with st.popover(
            "Settings",
            use_container_width=True,
        ):
            st.toggle(
                "Tavily web research",
                key="ma_web_on",
            )

            st.radio(
                "Answer mode",
                ("Fast", "Thorough"),
                key="ma_answer_mode",
            )

            st.caption(
                "Gemini · Groq · OpenRouter"
            )

# ==================================================
# CHAT DISPLAY
# ==================================================

st.markdown(
    "**Conversation** · Gemini · Groq · "
    "OpenRouter · Tavily research"
)

with st.container(
    height=420,
    border=True,
    key="ma_conversation",
):
    chat = active_chat()

    if not chat["messages"]:
        st.markdown("""
        <div class="ma-welcome">
            <div class="ma-spark">✦</div>
            <h2>What's on your mind?</h2>
            <p>
                Ask anything. Multiple AI models
                work together to produce one
                thoughtful answer.
            </p>
        </div>
        """, unsafe_allow_html=True)

    else:
        for message in chat["messages"]:
            role = message.get(
                "role", "assistant"
            )

            if role not in ("user", "assistant"):
                continue

            with st.chat_message(
                role,
                avatar=(
                    "👤" if role == "user"
                    else AVATAR
                ),
            ):
                st.markdown(
                    str(message.get("content", ""))
                )

                if role == "assistant":
                    show_sources(
                        message.get("sources")
                    )

    answer_space = st.empty()

# ==================================================
# LIVE CONVERSATION + ELEVENLABS
# ==================================================

st.session_state.setdefault(
    "ma_voice_reply", ""
)
st.session_state.setdefault(
    "ma_voice_reply_id", ""
)
st.session_state.setdefault(
    "ma_voice_failed_id", ""
)
st.session_state.setdefault(
    "ma_voice_audio_b64", ""
)

ELEVENLABS_KEY = secret("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = secret("ELEVENLABS_VOICE_ID")

ELEVENLABS_READY = bool(
    ELEVENLABS_KEY and ELEVENLABS_VOICE_ID
)

# This component displays the dark voice popup,
# glowing blue orb, voice engine selector,
# microphone, language selector and End button.

voice_event = voice_chat(
    reply=st.session_state.ma_voice_reply,
    reply_id=st.session_state.ma_voice_reply_id,
    failed_id=st.session_state.ma_voice_failed_id,
    audio_b64=st.session_state.ma_voice_audio_b64,
    elevenlabs_available=ELEVENLABS_READY,
)

spoken_question = (
    voice_event.get("text")
    if isinstance(voice_event, dict)
    else None
)

# ==================================================
# TEXT MESSAGE INPUT
# ==================================================

typed_question = st.chat_input(
    "Ask Merge AI anything...",
    max_chars=MAX_INPUT,
    key="ma_question",
)

st.markdown("""
<div class="ma-foot">
    One answer from multiple AI models ·
    Live Voice powered by ElevenLabs
</div>
""", unsafe_allow_html=True)

# ==================================================
# PROCESS TEXT OR VOICE QUESTIONS
# ==================================================

question = typed_question or spoken_question

if question and str(question).strip():
    is_voice = bool(
        spoken_question and not typed_question
    )

    question = str(question).strip()

    now = time.monotonic()

    st.session_state.ma_request_times = [
        t for t in st.session_state.ma_request_times
        if now - t < 3600
    ]

    if (
        len(st.session_state.ma_request_times)
        >= MAX_PER_HOUR
    ):
        st.warning(
            "Hourly question limit reached."
        )

        if is_voice:
            st.session_state.ma_voice_failed_id = (
                uuid.uuid4().hex
            )
            st.rerun()

    else:
        st.session_state.ma_request_times.append(now)

        with answer_space.container():
            with st.chat_message(
                "user",
                avatar="👤",
            ):
                st.markdown(question)

            with st.chat_message(
                "assistant",
                avatar=AVATAR,
            ):
                with st.spinner(
                    "Researching and merging..."
                ):
                    try:
                        engine = active_chat()["engine"]

                        ask_text = question

                        # In voice mode, request an answer
                        # in the selected language.
                        if is_voice and isinstance(
                            voice_event, dict
                        ):
                            language = voice_event.get(
                                "language_name",
                                "English",
                            )

                            ask_text += (
                                "\n\n[Voice preference: "
                                "Reply naturally in "
                                + str(language)
                                + ".]"
                            )

                        result = engine.ask(
                            ask_text,
                            fast=(
                                st.session_state.ma_answer_mode
                                == "Fast"
                            ),
                            web_search=st.session_state.ma_web_on,
                        )

                        answer = str(result)

                        report = getattr(
                            engine, "last_report", {}
                        )

                        sources = report.get(
                            "sources", []
                        )

                    except Exception:
                        logging.exception(
                            "Merge AI response failed"
                        )

                        if is_voice:
                            st.session_state.ma_voice_failed_id = (
                                uuid.uuid4().hex
                            )

                        st.error(
                            "Sorry, Merge AI could not "
                            "answer right now. Please retry."
                        )

                    else:
                        st.markdown(answer)
                        show_sources(sources)

                        append_message(
                            "user", question
                        )

                        append_message(
                            "assistant",
                            answer,
                            sources,
                        )

                        # Generate ElevenLabs audio
                        # only for voice conversations.
                        if is_voice:
                            st.session_state.ma_voice_audio_b64 = ""

                            chosen_provider = voice_event.get(
                                "voice_provider",
                                "browser",
                            )

                            if (
                                chosen_provider == "elevenlabs"
                                and ELEVENLABS_READY
                            ):
                                try:
                                    audio_bytes = synthesize(
                                        answer,
                                        ELEVENLABS_KEY,
                                        ELEVENLABS_VOICE_ID,
                                    )

                                    st.session_state.ma_voice_audio_b64 = (
                                        base64.b64encode(
                                            audio_bytes
                                        ).decode("ascii")
                                    )

                                except VoiceGenerationError as exc:
                                    logging.warning(
                                        "ElevenLabs unavailable: %s",
                                        exc,
                                    )

                            # Send response to voice popup.
                            # If no ElevenLabs audio was made,
                            # the component uses browser TTS.
                            st.session_state.ma_voice_reply = answer

                            st.session_state.ma_voice_reply_id = (
                                uuid.uuid4().hex
                            )

                        st.rerun()
