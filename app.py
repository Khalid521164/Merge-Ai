
"""Merge AI - Streamlit Website
Google Login + Supabase Chat History + Responsive UI

Required existing files:
    merge_ai.py
    interaction.py
    web_search.py
    cloud_history.py

All API keys must stay in Streamlit Secrets.
"""

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

from merge_ai import MergeAI, default_providers, safe_source_url
from cloud_history import CloudHistory, CloudHistoryError


# ==========================================
# PAGE CONFIGURATION
# ==========================================

ICON_PATH = Path(__file__).parent / "merge_ai_favicon.png"

FAVICON = str(ICON_PATH) if ICON_PATH.is_file() else "🟢"
AI_AVATAR = FAVICON if ICON_PATH.is_file() else "🤖"

st.set_page_config(
    page_title="Merge AI | One clearer answer",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAX_CHATS = 20
MAX_INPUT = 1000
MAX_PER_HOUR = 20


# ==========================================
# PROFESSIONAL RESPONSIVE DESIGN
# ==========================================

st.markdown("""
<style>

:root {
    --bg: #faf8f4;
    --white: #ffffff;
    --green: #326957;
    --dark: #193e35;
    --mint: #f1f7f2;
    --line: #dfebe1;
    --muted: #708178;
}

html, body, .stApp {
    background: var(--bg) !important;
    color: var(--dark) !important;
    font-family: system-ui, sans-serif;
    color-scheme: light !important;
}

[data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
}

[data-testid="stMainBlockContainer"] {
    max-width: 950px !important;
    padding: 1.3rem 1.4rem 2rem !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
#MainMenu,
footer {
    display: none !important;
}

.ma-logo {
    display: flex;
    align-items: center;
    gap: 13px;
    margin-bottom: 13px;
}

.ma-mark {
    background: var(--green);
    color: white;
    border-radius: 15px;
    width: 49px;
    height: 49px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 25px;
    font-weight: 850;
}

.ma-name {
    color: var(--dark);
    font-size: 27px;
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1.2;
}

.ma-subtitle {
    color: var(--muted);
    font-size: 10px;
    letter-spacing: 1px;
    margin-top: 4px;
}

.ma-line {
    height: 1px;
    background: var(--line);
    margin-bottom: 12px;
}

.stButton > button,
[data-testid="stPopover"] button {
    border: 1px solid var(--line) !important;
    background: white !important;
    color: var(--dark) !important;
    border-radius: 12px !important;
    min-height: 41px !important;
    font-weight: 600 !important;
}

.stButton > button:hover,
[data-testid="stPopover"] button:hover {
    border-color: #a4c2ac !important;
    background: var(--mint) !important;
}

.st-key-merge_toolbar [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 7px !important;
}

.st-key-merge_toolbar [data-testid="column"] {
    min-width: 0 !important;
    flex: 1 1 0 !important;
    width: 0 !important;
}

.st-key-merge_conversation {
    background: white !important;
    border: 1px solid var(--line) !important;
    border-radius: 20px !important;
    box-shadow: 0 7px 25px #173c3510;
}

[data-testid="stChatMessage"] {
    background: white !important;
    border: 1px solid var(--line) !important;
    border-radius: 15px !important;
    padding: 12px !important;
    margin-bottom: 8px !important;
}

[data-testid="stChatMessageContent"] {
    overflow-wrap: anywhere;
    min-width: 0;
}

.ma-welcome {
    text-align: center;
    padding: 80px 10px 55px;
}

.ma-welcome-icon {
    background: var(--mint);
    color: var(--green);
    width: 58px;
    height: 58px;
    border-radius: 18px;
    display: grid;
    place-items: center;
    margin: auto auto 25px;
    font-size: 30px;
}

.ma-welcome h2 {
    color: var(--dark);
    font-size: clamp(22px, 4vw, 30px);
    letter-spacing: -0.7px;
}

.ma-welcome p {
    color: var(--muted);
    font-size: 13px;
    line-height: 1.8;
}

.ma-section {
    color: var(--dark);
    font-weight: 750;
    margin: 17px 0 9px;
    font-size: 14px;
}

.ma-section span {
    color: var(--muted);
    font-size: 11px;
    font-weight: 400;
}

[data-testid="stChatInput"] {
    border: 1px solid #cbded0 !important;
    background: white !important;
    border-radius: 15px !important;
}

.ma-footer {
    color: var(--muted);
    text-align: center;
    font-size: 10px;
    margin-top: 15px;
}

@media (max-width: 650px) {
    [data-testid="stMainBlockContainer"] {
        padding: 0.8rem 0.6rem 1.5rem !important;
    }

    .ma-name {
        font-size: 22px;
    }

    .ma-mark {
        width: 42px;
        height: 42px;
        font-size: 22px;
    }

    .ma-subtitle {
        font-size: 8px;
    }

    .ma-welcome {
        padding: 45px 5px 35px;
    }

    .st-key-merge_toolbar button {
        font-size: 12px !important;
        padding-left: 4px !important;
        padding-right: 4px !important;
    }

    [data-testid="stChatMessage"] {
        padding: 9px !important;
    }
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# SECRET CONFIGURATION
# ==========================================

def get_secret(name):
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


for key in (
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TAVILY_API_KEY",
):
    value = get_secret(key)
    if value:
        os.environ[key] = value


# ==========================================
# GOOGLE AUTHENTICATION
# ==========================================

def current_user():
    try:
        if st.user.is_logged_in:
            return st.user
    except (AttributeError, KeyError):
        pass
    return None


def owner_id():
    user = current_user()

    if user is None:
        return None

    subject = str(user.get("sub") or "").strip()

    if not subject:
        return None

    return "google:" + subject


def google_ready():
    try:
        auth = st.secrets.get("auth", {})
        return all(
            auth.get(k)
            for k in (
                "redirect_uri",
                "cookie_secret",
                "client_id",
                "client_secret",
                "server_metadata_url",
            )
        )
    except Exception:
        return False


def clear_account_session():
    for key in (
        "ma_chats_v2",
        "ma_active_v2",
        "ma_identity",
        "ma_cloud_loaded",
        "ma_cloud_error",
        "ma_request_times",
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

            if cloud_connection() is not None:
                st.caption("Cloud chat history is configured.")
            else:
                st.warning("Cloud history is not configured.")

            if st.button(
                "Log out",
                key="ma_logout",
                use_container_width=True,
            ):
                clear_account_session()
                st.logout()

        else:
            st.markdown("#### Welcome to Merge AI")
            st.caption("Sign in to save your conversations.")

            ready = google_ready()

            if st.button(
                "Continue with Google",
                key="ma_google",
                use_container_width=True,
                disabled=not ready,
            ):
                st.login()

            if not ready:
                st.caption(
                    "Configure Google OAuth in Streamlit Secrets."
                )

            st.button(
                "Continue with Apple",
                key="ma_apple",
                disabled=True,
                use_container_width=True,
            )

            st.caption(
                "You can continue as a guest without signing in."
            )


# ==========================================
# AI BACKEND
# ==========================================

def new_engine():
    return MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
    )


def restore_context(engine, messages):
    turns = []
    question = None

    for message in messages:
        if not isinstance(message, dict):
            continue

        if message.get("role") == "user":
            question = str(message.get("content", ""))

        elif message.get("role") == "assistant" and question is not None:
            turns.append(
                (question, str(message.get("content", "")))
            )
            question = None

    engine._turns = turns[-12:]


# ==========================================
# SUPABASE CLOUD CONNECTION
# ==========================================

def cloud_connection():
    owner = owner_id()

    if not owner:
        return None

    url = get_secret("SUPABASE_URL")
    secret = get_secret("SUPABASE_SECRET_KEY")

    if not url or not secret:
        return None

    try:
        return CloudHistory(url, secret, owner)
    except CloudHistoryError:
        logging.warning("Cloud history configuration failed")
        return None


def save_cloud_chat(chat):
    if owner_id() is None:
        return True

    client = cloud_connection()

    if client is None:
        st.session_state.ma_cloud_error = (
            "Cloud history is unavailable. "
            "This chat is not saved to your account."
        )
        return False

    try:
        client.upsert(chat)
        st.session_state.ma_cloud_error = ""
        return True

    except CloudHistoryError:
        logging.exception("Could not save cloud chat")
        st.session_state.ma_cloud_error = (
            "Could not save your chat to Supabase. "
            "Download a backup from History."
        )
        return False


def load_cloud_chats():
    if st.session_state.get("ma_cloud_loaded", False):
        return

    st.session_state.ma_cloud_loaded = True

    client = cloud_connection()

    if client is None:
        if owner_id() is not None:
            st.session_state.ma_cloud_error = (
                "Cloud history isn't configured. "
                "Check your Supabase settings."
            )
        return

    try:
        records = client.list_chats()

        imported = {}

        for row in records:
            chat_id = str(uuid.UUID(str(row["id"]))).replace("-", "")

            messages = row.get("messages", [])

            if not isinstance(messages, list):
                messages = []

            engine = new_engine()
            restore_context(engine, messages)

            imported[chat_id] = {
                "id": chat_id,
                "title": str(row.get("title") or "New conversation")[:60],
                "messages": messages,
                "updated": time.time(),
                "engine": engine,
            }

        if imported:
            existing = st.session_state.ma_chats_v2

            # Preserve any local chats until explicitly deleted.
            existing.update(imported)

            st.session_state.ma_active_v2 = next(iter(imported))

        st.session_state.ma_cloud_error = ""

    except (CloudHistoryError, ValueError, KeyError, TypeError):
        logging.exception("Could not load cloud history")

        st.session_state.ma_cloud_error = (
            "Cloud history could not be loaded. "
            "New chats may not be saved."
        )


def delete_cloud_chat(chat_id):
    if owner_id() is None:
        return True

    client = cloud_connection()

    if client is None:
        st.session_state.ma_cloud_error = (
            "Cloud history unavailable. Cannot delete saved chat."
        )
        return False

    try:
        client.delete(chat_id)
        return True

    except CloudHistoryError:
        logging.exception("Cloud chat deletion failed")
        st.session_state.ma_cloud_error = (
            "Could not delete the cloud conversation."
        )
        return False


# ==========================================
# CHAT HISTORY MANAGEMENT
# ==========================================

def make_chat():
    return {
        "id": uuid.uuid4().hex,
        "title": "New conversation",
        "messages": [],
        "updated": time.time(),
        "engine": new_engine(),
    }


def ensure_history():
    """Always initialize history, even if Supabase is unavailable."""

    chats = st.session_state.get("ma_chats_v2")

    if not isinstance(chats, dict) or not chats:
        record = make_chat()

        st.session_state.ma_chats_v2 = {
            record["id"]: record
        }

        st.session_state.ma_active_v2 = record["id"]

    elif (
        st.session_state.get("ma_active_v2")
        not in st.session_state.ma_chats_v2
    ):
        st.session_state.ma_active_v2 = next(
            iter(st.session_state.ma_chats_v2)
        )


def initialize():
    identity = owner_id() or "guest"

    if st.session_state.get("ma_identity") != identity:
        clear_account_session()
        st.session_state.ma_identity = identity

    ensure_history()

    st.session_state.setdefault("ma_web_on", True)
    st.session_state.setdefault("ma_mode", "Fast")
    st.session_state.setdefault("ma_request_times", [])
    st.session_state.setdefault("ma_cloud_error", "")

    load_cloud_chats()

    # Important: prevent History from crashing.
    ensure_history()


def active_chat():
    ensure_history()

    return st.session_state.ma_chats_v2[
        st.session_state.ma_active_v2
    ]


def create_chat():
    current = active_chat()

    if not current["messages"]:
        return True

    if len(st.session_state.ma_chats_v2) >= MAX_CHATS:
        return False

    chat = make_chat()

    st.session_state.ma_chats_v2[chat["id"]] = chat
    st.session_state.ma_active_v2 = chat["id"]

    return True


def chat_title(question):
    question = " ".join(str(question).split())

    return (
        question[:42] + ("…" if len(question) > 42 else "")
        if question else "New conversation"
    )


def add_message(role, content, sources=None):
    chat = active_chat()

    record = {
        "role": role,
        "content": content,
    }

    if role == "assistant" and sources:
        record["sources"] = sources

    chat["messages"].append(record)
    chat["updated"] = time.time()

    if role == "user":
        questions = sum(
            m.get("role") == "user"
            for m in chat["messages"]
        )

        if questions == 1:
            chat["title"] = chat_title(content)


def remove_chat(chat_id):
    if not delete_cloud_chat(chat_id):
        return False

    chats = st.session_state.ma_chats_v2
    chats.pop(chat_id, None)

    if not chats:
        new = make_chat()
        chats[new["id"]] = new

    if st.session_state.ma_active_v2 not in chats:
        st.session_state.ma_active_v2 = next(iter(chats))

    return True


def history_backup():
    chats = st.session_state.ma_chats_v2.values()

    data = {
        "app": "Merge AI",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chats": [
            {
                "title": chat["title"],
                "messages": chat["messages"],
            }
            for chat in chats if chat["messages"]
        ],
    }

    return json.dumps(data, ensure_ascii=False, indent=2)


# ==========================================
# CHAT HISTORY COMPONENT
# ==========================================

def history_menu():
    ensure_history()

    with st.popover("History", use_container_width=True):

        st.markdown("#### Your conversations")

        search = st.text_input(
            "Search chats",
            placeholder="Search chat history...",
            key="ma_search",
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

        with st.container(height=230, border=False):

            if not chats:
                st.caption("No matching conversations.")

            for chat in chats:

                selected = (
                    chat["id"] == st.session_state.ma_active_v2
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

        with st.expander("Rename or delete chat"):

            chat = active_chat()

            title = st.text_input(
                "Conversation title",
                value=chat["title"],
                max_chars=60,
                key="rename_" + chat["id"],
            )

            if st.button(
                "Save name",
                key="save_name_" + chat["id"],
            ):
                new_title = title.strip()

                if new_title:
                    chat["title"] = new_title
                    chat["updated"] = time.time()
                    save_cloud_chat(chat)
                    st.rerun()

            if st.button(
                "Delete chat",
                key="delete_" + chat["id"],
            ):
                if remove_chat(chat["id"]):
                    st.rerun()

        st.download_button(
            "Download chat backup",
            data=history_backup(),
            file_name="merge_ai_history.json",
            mime="application/json",
            use_container_width=True,
        )

        if owner_id():
            if st.session_state.ma_cloud_error:
                st.caption("Cloud sync is currently unavailable.")
            elif cloud_connection():
                st.caption("Google account cloud history enabled.")
            else:
                st.caption("Cloud sync is not configured.")
        else:
            st.caption("Guest chats are temporary.")


# ==========================================
# TAVILY SOURCE LINKS
# ==========================================

def show_sources(sources):
    if not isinstance(sources, list):
        return

    verified = []

    for item in sources[:8]:

        if not isinstance(item, dict):
            continue

        url = safe_source_url(item.get("url"))

        if url:
            title = str(
                item.get("title")
                or urlsplit(url).hostname
                or "Source"
            )[:90]

            verified.append((title, url))

    if verified:
        with st.expander(
            f"Research sources ({len(verified)})"
        ):
            for title, url in verified:
                st.link_button(title, url)


# ==========================================
# INITIALIZE ALL CHAT STATE
# ==========================================

initialize()


# ==========================================
# STATUS WARNINGS
# ==========================================

if st.session_state.ma_cloud_error:
    st.warning(st.session_state.ma_cloud_error)


# ==========================================
# HEADER
# ==========================================

with st.container():

    brand_col, account_col = st.columns(
        [5, 2],
        gap="small",
        vertical_alignment="center",
    )

    with brand_col:
        st.markdown("""
        <div class="ma-logo">
            <div class="ma-mark">M</div>
            <div>
                <div class="ma-name">Merge AI</div>
                <div class="ma-subtitle">
                    THINK TOGETHER. ANSWER BETTER.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with account_col:
        account_menu()

st.markdown(
    '<div class="ma-line"></div>',
    unsafe_allow_html=True,
)


# ==========================================
# TOOLBAR
# ==========================================

with st.container(key="merge_toolbar"):

    history_col, new_col, settings_col = st.columns(
        [1, 1, 1],
        gap="small",
    )

    with history_col:
        history_menu()

    with new_col:
        if st.button(
            "＋ New chat",
            use_container_width=True,
            key="ma_new_chat",
        ):
            if create_chat():
                st.rerun()
            else:
                st.warning(
                    "Maximum conversations reached. "
                    "Delete an old chat first."
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
                key="ma_mode",
            )

            st.caption(
                "Gemini · OpenRouter · Groq"
            )


# ==========================================
# CONVERSATION SCREEN
# ==========================================

st.markdown("""
<div class="ma-section">
    Conversation
    <span>Gemini · OpenRouter · Groq · Tavily research</span>
</div>
""", unsafe_allow_html=True)


with st.container(
    height=420,
    border=True,
    key="merge_conversation",
):

    chat = active_chat()

    if not chat["messages"]:

        st.markdown("""
        <div class="ma-welcome">
            <div class="ma-welcome-icon">✦</div>
            <h2>What's on your mind?</h2>
            <p>
                Ask anything. Multiple AI models work together
                <br>
                to produce one thoughtful answer.
            </p>
        </div>
        """, unsafe_allow_html=True)

    else:

        for message in chat["messages"]:

            role = message.get("role", "assistant")

            if role not in ("user", "assistant"):
                continue

            avatar = (
                "👤" if role == "user"
                else AI_AVATAR
            )

            with st.chat_message(
                role,
                avatar=avatar,
            ):
                st.markdown(
                    str(message.get("content", ""))
                )

                if role == "assistant":
                    show_sources(
                        message.get("sources")
                    )

    answer_space = st.empty()


# ==========================================
# MESSAGE INPUT
# ==========================================

with st.container():

    question = st.chat_input(
        "Ask Merge AI anything...",
        max_chars=MAX_INPUT,
        key="ma_question",
    )


st.markdown("""
<div class="ma-footer">
    One answer from multiple AI models ·
    Google account cloud history when connected
</div>
""", unsafe_allow_html=True)


# ==========================================
# ASK MERGE AI
# ==========================================

if question and question.strip():

    question = question.strip()

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
            "You have reached this session's hourly "
            "question limit. Please try later."
        )

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
                avatar=AI_AVATAR,
            ):

                with st.spinner(
                    "Researching and merging an answer..."
                ):

                    try:

                        engine = active_chat()["engine"]

                        result = engine.ask(
                            question,
                            fast=(
                                st.session_state.ma_mode
                                == "Fast"
                            ),
                            web_search=st.session_state.ma_web_on,
                        )

                        answer = str(result)

                        sources = engine.last_report.get(
                            "sources", []
                        )

                    except Exception:

                        logging.exception(
                            "Merge AI request failed"
                        )

                        st.error(
                            "Sorry, I couldn't complete "
                            "that answer. Please try again."
                        )

                    else:

                        st.markdown(answer)
                        show_sources(sources)

                        add_message(
                            "user",
                            question,
                        )

                        add_message(
                            "assistant",
                            answer,
                            sources,
                        )

                        # Save completed conversation.
                        saved = save_cloud_chat(active_chat())

                        if not saved and owner_id():
                            st.warning(
                                "Answer completed, but cloud "
                                "history was not saved."
                            )

                        st.rerun()
