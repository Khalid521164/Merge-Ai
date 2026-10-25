
"""Merge AI — ChatGPT-style UI with a working history sidebar."""

from __future__ import annotations

import base64
import html
import inspect
import json
import os
import uuid

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import streamlit as st


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Merge AI",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# 2. API KEYS
# =========================================================

def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
        return str(value) if value is not None else default
    except Exception:
        return os.environ.get(name, default)


for key in (
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
    "GEMINI_MODEL",
    "GROQ_MODEL",
    "OPENROUTER_MODEL",
):
    value = secret(key)
    if value:
        os.environ[key] = value


ELEVENLABS_API_KEY = secret("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = secret("ELEVENLABS_VOICE_ID")


# =========================================================
# 3. IMPORT MERGE AI COMPONENTS
# =========================================================

try:
    from merge_ai import MergeAI, default_providers
    BACKEND_ERROR = ""
except Exception as exc:
    MergeAI = None
    default_providers = None
    BACKEND_ERROR = str(exc)


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
        init_voice_trainer,
        trainer_panel,
        apply_pronunciations,
        parse_correction,
        save_pronunciation,
    )
    HAS_TRAINER = True
except Exception:
    HAS_TRAINER = False


# =========================================================
# 4. CHAT MEMORY
# =========================================================

def make_chat(title="New chat"):
    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "created": datetime.now().isoformat(
            timespec="seconds"
        ),
        "messages": [],
    }


def initialize():
    defaults = {
        "ma_chats": [],
        "ma_active_chat": "",
        "ma_search_open": False,
        "ma_mode": "Fast",
        "ma_web": True,
        "ma_voice_reply": "",
        "ma_voice_reply_id": "",
        "ma_voice_failed_id": "",
        "ma_voice_audio_b64": "",
        "ma_voice_audio_error": "",
        "ma_last_voice_event": "",
        "ma_audio_bytes": None,
        "ma_audio_for": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.ma_chats:
        first = make_chat()

        st.session_state.ma_chats = [first]
        st.session_state.ma_active_chat = first["id"]

    valid_ids = {
        chat["id"]
        for chat in st.session_state.ma_chats
    }

    if st.session_state.ma_active_chat not in valid_ids:
        st.session_state.ma_active_chat = (
            st.session_state.ma_chats[0]["id"]
        )


initialize()

if HAS_TRAINER:
    init_voice_trainer()


def active_chat():
    return next(
        chat
        for chat in st.session_state.ma_chats
        if chat["id"] == st.session_state.ma_active_chat
    )


def new_chat():
    chat = make_chat()

    st.session_state.ma_chats.insert(0, chat)
    st.session_state.ma_active_chat = chat["id"]

    st.session_state.ma_audio_bytes = None
    st.session_state.ma_audio_for = ""


def remove_chat(chat_id):
    st.session_state.ma_chats = [
        chat
        for chat in st.session_state.ma_chats
        if chat["id"] != chat_id
    ]

    if not st.session_state.ma_chats:
        st.session_state.ma_chats = [make_chat()]

    if st.session_state.ma_active_chat == chat_id:
        st.session_state.ma_active_chat = (
            st.session_state.ma_chats[0]["id"]
        )

    st.session_state.ma_audio_bytes = None
    st.session_state.ma_audio_for = ""


# =========================================================
# 5. PROFESSIONAL UI DESIGN
# =========================================================

st.markdown(
    """
<style>

/* Keep the Streamlit sidebar button visible! */

#MainMenu,
footer {
    visibility: hidden;
}

header[data-testid="stHeader"],
[data-testid="stHeader"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    visibility: visible !important;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    z-index: 999999 !important;
}

/* Sidebar */

[data-testid="stSidebar"] {
    background: #f7f8f7;
    border-right: 1px solid #e5e9e6;
}

[data-testid="stSidebar"] .stButton > button {
    justify-content: flex-start;
    text-align: left;
    width: 100%;
    border-radius: 10px;
}

/* Main content */

.block-container {
    max-width: 920px;
    padding-top: 2.5rem;
    padding-bottom: 6rem;
}

/* Logo */

.m-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    margin: 10px 0 20px;
}

.m-logo {
    width: 38px;
    height: 38px;
    border-radius: 12px;
    background: #147353;
    color: white;
    display: grid;
    place-items: center;
    font-size: 21px;
    font-weight: 800;
}

.m-name {
    font-weight: 750;
    font-size: 20px;
}

/* Header */

.m-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 4px 0 28px;
    gap: 16px;
}

.m-title {
    font-size: 21px;
    font-weight: 680;
}

.m-model {
    color: #829188;
    font-size: 12px;
}

/* Welcome screen */

.m-welcome {
    min-height: 260px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 13px;
}

.m-welcome-mark {
    width: 55px;
    height: 55px;
    border-radius: 18px;
    background: #147353;
    color: white;
    font-size: 28px;
    font-weight: 800;
    display: grid;
    place-items: center;
}

.m-welcome-title {
    font-size: 26px;
    font-weight: 650;
    letter-spacing: -0.5px;
}

.m-welcome-desc {
    font-size: 13px;
    color: #849187;
}

/* User messages */

.m-user-line {
    display: flex;
    justify-content: flex-end;
    margin: 16px 0 8px;
}

.m-user-text {
    background: #f0f3f1;
    border-radius: 20px;
    padding: 11px 16px;
    max-width: 85%;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
}

/* Assistant messages */

.m-assistant {
    color: #147353;
    font-size: 13px;
    font-weight: 700;
    margin: 24px 0 10px;
}

.m-footnote {
    font-size: 11px;
    color: #8c9790;
    text-align: center;
    margin-top: 20px;
}

/* Chat input */

[data-testid="stChatInput"] {
    max-width: 920px;
    margin: auto;
}

[data-testid="stChatInput"] textarea {
    border-radius: 20px !important;
}

/* Mobile */

@media (max-width: 720px) {

    .block-container {
        padding-top: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }

    .m-welcome-title {
        font-size: 22px;
    }

    .m-user-text {
        max-width: 95%;
    }
}

/* Dark mode */

@media (prefers-color-scheme: dark) {

    [data-testid="stSidebar"] {
        background: #1b201e;
        border-right-color: #353b37;
    }

    .m-user-text {
        background: #303733;
        color: #f4f6f4;
    }
}

</style>
""",
    unsafe_allow_html=True,
)


# =========================================================
# 6. HISTORY SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        '<div class="m-brand">'
        '<div class="m-logo">M</div>'
        '<div class="m-name">Merge AI</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # New chat

    if st.button(
        "✏️  New chat",
        key="ma_new",
        use_container_width=True,
    ):
        new_chat()
        st.rerun()

    # Search chats

    if st.button(
        "🔎  Search chats",
        key="ma_search_toggle",
        use_container_width=True,
    ):
        st.session_state.ma_search_open = (
            not st.session_state.ma_search_open
        )
        st.rerun()

    search = ""

    if st.session_state.ma_search_open:
        search = st.text_input(
            "Search chats",
            placeholder="Search your conversations…",
        )

    st.divider()

    st.caption("CHAT HISTORY")

    displayed = 0

    for chat in st.session_state.ma_chats:

        searchable = chat["title"] + " " + " ".join(
            str(message.get("content", ""))
            for message in chat["messages"]
        )

        if (
            search
            and search.casefold() not in searchable.casefold()
        ):
            continue

        displayed += 1

        selected = (
            chat["id"] == st.session_state.ma_active_chat
        )

        label = (
            "🟢  " if selected else "💬  "
        ) + chat["title"][:31]

        if st.button(
            label,
            key="ma_open_" + chat["id"],
            use_container_width=True,
        ):
            st.session_state.ma_active_chat = chat["id"]
            st.session_state.ma_audio_bytes = None
            st.rerun()

    if not displayed:
        st.caption(
            "No conversations match your search."
        )

    # Chat management

    with st.expander("⚙️ Manage current chat"):

        name = st.text_input(
            "Chat title",
            value=active_chat()["title"],
            key=(
                "ma_title_"
                + st.session_state.ma_active_chat
            ),
        )

        if st.button(
            "Save title",
            key="ma_save_title",
        ):
            active_chat()["title"] = (
                name.strip() or "New chat"
            )
            st.rerun()

        if st.button(
            "🗑️ Delete this chat",
            key="ma_delete_chat",
        ):
            remove_chat(
                st.session_state.ma_active_chat
            )
            st.rerun()

        st.download_button(
            "⬇️ Export chat history",
            data=json.dumps(
                st.session_state.ma_chats,
                indent=2,
                ensure_ascii=False,
            ),
            file_name="merge_ai_chats.json",
            mime="application/json",
            key="ma_export",
        )

    st.divider()

    # AI settings

    st.session_state.ma_mode = st.selectbox(
        "Answer mode",
        ["Fast", "Deep"],
        index=(
            0
            if st.session_state.ma_mode == "Fast"
            else 1
        ),
        key="ma_mode_select",
    )

    st.session_state.ma_web = st.toggle(
        "🌐 Web search",
        value=st.session_state.ma_web,
        key="ma_web_toggle",
    )

    # Optional voice trainer

    if HAS_TRAINER:
        trainer_panel()

    st.caption(
        "History is saved for this Streamlit session. "
        "Export it to keep a backup."
    )


# =========================================================
# 7. MERGE AI BACKEND
# =========================================================

@st.cache_resource(show_spinner=False)
def get_engine():

    if MergeAI is None or default_providers is None:
        raise RuntimeError(
            "Could not import merge_ai.py: "
            + BACKEND_ERROR
        )

    return MergeAI(
        providers=default_providers(),
        tavily_api_key=secret("TAVILY_API_KEY"),
    )


def extract_answer(result: Any):

    if isinstance(result, str):
        return result, []

    if isinstance(result, dict):

        text = next(
            (
                result.get(key)
                for key in (
                    "answer",
                    "final_answer",
                    "final",
                    "response",
                    "text",
                )
                if result.get(key)
            ),
            None,
        )

        sources = result.get("sources") or []

    else:

        text = next(
            (
                getattr(result, key, None)
                for key in (
                    "answer",
                    "final_answer",
                    "final",
                    "response",
                    "text",
                )
                if getattr(result, key, None)
            ),
            None,
        )

        sources = (
            getattr(result, "sources", []) or []
        )

    if text is None:
        text = result

    if not isinstance(sources, list):
        sources = []

    return str(text), sources


def generate_answer(question):

    engine = get_engine()

    try:

        result = engine.ask(
            question,
            fast=(
                st.session_state.ma_mode == "Fast"
            ),
            web_search=st.session_state.ma_web,
        )

    except TypeError as exc:

        # Support older versions of merge_ai.py
        # that do not accept web_search.

        if "web_search" not in str(exc):
            raise

        result = engine.ask(
            question,
            fast=(
                st.session_state.ma_mode == "Fast"
            ),
        )

    return extract_answer(result)


# =========================================================
# 8. ELEVENLABS TEXT TO SPEECH
# =========================================================

def voice_audio(answer):

    st.session_state.ma_voice_audio_error = ""

    if not (
        ELEVENLABS_API_KEY
        and ELEVENLABS_VOICE_ID
        and synthesize
    ):
        st.session_state.ma_voice_audio_error = (
            "ElevenLabs needs ELEVENLABS_API_KEY, "
            "ELEVENLABS_VOICE_ID and elevenlabs_tts.py."
        )
        return None

    try:

        spoken = (
            apply_pronunciations(answer)
            if HAS_TRAINER
            else answer
        )

        parameters = inspect.signature(
            synthesize
        ).parameters

        options = {}

        settings = st.session_state.get(
            "vt_settings", {}
        )

        if "speed" in parameters:
            options["speed"] = float(
                settings.get("speed", 0.95)
            )

        if "stability" in parameters:
            options["stability"] = float(
                settings.get("stability", 0.55)
            )

        mp3 = synthesize(
            spoken,
            ELEVENLABS_API_KEY,
            ELEVENLABS_VOICE_ID,
            **options,
        )

        if not isinstance(mp3, bytes) or not mp3:
            raise RuntimeError(
                "ElevenLabs did not return MP3 data."
            )

        return mp3

    except Exception as exc:

        st.session_state.ma_voice_audio_error = str(
            exc
        )

        return None


# =========================================================
# 9. SOURCES
# =========================================================

def safe_url(raw):

    try:
        parsed = urlparse(raw)

        if (
            parsed.scheme in ("http", "https")
            and parsed.netloc
        ):
            return raw

    except Exception:
        pass

    return None


def show_sources(sources):

    entries = []

    for item in sources[:10]:

        if isinstance(item, str):
            url = item

        elif isinstance(item, dict):

            url = (
                item.get("url")
                or item.get("link")
                or ""
            )

            if isinstance(url, dict):
                url = url.get("uri", "")

        else:
            url = getattr(item, "url", "")

        if isinstance(url, str):

            clean = safe_url(url)

            if clean and clean not in entries:
                entries.append(clean)

    if entries:

        with st.expander(
            "Sources (" + str(len(entries)) + ")"
        ):

            for url in entries:
                st.markdown("- " + url)


# =========================================================
# 10. MAIN CHAT INTERFACE
# =========================================================

st.markdown(
    '<div class="m-top">'
    '<div class="m-title">Merge AI ⌄</div>'
    '<div class="m-model">'
    'Gemini + Groq + OpenRouter'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)


chat = active_chat()


# Welcome screen

if not chat["messages"]:

    st.markdown(
        '<div class="m-welcome">'
        '<div class="m-welcome-mark">M</div>'
        '<div class="m-welcome-title">'
        'What can I help with?'
        '</div>'
        '<div class="m-welcome-desc">'
        'Ask a question or start a voice conversation.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


# Display messages

for i, message in enumerate(chat["messages"]):

    if message["role"] == "user":

        st.markdown(
            '<div class="m-user-line">'
            '<div class="m-user-text">'
            + html.escape(message["content"])
            + '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    else:

        st.markdown(
            '<div class="m-assistant">'
            '✦ Merge AI'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(message["content"])

        show_sources(
            message.get("sources", [])
        )

        # Answer controls

        col1, col2, _ = st.columns(
            [1, 1, 9]
        )

        audio_key = (
            chat["id"] + ":" + str(i)
        )

        with col1:

            if st.button(
                "🔊",
                key="ma_speak_" + audio_key,
                help="Read aloud",
            ):

                st.session_state.ma_audio_bytes = (
                    voice_audio(
                        message["content"]
                    )
                )

                st.session_state.ma_audio_for = (
                    audio_key
                )

        with col2:

            if st.button(
                "📋",
                key="ma_copy_" + audio_key,
                help="Show copyable text",
            ):

                st.code(
                    message["content"],
                    language=None,
                )

        # Audio player

        if (
            st.session_state.ma_audio_for
            == audio_key
        ):

            if st.session_state.ma_audio_bytes:

                st.audio(
                    st.session_state.ma_audio_bytes,
                    format="audio/mpeg",
                )

            elif (
                st.session_state.ma_voice_audio_error
            ):

                st.warning(
                    st.session_state.ma_voice_audio_error
                )


# =========================================================
# 11. LIVE VOICE FEATURE
# =========================================================

st.markdown("**🎙️ Live Voice**")

voice_event = None


if voice_chat is not None:

    try:

        voice_event = voice_chat(
            reply=st.session_state.ma_voice_reply,
            reply_id=st.session_state.ma_voice_reply_id,
            failed_id=st.session_state.ma_voice_failed_id,
            audio_b64=st.session_state.ma_voice_audio_b64,
            elevenlabs_available=bool(
                ELEVENLABS_API_KEY
                and ELEVENLABS_VOICE_ID
                and synthesize
            ),
        )

    except Exception as exc:

        st.warning(
            "Could not display Live Voice: "
            + str(exc)
        )

else:

    st.caption(
        "Add your existing voice_chat.py "
        "to enable the Live Voice orb."
    )


# =========================================================
# 12. VOICE QUESTION PROCESSING
# =========================================================

spoken = ""
voice_provider = "browser"


if isinstance(voice_event, dict):

    spoken = str(
        voice_event.get("text") or ""
    ).strip()

    voice_provider = str(
        voice_event.get("voice_provider")
        or "browser"
    )


# =========================================================
# 13. MESSAGE INPUT
# =========================================================

question = st.chat_input(
    "Ask Merge AI anything…"
)

is_voice = False


# Check for a new voice question

if not question and spoken:

    event_id = str(
        voice_event.get("request_id")
        or voice_event.get("id")
        or spoken
    )

    if (
        event_id
        != st.session_state.ma_last_voice_event
    ):

        st.session_state.ma_last_voice_event = (
            event_id
        )

        question = spoken
        is_voice = True


# =========================================================
# 14. GENERATE AN ANSWER
# =========================================================

if question and question.strip():

    question = question.strip()

    # Pronunciation teaching commands

    if HAS_TRAINER:

        correction = parse_correction(
            question
        )

        if correction:

            if save_pronunciation(
                *correction
            ):

                st.success(
                    "Saved pronunciation: "
                    + correction[0]
                    + " → "
                    + correction[1]
                )

            else:

                st.warning(
                    "Could not save the "
                    "pronunciation correction."
                )

            st.stop()

    # Save user message

    chat = active_chat()

    chat["messages"].append(
        {
            "role": "user",
            "content": question,
        }
    )

    # Rename new chat automatically

    if chat["title"] == "New chat":

        chat["title"] = (
            question[:40]
            + ("…" if len(question) > 40 else "")
        )

    # Move active chat to top of history

    st.session_state.ma_chats.remove(
        chat
    )

    st.session_state.ma_chats.insert(
        0, chat
    )

    # Generate AI response

    with st.spinner(
        "Consulting models and preparing your answer…"
    ):

        try:

            answer, sources = (
                generate_answer(question)
            )

        except Exception as exc:

            answer = (
                "I couldn't generate an answer. "
                "Check your API keys and logs. "
                "Details: "
                + str(exc)
            )

            sources = []

    # Save AI response

    chat["messages"].append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
        }
    )

    # Voice reply

    if is_voice:

        st.session_state.ma_voice_reply = (
            answer
        )

        st.session_state.ma_voice_reply_id = (
            str(uuid.uuid4())
        )

        st.session_state.ma_voice_failed_id = ""
        st.session_state.ma_voice_audio_b64 = ""

        if voice_provider == "elevenlabs":

            sound = voice_audio(answer)

            if sound:

                st.session_state.ma_voice_audio_b64 = (
                    base64.b64encode(
                        sound
                    ).decode("ascii")
                )

            else:

                st.session_state.ma_voice_failed_id = (
                    st.session_state.ma_voice_reply_id
                )

    st.rerun()


# =========================================================
# 15. FOOTER
# =========================================================

st.markdown(
    '<div class="m-footnote">'
    'Merge AI can make mistakes. '
    'Verify important information.'
    '</div>',
    unsafe_allow_html=True,
)
