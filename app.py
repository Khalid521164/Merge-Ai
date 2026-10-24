"""Merge AI web app — responsive Streamlit screen, history, optional Google sign-in.

Requires only Streamlit and your existing Merge AI project modules:
    merge_ai.py, interaction.py, web_search.py

The optional merge_ai_favicon.png is used if it exists. Nothing crashes if
that image is missing. API keys should be configured in Streamlit Secrets.

Guest chats are session-only. Signed-in Google users save chats to Supabase
when SUPABASE_URL and SUPABASE_SECRET_KEY exist in Streamlit Secrets.

Google sign-in works when Streamlit OIDC secrets are configured and Authlib
is installed. Guests can use the website without logging in. Apple web OAuth
is not activated because it requires additional Apple developer setup.
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

# --- Page setup: do not require an image that might be missing on GitHub. ---
ICON_FILE = Path(__file__).resolve().parent / "merge_ai_favicon.png"
ICON = str(ICON_FILE) if ICON_FILE.is_file() else "🟢"
ASSISTANT_AVATAR = ICON if ICON_FILE.is_file() else "🤖"

st.set_page_config(
    page_title="Merge AI | One clearer answer",
    page_icon=ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Import only the existing AI backend. There is NO dependency on the older
# chat_history.py or account_info.py files, so their imports cannot crash this page.
from merge_ai import MergeAI, default_providers, safe_source_url
from cloud_history import CloudHistory, CloudHistoryError

MAX_CHATS = 20
MAX_QUESTION_CHARS = 1000
MAX_QUESTIONS_PER_HOUR = 20


# --- Theme: identical screen components at all breakpoints. ---
st.markdown(
    """
<style>
:root {
    --cream:#faf8f4; --paper:#ffffff; --forest:#193e35;
    --green:#326957; --muted:#708178; --line:#dfebe1; --mint:#f1f7f2;
}
html,body,.stApp,[data-testid="stAppViewContainer"] {
    background:var(--cream)!important;
    color-scheme:light!important;
    color:var(--forest)!important;
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif!important;
}
[data-testid="stHeader"] {background:transparent!important;}
[data-testid="stDecoration"],footer {display:none!important;}
/* Hide optional Streamlit chrome when supported by this Streamlit version. */
[data-testid="stToolbar"], #MainMenu, .stAppDeployButton {display:none!important;}
.st-key-ma_brand_account [data-testid="stHorizontalBlock"] {
    align-items:center!important;flex-wrap:nowrap!important;
}
[data-testid="stMainBlockContainer"] {
    max-width:950px!important;
    padding:1.35rem clamp(.75rem,3vw,1.7rem) 2rem!important;
}
.merge-brand {display:flex;align-items:center;gap:12px;padding-bottom:10px;}
.merge-mark {
    width:48px;height:48px;flex:none;display:grid;place-items:center;
    border-radius:15px;background:var(--green);color:white;
    font-size:25px;font-weight:850;box-shadow:0 8px 20px #32695723;
}
.merge-title {font-size:clamp(22px,3.8vw,28px);font-weight:800;
    letter-spacing:-1px;line-height:1.2;color:var(--forest);}
.merge-sub {font-size:10px;letter-spacing:.095em;color:var(--muted);
    margin-top:3px;font-weight:600;}
.merge-rule {height:1px;background:var(--line);margin:8px 0 13px;}
.st-key-ma_brand_account [data-testid="stPopover"] button {
    white-space:nowrap; font-size:13px!important;
}
.merge-section {display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;
    margin:15px 0 10px;}
.merge-section strong {font-size:15px;font-weight:800;color:var(--forest);}
.merge-section span {font-size:11px;color:var(--muted);}
[data-testid="stVerticalBlock"] {gap:.65rem;}
.st-key-merge_toolbar [data-testid="stHorizontalBlock"] {
    flex-direction:row!important;flex-wrap:nowrap!important;gap:.4rem!important;
}
.st-key-merge_toolbar [data-testid="column"] {
    min-width:0!important;flex:1 1 0!important;width:0!important;
}
.stButton>button, [data-testid="stPopover"] button {
    border:1px solid var(--line)!important;color:var(--forest)!important;
    background:var(--paper)!important;border-radius:12px!important;
    font-weight:650!important;min-height:40px!important;
}
.stButton>button:hover,[data-testid="stPopover"] button:hover {
    border-color:#9fbbab!important;background:var(--mint)!important;
}
.st-key-merge_conversation {
    border-radius:20px!important;border:1px solid var(--line)!important;
    background:var(--paper)!important;box-shadow:0 8px 25px #173c3510;
}
[data-testid="stChatMessage"] {
    background:var(--paper)!important;border:1px solid var(--line)!important;
    border-radius:16px!important;padding:12px 14px!important;margin:7px 0!important;
    box-shadow:0 2px 8px #173c3506;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background:var(--mint)!important;
}
[data-testid="stChatMessageContent"] {min-width:0;overflow-wrap:anywhere;}
[data-testid="stChatMessageContent"] p {line-height:1.6;}
.merge-welcome {text-align:center;padding:85px 12px 70px;color:var(--forest);}
.merge-welcome-mark {width:55px;height:55px;margin:0 auto 18px;
    border-radius:18px;background:var(--mint);color:var(--green);
    font-weight:900;font-size:29px;display:grid;place-items:center;}
.merge-welcome h2 {font-size:clamp(20px,4vw,29px);line-height:1.3;
    letter-spacing:-.6px;margin:0 0 12px;font-weight:850;}
.merge-welcome p {font-size:13px;color:var(--muted);line-height:1.6;margin:0;}
[data-testid="stChatInput"] {
    border:1px solid #cbded0!important;border-radius:15px!important;
    background:white!important;box-shadow:0 6px 22px #173c3511!important;
}
[data-testid="stChatInput"] textarea {font-size:14px!important;color:var(--forest)!important;}
.merge-footnote {text-align:center;font-size:11px;color:var(--muted);margin:10px 0 0;}
@media(max-width:650px) {
  [data-testid="stMainBlockContainer"] {padding:1rem .6rem 1.5rem!important;}
  .merge-mark {width:42px;height:42px;font-size:23px;border-radius:13px;}
  .merge-brand {gap:9px;}
  .merge-sub {font-size:9px;letter-spacing:.055em;}
  .st-key-merge_toolbar button {min-height:38px!important;font-size:12px!important;
    padding-left:.3rem!important;padding-right:.3rem!important;}
  [data-testid="stChatMessage"] {padding:10px!important;border-radius:13px!important;}
  .merge-welcome {padding:50px 6px 36px;}
  .merge-section span {font-size:10px;}
  .st-key-ma_brand_account [data-testid="stPopover"] button {
    font-size:12px!important;min-height:37px!important;padding:.3rem!important;
  }
}
</style>
""",
    unsafe_allow_html=True,
)


# --- Secrets stay server-side. ---
def read_secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except (KeyError, FileNotFoundError):
        return ""
    except Exception:
        return ""


# Google login uses Streamlit's built-in OIDC support. The OAuth client ID,
# secret, redirect URI and cookie signing secret are configured in Streamlit
# Cloud > App settings > Secrets, not in this public source file.
def google_auth_ready() -> bool:
    try:
        config = st.secrets.get("auth", {})
        return all(config.get(name) for name in (
            "redirect_uri", "cookie_secret", "client_id",
            "client_secret", "server_metadata_url",
        ))
    except (KeyError, FileNotFoundError, TypeError, AttributeError):
        return False


def logged_in_user():
    try:
        if st.user.is_logged_in:
            return st.user
    except (AttributeError, KeyError):
        pass
    return None


def current_identity() -> str:
    # Email is not used as a database key. The OIDC subject is provider-scoped.
    user = logged_in_user()
    if user is None:
        return "guest"
    sub = str(user.get("sub") or "").strip()
    return "google:" + sub if sub else "guest"


def erase_session_chats() -> None:
    # Clear per-visitor data before logout; never let the next user see it.
    for key in (
        "ma_chats_v2", "ma_active_v2", "ma_request_times", "ma_identity_v3",
        "messages", "merge_chats", "merge_engines", "merge_active_id", "engine",
        "ma_cloud_loaded", "ma_cloud_error",
    ):
        if key in st.session_state:
            del st.session_state[key]


def account_controls() -> None:
    user = logged_in_user()
    button_label = "Account" if user is None else "My account"
    with st.popover(button_label, use_container_width=True):
        if user is not None:
            name = str(user.get("name") or "Merge AI member")
            email = str(user.get("email") or "")
            st.markdown(f"**Signed in as {name}**")
            if email:
                st.caption(email)
            st.caption("Your chats sync with your account when cloud history is connected.")
            if st.button("Log out", key="ma_google_logout", use_container_width=True):
                erase_session_chats()
                st.logout()
        else:
            st.markdown("##### Welcome to Merge AI")
            st.caption("Continue as a guest, or use a Google account.")
            is_ready = google_auth_ready()
            if st.button("Continue with Google", key="ma_google_login",
                         use_container_width=True, disabled=not is_ready):
                st.login()
            if not is_ready:
                st.caption("Google sign-in becomes available after its private "
                           "Google OAuth settings are added in Streamlit Secrets.")
            st.button("Continue with Apple", key="ma_apple_login",
                      use_container_width=True, disabled=True,
                      help="Apple web sign-in needs Apple Developer Program setup.")
            st.caption("Apple sign-in is not enabled on the free setup. "
                       "Its web configuration generally requires a paid Apple Developer membership.")
            st.caption("**Guest access is already enabled.** Close this menu to start chatting.")


for _key in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY"):
    _val = read_secret(_key)
    if _val:
        os.environ[_key] = _val


def make_engine() -> MergeAI:
    return MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
    )


# --- Cloud history: accessed only from authenticated Streamlit server code. ---
def cloud_client():
    owner = current_identity()
    if owner == "guest":
        return None
    url = read_secret("SUPABASE_URL")
    key = read_secret("SUPABASE_SECRET_KEY")
    if not (url and key):
        return None
    try:
        return CloudHistory(url, key, owner)
    except CloudHistoryError:
        return None


def restore_engine_history(engine, messages):
    """Rebuild the existing MergeAI engine's conversational context."""
    turns = []
    pending = None
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user":
            pending = str(message.get("content", ""))
        elif message.get("role") == "assistant" and pending is not None:
            turns.append((pending, str(message.get("content", ""))))
            pending = None
    engine._turns = turns[-12:]


def cloud_load():
    if st.session_state.get("ma_cloud_loaded"):
        return
    st.session_state.ma_cloud_loaded = True
    client = cloud_client()
    if client is None:
        return
    try:
        rows = client.list_chats()
        if rows:
            imported = {}
            for row in rows:
                chat_id = str(uuid.UUID(str(row["id"]))).replace("-", "")
                messages = row.get("messages")
                if not isinstance(messages, list):
                    messages = []
                engine = make_engine()
                restore_engine_history(engine, messages)
                imported[chat_id] = {
                    "id": chat_id, "title": str(row.get("title") or "New conversation")[:60],
                    "messages": messages, "updated": time.time(), "engine": engine,
                }
            st.session_state.ma_chats_v2 = imported
            st.session_state.ma_active_v2 = next(iter(imported))
    except (CloudHistoryError, ValueError, KeyError, TypeError):
        st.session_state.ma_cloud_error = "Cloud history could not be loaded. New chats may not be saved."


def cloud_save(chat):
    client = cloud_client()
    if client is None:
        return
    try:
        client.upsert(chat)
        st.session_state.ma_cloud_error = ""
    except (CloudHistoryError, ValueError, KeyError):
        st.session_state.ma_cloud_error = "Could not save this chat to your account. Keep a backup."


def cloud_delete(chat_id):
    client = cloud_client()
    if client is None:
        return True
    try:
        client.delete(chat_id)
        st.session_state.ma_cloud_error = ""
        return True
    except (CloudHistoryError, ValueError):
        st.session_state.ma_cloud_error = "Could not delete this chat from your account."
        return False


# --- History state and UI. Guests remain session-only. ---
def new_chat_record() -> dict:
    return {
        "id": uuid.uuid4().hex,
        "title": "New conversation",
        "messages": [],
        "updated": time.time(),
        "engine": make_engine(),
    }


def short_title(text: str) -> str:
    text = " ".join(text.split())
    return text[:42] + ("…" if len(text) > 42 else "") or "New conversation"


def init_state() -> None:
    # A visitor signing in or logging out starts an isolated chat session.
    identity = current_identity()
    if st.session_state.get("ma_identity_v3") != identity:
        erase_session_chats()
        st.session_state.ma_identity_v3 = identity
    if "ma_chats_v2" not in st.session_state:
        # Import session-only history from an earlier version where possible.
        migrated = {}
        old = st.session_state.get("merge_chats")
        engines = st.session_state.get("merge_engines", {})
        if isinstance(old, dict):
            for chat_id, item in list(old.items())[:MAX_CHATS]:
                if not isinstance(item, dict):
                    continue
                migrated[chat_id] = {
                    "id": chat_id,
                    "title": str(item.get("title", "New conversation"))[:60],
                    "messages": list(item.get("messages") or []),
                    "updated": float(item.get("updated", time.time())),
                    "engine": engines.get(chat_id) or make_engine(),
                }
        if migrated:
            st.session_state.ma_chats_v2 = migrated
            active_id = st.session_state.get("merge_active_id")
            st.session_state.ma_active_v2 = (
                active_id if active_id in migrated else next(iter(migrated))
            )
        else:
            record = new_chat_record()
            old_messages = st.session_state.get("messages")
            if isinstance(old_messages, list) and old_messages:
                record["messages"] = list(old_messages)
                first = next(
                    (m.get("content", "") for m in old_messages
                     if isinstance(m, dict) and m.get("role") == "user"), ""
                )
                record["title"] = short_title(first)
                record["engine"] = st.session_state.get("engine") or make_engine()
            st.session_state.ma_chats_v2 = {record["id"]: record}
            st.session_state.ma_active_v2 = record["id"]
    if "ma_web_on" not in st.session_state:
        st.session_state.ma_web_on = True
    if "ma_answer_mode" not in st.session_state:
        st.session_state.ma_answer_mode = "Fast"
    if "ma_request_times" not in st.session_state:
        st.session_state.ma_request_times = []
    cloud_load()


def active_chat() -> dict:
    chats = st.session_state.ma_chats_v2
    chat_id = st.session_state.ma_active_v2
    if chat_id not in chats:
        st.session_state.ma_active_v2 = next(iter(chats))
    return chats[st.session_state.ma_active_v2]


def start_new_chat() -> bool:
    if not active_chat()["messages"]:
        return True
    chats = st.session_state.ma_chats_v2
    if len(chats) >= MAX_CHATS:
        return False
    item = new_chat_record()
    chats[item["id"]] = item
    st.session_state.ma_active_v2 = item["id"]
    return True


def delete_chat(chat_id: str) -> None:
    if not cloud_delete(chat_id):
        return
    chats = st.session_state.ma_chats_v2
    chats.pop(chat_id, None)
    if not chats:
        item = new_chat_record()
        chats[item["id"]] = item
    if st.session_state.ma_active_v2 not in chats:
        st.session_state.ma_active_v2 = max(chats, key=lambda key: chats[key]["updated"])


def append_message(role: str, content: str, sources=None) -> None:
    chat = active_chat()
    chat["messages"].append({
        "role": role,
        "content": content,
        **({"sources": sources} if sources and role == "assistant" else {}),
    })
    chat["updated"] = time.time()
    if role == "user" and sum(m.get("role") == "user" for m in chat["messages"]) == 1:
        chat["title"] = short_title(content)
    # Persist only after a complete user/assistant pair so cloud drafts aren't partial.
    if role == "assistant":
        cloud_save(chat)


def export_history() -> str:
    records = sorted(st.session_state.ma_chats_v2.values(),
                     key=lambda chat: chat["updated"], reverse=True)
    return json.dumps({
        "app": "Merge AI",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "chats": [
            {"title": chat["title"], "messages": chat["messages"]}
            for chat in records if chat["messages"]
        ],
    }, ensure_ascii=False, indent=2)


def show_history() -> None:
    with st.popover("History", use_container_width=True):
        st.markdown("##### Chat history")
        search = st.text_input(
            "Search previous chats", placeholder="Search titles or messages...",
            key="ma_history_search",
        ).strip().casefold()
        items = sorted(st.session_state.ma_chats_v2.values(),
                       key=lambda chat: chat["updated"], reverse=True)
        if search:
            items = [c for c in items if search in c["title"].casefold() or any(
                search in str(m.get("content", "")).casefold() for m in c["messages"]
            )]
        with st.container(height=225, border=False):
            if not items:
                st.caption("No matching conversations.")
            for item in items:
                selected = item["id"] == st.session_state.ma_active_v2
                title = ("● " if selected else "") + item["title"]
                if st.button(title, key="ma_open_" + item["id"],
                             use_container_width=True):
                    st.session_state.ma_active_v2 = item["id"]
                    st.rerun()
        with st.expander("Rename or delete current chat"):
            chat = active_chat()
            name = st.text_input("Chat name", value=chat["title"],
                                 max_chars=60, key="ma_rename_" + chat["id"])
            if st.button("Save name", key="ma_save_name"):
                new_name = " ".join(name.split())[:60]
                if new_name:
                    chat["title"] = new_name
                    cloud_save(chat)
                    st.rerun()
            if st.button("Delete this chat", key="ma_delete_chat"):
                delete_chat(chat["id"])
                st.rerun()
        st.download_button(
            "Download chat backup",
            data=export_history(),
            file_name="merge_ai_chat_history.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption(f"{len(st.session_state.ma_chats_v2)} of {MAX_CHATS} chats. "
                   + ("Signed-in history syncs through Supabase." if cloud_client()
                      else "Guest history lasts only for this browser session."))


def show_sources(sources) -> None:
    if not isinstance(sources, list):
        return
    valid = []
    for item in sources[:8]:
        if not isinstance(item, dict):
            continue
        url = safe_source_url(item.get("url"))
        if url:
            label = str(item.get("title") or urlsplit(url).hostname or "Source")[:90]
            valid.append((label, url))
    if valid:
        with st.expander(f"Research sources ({len(valid)})"):
            for title, url in valid:
                st.link_button(title, url)


# --- Visible UI ---
init_state()
if st.session_state.get("ma_cloud_error"):
    st.warning(st.session_state.ma_cloud_error)
if current_identity() != "guest" and cloud_client() is None:
    st.warning("Cloud history isn't configured. Add SUPABASE_URL and SUPABASE_SECRET_KEY in Streamlit Secrets.")

with st.container(key="ma_brand_account"):
    brand_col, account_col = st.columns([5, 2], gap="small", vertical_alignment="center")
    with brand_col:
        st.markdown(
            '<div class="merge-brand"><div class="merge-mark">M</div>'
            '<div><div class="merge-title">Merge AI</div>'
            '<div class="merge-sub">THINK TOGETHER. ANSWER BETTER.</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with account_col:
        account_controls()
st.markdown('<div class="merge-rule"></div>', unsafe_allow_html=True)

with st.container(key="merge_toolbar"):
    history_col, new_col, options_col = st.columns([1, 1, 1], gap="small")
    with history_col:
        show_history()
    with new_col:
        if st.button("＋ New chat", key="ma_new_chat", use_container_width=True):
            if start_new_chat():
                st.rerun()
            else:
                st.warning("Your chat list is full. Delete an old chat first.")
    with options_col:
        with st.popover("Settings", use_container_width=True):
            st.toggle("Tavily web research", key="ma_web_on")
            st.radio("Answer mode", ("Fast", "Thorough"), key="ma_answer_mode")
            st.caption("Gemini · OpenRouter · Groq")

st.markdown(
    '<div class="merge-section"><strong>Conversation</strong>'
    '<span>Gemini · OpenRouter · Groq · Tavily research</span></div>',
    unsafe_allow_html=True,
)

# Inline composer below a scrollable history area — same placement on mobile.
with st.container(height=420, border=True, key="merge_conversation"):
    chat = active_chat()
    if not chat["messages"]:
        st.markdown(
            '<div class="merge-welcome"><div class="merge-welcome-mark">✦</div>'
            '<h2>What’s on your mind?</h2>'
            '<p>Ask anything. Multiple AI models work together<br>'
            'to produce one thoughtful answer.</p></div>',
            unsafe_allow_html=True,
        )
    else:
        for message in chat["messages"]:
            role = message.get("role", "assistant")
            if role not in ("user", "assistant"):
                continue
            avatar = "👤" if role == "user" else ASSISTANT_AVATAR
            with st.chat_message(role, avatar=avatar):
                st.markdown(str(message.get("content", "")))
                if role == "assistant":
                    show_sources(message.get("sources"))

    # New answer appears here before the rerun updates the history.
    answer_space = st.empty()

# st.chat_input inside a container is inline instead of pinned elsewhere.
with st.container():
    question = st.chat_input(
        "Ask Merge AI anything...", max_chars=MAX_QUESTION_CHARS,
        key="ma_question",
    )

st.markdown(
    '<div class="merge-footnote">One answer from multiple AI models · '
    'Chats sync when signed in and cloud storage is connected</div>',
    unsafe_allow_html=True,
)

if question and question.strip():
    question = question.strip()
    now = time.monotonic()
    st.session_state.ma_request_times = [
        t for t in st.session_state.ma_request_times if now - t < 3600
    ]
    if len(st.session_state.ma_request_times) >= MAX_QUESTIONS_PER_HOUR:
        st.warning("You have reached this session's hourly question limit. Try later.")
    else:
        st.session_state.ma_request_times.append(now)
        with answer_space.container():
            with st.chat_message("user", avatar="👤"):
                st.markdown(question)
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                with st.spinner("Researching and merging an answer..."):
                    try:
                        engine = active_chat()["engine"]
                        result = engine.ask(
                            question,
                            fast=(st.session_state.ma_answer_mode == "Fast"),
                            web_search=st.session_state.ma_web_on,
                        )
                        answer = str(result)
                        sources = engine.last_report.get("sources", [])
                    except Exception:
                        logging.exception("Merge AI request failed")
                        st.error("Sorry, I couldn't complete that answer. Please try again.")
                    else:
                        st.markdown(answer)
                        show_sources(sources)
                        append_message("user", question)
                        append_message("assistant", answer, sources)
                        st.rerun()
