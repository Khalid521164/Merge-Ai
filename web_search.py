"""Merge AI — science fair website screen.

Run locally:
    python -m streamlit run web_app.py

This file deliberately includes the *website UI only*. The real AI backend
must be connected after inspecting the existing merge_ai.py source, so that no
function names, model IDs, or API behavior are guessed.
"""

from __future__ import annotations

import hmac
import logging
import time
from datetime import datetime
from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# Basic page settings
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Merge AI · Tavily",
    page_icon="🟢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAX_QUESTION_LENGTH = 1000
MAX_QUESTIONS_PER_HOUR = 20
LOGGER = logging.getLogger("merge_ai_web")


class BackendNotConnected(Exception):
    """The existing Merge AI Python backend has not been wired to the web UI."""


def ask_merge_ai(
    question: str,
    use_tavily: bool,
    response_mode: str,
) -> tuple[str, list[dict[str, str]]]:
    """Connect the *real* merge_ai.py here after we see its actual functions.

    Future return format:
        ("The merged answer", [{"title": "Page", "url": "https://..."}])

    API credentials belong in Streamlit Secrets, never in this file or GitHub.
    """
    raise BackendNotConnected("AI backend is not connected to the web screen yet")


def read_secret(name: str) -> str:
    """Read a server-side secret, or return an empty string if none exists."""
    try:
        value = st.secrets.get(name, "")
        return str(value).strip() if value is not None else ""
    except Exception:
        return ""


def start_new_chat() -> None:
    """Clear only this visitor's conversation."""
    st.session_state.messages = []
    st.session_state.draft = ""


def use_suggestion(text: str) -> None:
    st.session_state.draft = text


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning."
    if hour < 18:
        return "Good afternoon."
    return "Good evening."


def is_safe_source_url(url: str) -> bool:
    """Reject non-web links in eventual model-supplied source lists."""
    return url.startswith("https://") or url.startswith("http://")


# ---------------------------------------------------------------------------
# Page design: closely follows the provided beige / dark green reference
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
:root {
    --merge-cream: #F7F5EF;
    --merge-ink: #15372F;
    --merge-muted: #82928E;
    --merge-green: #466F5E;
    --merge-pale: #E8EFE8;
    --merge-line: #DEDCD5;
}
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: var(--merge-cream) !important;
    color: var(--merge-ink);
}
[data-testid="stHeader"] {
    background: transparent !important;
}
[data-testid="stMainBlockContainer"], .block-container {
    max-width: 100% !important;
    padding: 18px 30px 70px !important;
}
* { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }

.merge-brand {
    display: flex;
    align-items: center;
    gap: 14px;
    height: 57px;
}
.merge-logo {
    background: #3D7765;
    color: white;
    border-radius: 50%;
    width: 39px;
    height: 39px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 800;
    font-family: Georgia, serif;
}
.merge-brandname {
    color: var(--merge-ink);
    font-size: 25px;
    font-weight: 750;
    letter-spacing: -0.5px;
}
.merge-rule {
    width: 100%;
    height: 1px;
    background: var(--merge-line);
    margin-top: 4px;
}
.merge-hero {
    margin-top: clamp(85px, 19vh, 185px);
    text-align: center;
    margin-bottom: 26px;
}
.merge-greeting {
    color: #7B8F8A;
    font-size: 19px;
    font-weight: 400;
    margin-bottom: 14px;
}
.merge-hero h1 {
    color: var(--merge-ink);
    font-size: clamp(30px, 3vw, 39px);
    line-height: 1.15;
    font-weight: 760;
    margin: 0 0 18px;
    letter-spacing: -1px;
}
.merge-subtitle {
    color: #82928E;
    font-size: 15px;
}
.merge-chat-title {
    text-align: center;
    margin: 36px auto 25px;
    color: var(--merge-ink);
    font-size: 24px;
    font-weight: 700;
}
.merge-footline {
    display: flex;
    justify-content: space-between;
    color: #7F918C;
    font-size: 12px;
    margin: 8px 3px 14px;
}
.merge-chip-hint {
    text-align: center;
    color: #84938E;
    font-size: 12px;
    margin-top: 15px;
}
/* Composer frame */
[data-testid="stForm"] {
    border: 1px solid #DADBD4 !important;
    border-radius: 0 !important;
    padding: 10px 13px !important;
    background: white !important;
    box-shadow: none !important;
}
[data-testid="stForm"] [data-testid="stTextArea"] textarea {
    background: white !important;
    color: var(--merge-ink) !important;
    border: none !important;
    border-radius: 0 !important;
    outline: none !important;
    box-shadow: none !important;
    padding: 7px 1px !important;
    min-height: 65px !important;
    font-size: 15px !important;
    resize: none !important;
}
[data-testid="stForm"] [data-testid="stTextArea"] textarea::placeholder {
    color: #8B9894 !important;
}
[data-testid="stFormSubmitButton"] button,
[data-testid="stForm"] button[kind="primary"] {
    background: var(--merge-green) !important;
    color: white !important;
    border-radius: 0 !important;
    border: none !important;
    font-size: 13px !important;
    font-weight: 650 !important;
    min-height: 42px !important;
    margin-top: 16px !important;
}
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stForm"] button[kind="primary"]:hover {
    background: #365D4D !important;
}
/* Settings popover (Tavily status chip) */
[data-testid="stPopover"] > button {
    background: var(--merge-pale) !important;
    color: #365E4D !important;
    border: none !important;
    border-radius: 0 !important;
    min-height: 32px !important;
    padding: 4px 12px !important;
    font-size: 12px !important;
    box-shadow: none !important;
}
/* Quick prompt and new-chat buttons */
[data-testid="stButton"] button[kind="secondary"] {
    background: var(--merge-pale);
    color: #274D40;
    border: none;
    border-radius: 0;
    box-shadow: none;
    font-size: 12px;
    min-height: 39px;
}
[data-testid="stButton"] button[kind="secondary"]:hover {
    background: #DCE8DC;
    color: #244B3D;
}
/* Conversation */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.72);
    border: 1px solid #E5E2DA;
    border-radius: 8px;
    margin-bottom: 10px;
}
[data-testid="stChatMessage"] p { color: var(--merge-ink); }
[data-testid="stChatMessageAvatarAssistant"] {
    background: var(--merge-green) !important;
}
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"], .block-container {
        padding: 15px 14px 40px !important;
    }
    .merge-brandname { font-size: 20px; }
    .merge-logo { height: 33px; width: 33px; font-size: 19px; }
    .merge-hero { margin-top: 75px; margin-bottom: 27px; }
    .merge-hero h1 { font-size: 29px; }
    .merge-subtitle { font-size: 13px; }
    .merge-footline { font-size: 10px; }
    [data-testid="stForm"] { padding: 8px !important; }
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Visitor state and optional shared-access password
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "draft" not in st.session_state:
    st.session_state.draft = ""
if "tavily_enabled" not in st.session_state:
    st.session_state.tavily_enabled = True
if "response_mode" not in st.session_state:
    st.session_state.response_mode = "Fast"
if "question_times" not in st.session_state:
    st.session_state.question_times = []

site_password = read_secret("APP_PASSWORD")
if site_password and not st.session_state.get("authorized", False):
    st.markdown(
        '<div class="merge-brand"><div class="merge-logo">M</div>'
        '<div class="merge-brandname">Merge AI</div></div>',
        unsafe_allow_html=True,
    )
    st.subheader("Enter the Science Fair access password")
    with st.form("access_form"):
        attempt = st.text_input("Password", type="password")
        unlocked = st.form_submit_button("Enter website", type="primary")
    if unlocked:
        if hmac.compare_digest(attempt, site_password):
            st.session_state.authorized = True
            st.rerun()
        else:
            st.error("That password is not correct.")
    st.stop()


# ---------------------------------------------------------------------------
# Top navigation
# ---------------------------------------------------------------------------

brand_col, new_chat_col = st.columns([8, 1])
with brand_col:
    st.markdown(
        '<div class="merge-brand"><div class="merge-logo">M</div>'
        '<div class="merge-brandname">Merge AI</div></div>',
        unsafe_allow_html=True,
    )
with new_chat_col:
    st.button("＋ New chat", key="new_chat", on_click=start_new_chat, use_container_width=True)
st.markdown('<div class="merge-rule"></div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Home greeting or existing conversation
# ---------------------------------------------------------------------------

if not st.session_state.messages:
    st.markdown(
        f"""
        <div class="merge-hero">
            <div class="merge-greeting">{greeting()}</div>
            <h1>What's on your mind?</h1>
            <div class="merge-subtitle">A question, an idea, or something to figure out together.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown('<div class="merge-chat-title">Merge AI</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chat and centered composer
# ---------------------------------------------------------------------------

left_side, main_area, right_side = st.columns([1, 3, 1], gap="small")
with main_area:
    if st.session_state.messages:
        for item in st.session_state.messages:
            role = item.get("role", "assistant")
            with st.chat_message(role, avatar="🟢" if role == "assistant" else "👤"):
                st.markdown(item.get("content", ""))
                sources = item.get("sources", [])
                if sources:
                    st.caption("Sources")
                    for source in sources:
                        url = str(source.get("url", ""))
                        title = str(source.get("title", "Source"))
                        if is_safe_source_url(url):
                            st.link_button(title, url, use_container_width=False)

    with st.popover(
        f"Tavily web research · {'On' if st.session_state.tavily_enabled else 'Off'}  ⚙"
    ):
        st.toggle("Use Tavily web research", key="tavily_enabled")
        st.radio("Response mode", ["Fast", "Thorough"], key="response_mode")
        st.caption("The AI engine will use these settings after it is connected.")

    with st.form("merge_message_form", clear_on_submit=True, border=True):
        compose_col, send_col = st.columns([8, 1], gap="small")
        with compose_col:
            question = st.text_area(
                "Ask Merge AI",
                key="draft",
                placeholder="Message Merge AI...",
                label_visibility="collapsed",
                height=72,
                max_chars=MAX_QUESTION_LENGTH,
            )
        with send_col:
            submitted = st.form_submit_button("Send ↑", type="primary", use_container_width=True)

    st.markdown(
        '<div class="merge-footline"><span>Ready</span>'
        '<span>Click Send or press Ctrl+Enter</span></div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.messages:
        quick_left, chip1, chip2, chip3, quick_right = st.columns([1, 2, 1.65, 1.45, 1])
        with chip1:
            st.button(
                "Explain something",
                key="suggest_explain",
                on_click=use_suggestion,
                args=("Explain how artificial intelligence works.",),
                use_container_width=True,
            )
        with chip2:
            st.button(
                "Help me write",
                key="suggest_write",
                on_click=use_suggestion,
                args=("Help me write a science fair project introduction.",),
                use_container_width=True,
            )
        with chip3:
            st.button(
                "Build an idea",
                key="suggest_idea",
                on_click=use_suggestion,
                args=("Help me brainstorm an invention for science fair.",),
                use_container_width=True,
            )

    # The current deliverable is the website screen. After Khalid provides
    # merge_ai.py, this handler will call its *verified* public function.
    if submitted:
        clean_question = question.strip()
        if not clean_question:
            st.warning("Type a question first.")
        else:
            now = time.time()
            st.session_state.question_times = [
                t for t in st.session_state.question_times if now - t < 3600
            ]
            if len(st.session_state.question_times) >= MAX_QUESTIONS_PER_HOUR:
                st.warning("This browser has reached 20 questions this hour. Try again later.")
            else:
                st.session_state.question_times.append(now)
                st.session_state.messages.append(
                    {"role": "user", "content": clean_question}
                )
                try:
                    with st.spinner("Merge AI is working..."):
                        reply, sources = ask_merge_ai(
                            question=clean_question,
                            use_tavily=st.session_state.tavily_enabled,
                            response_mode=st.session_state.response_mode,
                        )
                except BackendNotConnected:
                    reply = (
                        "The website screen is ready, but my AI engine is not "
                        "connected yet. Next, connect the real `merge_ai.py` "
                        "backend to make responses work."
                    )
                    sources = []
                except Exception:
                    LOGGER.exception("Merge AI processing failed")
                    reply = "Sorry, Merge AI couldn't answer that. Please try again."
                    sources = []
                st.session_state.messages.append(
                    {"role": "assistant", "content": reply, "sources": sources}
                )
                st.rerun()
