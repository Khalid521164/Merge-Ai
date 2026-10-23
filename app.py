"""Merge AI — responsive Streamlit chat screen with session-only chat history.

Keep this file next to chat_history.py, merge_ai.py, interaction.py,
web_search.py, and merge_ai_favicon.png. Existing desktop files are unchanged.
API keys belong in Streamlit Cloud > App settings > Secrets, never GitHub.
"""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlsplit

import streamlit as st

st.set_page_config(
    page_title="Merge AI | Think together. Answer better.",
    page_icon="merge_ai_favicon.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from merge_ai import MergeAI, default_providers, safe_source_url
from chat_history import (
    active_chat,
    active_engine,
    add_message,
    create_chat,
    history_popover,
    init_history,
    MAX_CHATS,
)

# The page deliberately uses the same brand, toolbar and message layout at
# all viewport sizes. Narrow screens reduce spacing instead of replacing the UI.
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root {
  --cream: #faf8f4; --white: #fff; --green: #326957;
  --forest: #183b35; --muted: #6e8079; --line: #e0e9df;
  --mist: #eff5ef;
}
html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--cream) !important;
    font-family: 'DM Sans', sans-serif;
}
[data-testid="stHeader"] {background: transparent !important;}
[data-testid="stDecoration"], footer {display:none;}
[data-testid="stMainBlockContainer"] {
    width: 100% !important;
    max-width: 990px !important;
    padding: 1.65rem clamp(0.75rem, 3.2vw, 2rem) 2rem !important;
}
h1, h2, h3 {font-family:'Manrope',sans-serif;}
.brand-wrap {display:flex; align-items:center; gap:14px; margin-bottom: 6px;}
.brand-icon {
    width:45px;height:45px;border-radius:14px;background:var(--green);
    color:white;display:flex;align-items:center;justify-content:center;
    font:800 24px 'Manrope',sans-serif;
    box-shadow:0 8px 24px rgba(50,105,87,.16);flex:none;
}
.brand-main {font:800 clamp(21px,4.4vw,27px)/1.1 'Manrope',sans-serif;
    letter-spacing:-.8px;color:var(--forest);}
.brand-sub {font-size:10px;color:var(--muted);letter-spacing:.08em;
    margin-top:6px;white-space:normal;}
.brand-rule {height:1px;background:var(--line);margin:14px 0 10px;}
.st-key-merge_toolbar [data-testid="stHorizontalBlock"] {
    flex-wrap:nowrap !important;gap:.5rem !important;align-items:center;
}
.st-key-merge_toolbar [data-testid="column"] {min-width:0 !important;}
.st-key-merge_toolbar .stButton button,
.st-key-merge_toolbar [data-testid="stPopover"] button {
    min-height:40px !important;
}
.stButton > button, [data-testid="stPopover"] > button {
    border: 1px solid var(--line) !important;
    background:white !important;
    color:var(--forest) !important;
    border-radius:12px !important;
    font-family:'DM Sans',sans-serif !important;
    font-size:13px !important;font-weight:700 !important;
    transition:background .15s ease,border-color .15s ease;
}
.stButton > button:hover, [data-testid="stPopover"] > button:hover {
    background:var(--mist) !important;
    border-color:#a6bcac !important;
    color:var(--green) !important;
}
.toolbar-hint {text-align:right;line-height:1.2;color:var(--muted);
    font-size:11px;padding-top:10px;}
.section-label {display:flex;align-items:baseline;gap:12px;
    margin:16px 0 12px;}
.section-label strong {font:800 15px 'Manrope',sans-serif;color:var(--forest);}
.section-label span {font-size:11px;color:var(--muted);overflow-wrap:anywhere;}
.st-key-conversation_panel {
    border-color:var(--line) !important;
    background:#fff !important;
    border-radius:20px !important;
    box-shadow:0 6px 35px rgba(29,65,54,.035);
}
[data-testid="stChatMessage"] {
    background:#fff !important;
    border:1px solid var(--line);
    border-radius:15px;padding:14px 15px;margin:8px 0;
    box-shadow:0 3px 12px rgba(40,75,60,.025);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background:#f1f6f1 !important;
}
[data-testid="stChatMessageContent"] {min-width:0;overflow-wrap:anywhere;}
[data-testid="stChatMessageContent"] p {line-height:1.65;}
.chat-empty {text-align:center;padding:82px 10px 52px;color:var(--forest);}
.chat-empty .empty-mark {
    width:46px;height:46px;background:var(--mist);color:var(--green);
    font-size:26px;font-weight:800;border-radius:15px;
    display:grid;place-items:center;margin:0 auto 20px;
}
.chat-empty h2 {font:800 clamp(19px,4.8vw,26px) 'Manrope',sans-serif;
    letter-spacing:-.5px;margin:0 0 8px;}
.chat-empty p {font-size:13px;color:var(--muted);line-height:1.7;margin:0;}
[data-testid="stChatInput"] {
    background:#fff !important;border-radius:16px !important;
    border:1px solid #cbdcd1 !important;
    box-shadow:0 6px 28px rgba(31,67,51,.065) !important;
}
[data-testid="stChatInput"] textarea {
    font-family:'DM Sans',sans-serif !important;color:var(--forest) !important;
    font-size:14px !important;
}
[data-testid="stChatInput"] button {color:var(--green) !important;}
.composer-caption {text-align:center;color:var(--muted);font-size:11px;
    margin:10px 0 0;}
@media(max-width:640px) {
  [data-testid="stMainBlockContainer"] {padding:1rem .7rem 1.4rem !important;}
  .brand-wrap {gap:10px;}
  .brand-icon {width:40px;height:40px;font-size:23px;border-radius:12px;}
  .brand-sub {font-size:9px;}
  .brand-rule {margin:12px 0 7px;}
  .st-key-merge_toolbar [data-testid="stHorizontalBlock"] {gap:.35rem !important;}
  .st-key-merge_toolbar .stButton button,
  .st-key-merge_toolbar [data-testid="stPopover"] button {
      min-height:39px !important;font-size:12px !important;padding:0 .35rem !important;
  }
  [data-testid="stChatMessage"] {padding:10px;margin:6px 0;border-radius:13px;}
  .section-label {margin-top:13px;}
  .section-label span {font-size:10px;}
  .chat-empty {padding:48px 6px 34px;}
}
</style>
    """,
    unsafe_allow_html=True,
)


def secret_value(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


# Keys are read on the server and never embedded into page HTML or JSON.
for secret_name in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY"):
    value = secret_value(secret_name)
    if value and not os.environ.get(secret_name):
        os.environ[secret_name] = value


def make_engine() -> MergeAI:
    return MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
    )


init_history(make_engine)
if "merge_request_times" not in st.session_state:
    st.session_state.merge_request_times = []
if "merge_web_enabled" not in st.session_state:
    st.session_state.merge_web_enabled = True
if "merge_answer_mode" not in st.session_state:
    st.session_state.merge_answer_mode = "Fast"


# Consistent header on ALL devices (same toolbar, no mobile-only replacement).
st.markdown(
    '<div class="brand-wrap"><div class="brand-icon">M</div>'
    '<div><div class="brand-main">Merge AI</div>'
    '<div class="brand-sub">THINK TOGETHER. ANSWER BETTER.</div></div></div>'
    '<div class="brand-rule"></div>',
    unsafe_allow_html=True,
)

with st.container(key="merge_toolbar"):
    history_col, new_col, settings_col = st.columns([1, 1, 1], gap="small")
    with history_col:
        history_popover(make_engine)
    with new_col:
        if st.button("＋ New chat", use_container_width=True, key="merge_new_chat"):
            if not create_chat(make_engine):
                st.warning(f"You have reached {MAX_CHATS} chats. Delete an old chat to create another.")
            else:
                st.rerun()
    with settings_col:
        with st.popover("Settings", use_container_width=True):
            st.markdown("##### Answer settings")
            st.toggle("Tavily web research", key="merge_web_enabled")
            st.radio("Answer mode", ["Fast", "Thorough"], key="merge_answer_mode")
            st.caption("Gemini · OpenRouter · Groq")

# Current conversation and composer are always in the same locations.
current_chat = active_chat()
st.markdown(
    '<div class="section-label"><strong>Conversation</strong>'
    '<span>Gemini · OpenRouter · Groq · optional Tavily research</span></div>',
    unsafe_allow_html=True,
)


def show_sources(sources: object) -> None:
    if not isinstance(sources, list):
        return
    safe = []
    for source in sources[:6]:
        if not isinstance(source, dict):
            continue
        url = safe_source_url(source.get("url"))
        if url:
            name = (source.get("title") or urlsplit(url).hostname or "Source")
            safe.append((str(name)[:85], url))
    if safe:
        with st.expander(f"Research sources ({len(safe)})"):
            for name, url in safe:
                st.link_button(name, url)


with st.container(height=420, border=True, key="conversation_panel"):
    if not current_chat["messages"]:
        st.markdown(
            '<div class="chat-empty"><div class="empty-mark">✦</div>'
            '<h2>What’s on your mind?</h2>'
            '<p>Ask a question and Merge AI will combine multiple AI perspectives<br>'
            'into one clear response.</p></div>',
            unsafe_allow_html=True,
        )
    else:
        for message in current_chat["messages"]:
            role = message.get("role", "assistant")
            with st.chat_message(role, avatar="👤" if role == "user" else "merge_ai_favicon.png"):
                st.markdown(str(message.get("content", "")))
                if role == "assistant":
                    show_sources(message.get("sources", []))
    latest_response = st.empty()

# Inside a container, chat_input stays inline (not differently docked on mobile).
with st.container():
    question = st.chat_input("Ask Merge AI anything...", max_chars=1000, key="merge_prompt")

st.markdown(
    '<div class="composer-caption">One thoughtful answer from multiple models · '
    'Chats are private to this browser session</div>',
    unsafe_allow_html=True,
)

if question and question.strip():
    now = time.monotonic()
    st.session_state.merge_request_times = [
        t for t in st.session_state.merge_request_times if now - t < 3600
    ]
    if len(st.session_state.merge_request_times) >= 20:
        st.warning("This browser session reached its hourly question limit. Try again later.")
    else:
        st.session_state.merge_request_times.append(now)
        add_message("user", question.strip())
        succeeded = False
        with latest_response.container():
            with st.chat_message("user", avatar="👤"):
                st.markdown(question)
            with st.chat_message("assistant", avatar="merge_ai_favicon.png"):
                with st.spinner("Researching and merging your answer..."):
                    try:
                        answer = active_engine().ask(
                            question.strip(),
                            fast=(st.session_state.merge_answer_mode == "Fast"),
                            web_search=st.session_state.merge_web_enabled,
                        )
                        sources = active_engine().last_report.get("sources", [])
                        if not isinstance(sources, list):
                            sources = []
                    except Exception:
                        logging.exception("Merge AI request failed")
                        # Failed questions aren't treated as successful conversation
                        # turns by the backend; keep the frontend history in sync.
                        active_chat()["messages"].pop()
                        st.error("I couldn't finish that answer. Please try again.")
                    else:
                        st.markdown(answer)
                        show_sources(sources)
                        add_message("assistant", answer, sources)
                        succeeded = True
        if succeeded:
            st.rerun()
