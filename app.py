"""Merge AI | Public Streamlit interface.

Put this file beside merge_ai.py, web_search.py, and interaction.py.
The desktop screen.py does not need to change.
Configure API keys using Streamlit Secrets (never put keys into GitHub).
"""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import urlsplit

import streamlit as st

st.set_page_config(
    page_title="Merge AI | One clearer answer",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from merge_ai import MergeAI, default_providers, safe_source_url


# --- Theme -----------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root {
      --canvas: #faf8f4; --paper: #ffffff; --ink: #183b35;
      --muted: #71817b; --accent: #326957; --accent-hover: #275545;
      --line: #e7ebe4; --soft: #edf4ed;
    }
    html, body, [class*="css"] {font-family: 'DM Sans', sans-serif;}
    [data-testid="stAppViewContainer"], .stApp { background: var(--canvas); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stDecoration"], footer { display: none; }
    div[data-testid="stMainBlockContainer"] {
        max-width: 1030px; padding: 2.0rem 2.2rem 2.5rem;
    }
    h1, h2, h3 { font-family: 'Manrope', sans-serif; }
    /* Header */
    .brand-line {display:flex; gap:14px; align-items:center; padding: 3px 0 23px;}
    .brand-logo {width:47px; height:47px; background:#326957; color:white;
        display:flex; align-items:center; justify-content:center; border-radius:15px;
        font-family:'Manrope',sans-serif; font-size:26px; font-weight:800;
        box-shadow:0 8px 22px rgba(50,105,87,.14);}
    .brand-name {font-family:'Manrope',sans-serif; font-size:25px; font-weight:800;
        letter-spacing:-.8px; line-height:1.1; color:var(--ink);}
    .brand-sub {font-size:12px; letter-spacing:.25px; color:var(--muted); margin-top:5px;}
    .header-rule {border-top:1px solid var(--line); margin: 0 0 18px;}
    /* Chat area replaces the large welcome heading */
    .conversation-label {display:flex; justify-content:space-between;
        align-items:center; margin:12px 0 12px; gap:12px;}
    .conversation-label strong {font-family:'Manrope',sans-serif;
        font-size:15px; color:var(--ink); font-weight:800;}
    .conversation-label span {font-size:12px; color:var(--muted);}
    .empty-chat {min-height:105px; display:flex; flex-direction:column;
        align-items:center; justify-content:center; text-align:center;
        color:var(--ink); font-weight:650; font-size:14px; padding:12px;}
    .empty-chat .empty-sub {font-weight:400; margin-top:9px;
        font-size:12px; color:var(--muted);}
    .chat-caption {font-size:11px; color:var(--muted); text-align:center;
        margin-top:12px;}
    /* Controls */
    .stButton > button {border-radius:11px; font-family:'DM Sans',sans-serif;
        font-size:13px; font-weight:650; border:1px solid #e0e7df;
        background:white; color:var(--ink); min-height:41px;}
    .stButton > button:hover {border-color:var(--accent); color:var(--accent);
        background:#f0f6f0;}
    .stButton > button[kind="primary"] {background:var(--accent); color:white;
        border-color:var(--accent);}
    .stButton > button[kind="primary"]:hover {background:var(--accent-hover); color:white;}
    /* Message cards */
    [data-testid="stChatMessage"] {border:1px solid var(--line);
        background:white; border-radius:17px; padding:16px 18px;
        margin:13px 0; box-shadow: 0 3px 20px rgba(30,66,52,.025);}
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background:#f0f4f0; border-color:#e6ece5;}
    [data-testid="stChatMessageContent"] p {line-height:1.7;}
    /* The input sits directly underneath the chat, not at screen bottom. */
    [data-testid="stChatInput"] {border:1px solid #dbe5d9;
        border-radius:17px; background:#fff;
        box-shadow:0 7px 30px rgba(28,64,49,.075); padding:6px;}
    [data-testid="stChatInput"]:focus-within {border-color:#8bad9b;}
    [data-testid="stChatInput"] textarea {color:var(--ink) !important;
        font-family:'DM Sans',sans-serif; font-size:14px;}
    [data-testid="stChatInput"] button {color:var(--accent) !important;}
    /* Sidebar */
    section[data-testid="stSidebar"] {background:#f5f7f1;
        border-right:1px solid var(--line);}
    section[data-testid="stSidebar"] h2 {color:var(--ink); font-size:20px;}
    .sidebar-note {background:white; border:1px solid var(--line); border-radius:12px;
        padding:12px 14px; font-size:12px; line-height:1.7; color:var(--muted);}
    .sidebar-note strong {color:var(--ink);}
    .status-dot {display:inline-block;width:7px;height:7px;border-radius:50%;
        background:#59a17b;margin-right:7px;vertical-align:middle;}
    @media (max-width: 640px) {
        div[data-testid="stMainBlockContainer"] {padding:1.5rem 1rem 2rem;}
        .brand-logo {width:40px;height:40px;font-size:22px;}
        .brand-name {font-size:21px;}
        .brand-sub {font-size:11px;}
        [data-testid="stChatMessage"] {padding:11px;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Secrets: server only, never displayed to public visitors ---------------
def secret_value(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        # Streamlit also works locally before secrets are configured.
        return ""


for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "TAVILY_API_KEY"):
    key = secret_value(name)
    if key and not os.environ.get(name):
        os.environ[name] = key


# --- One MergeAI conversation per visitor ----------------------------------
if "engine" not in st.session_state:
    st.session_state.engine = MergeAI(
        providers=default_providers(),
        tavily_api_key=os.environ.get("TAVILY_API_KEY", ""),
    )
if "messages" not in st.session_state:
    st.session_state.messages = []
if "request_times" not in st.session_state:
    st.session_state.request_times = []


# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    st.markdown("## Merge AI settings")
    web_enabled = st.toggle(
        "Tavily web research", value=True,
        help="Search the web for factual information using Tavily.",
    )
    mode = st.radio(
        "Answer mode", ["Fast", "Thorough"], index=0,
        help="Thorough can take longer and use more API tokens.",
    )
    st.divider()
    st.markdown(
        '<div class="sidebar-note"><strong>Three AI perspectives</strong><br>'
        'Gemini · OpenRouter · Groq<br><br>'
        '<strong>Private by design</strong><br>'
        'API keys stay on the server. Each visitor has a separate chat session.</div>',
        unsafe_allow_html=True,
    )
    st.caption("Made for Khalid’s science fair project")


# --- Branded header ---------------------------------------------------------
header_col, new_chat_col = st.columns([5, 1.15], vertical_alignment="center")
with header_col:
    st.markdown(
        '<div class="brand-line">'
        '<div class="brand-logo">M</div>'
        '<div><div class="brand-name">Merge AI</div>'
        '<div class="brand-sub">THINK TOGETHER. ANSWER BETTER.</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
with new_chat_col:
    if st.button("＋ New chat", use_container_width=True, key="new_chat"):
        st.session_state.engine.clear_history()
        st.session_state.messages = []
        st.rerun()
st.markdown('<div class="header-rule"></div>', unsafe_allow_html=True)


# --- Chat history -----------------------------------------------------------
def show_sources(sources: object) -> None:
    if not isinstance(sources, list):
        return
    safe_sources = []
    for source in sources[:6]:
        if not isinstance(source, dict):
            continue
        url = safe_source_url(source.get("url"))
        if url:
            hostname = urlsplit(url).hostname or "Source"
            safe_sources.append((str(source.get("title") or hostname)[:90], url))
    if safe_sources:
        with st.expander(f"Research sources · {len(safe_sources)}"):
            for title, url in safe_sources:
                st.link_button(title, url)


# --- Actual conversation occupies the former welcome section --------------
st.markdown(
    '<div class="conversation-label"><strong>Conversation</strong>'
    '<span>Gemini · OpenRouter · Groq · Tavily research</span></div>',
    unsafe_allow_html=True,
)

# A nested chat_input renders inline, so it is below the conversation panel.
# When chat is empty, the small panel and input sit near the middle of the page.
# After the first question, the panel grows and keeps earlier messages scrollable.
with st.container():
    panel_height = 440 if st.session_state.messages else 150
    with st.container(height=panel_height, border=True):
        if not st.session_state.messages:
            st.markdown(
                '<div class="empty-chat">Your Merge AI chat goes here'
                '<div class="empty-sub">Type a question below to begin.</div></div>',
                unsafe_allow_html=True,
            )
        for message in st.session_state.messages:
            role = message.get("role", "assistant")
            with st.chat_message(role, avatar="👤" if role == "user" else "🤖"):
                st.markdown(message["content"])
                if role == "assistant":
                    show_sources(message.get("sources", []))

        # Reserve a spot *inside* the message panel for the new exchange.
        latest_reply = st.empty()

    question = st.chat_input(
        "Ask Merge AI anything...", max_chars=1000, key="merge_chat_input",
    )

st.markdown(
    '<div class="chat-caption">Multiple AI perspectives · One thoughtful answer</div>',
    unsafe_allow_html=True,
)


# --- Composer and request limits --------------------------------------------
if question and question.strip():
    question = question.strip()
    now = time.monotonic()
    recent = [t for t in st.session_state.request_times if now - t < 3600]
    st.session_state.request_times = recent

    if len(recent) >= 20:
        with latest_reply.container():
            st.warning("This browser session has reached its hourly question limit. Please try again later.")
    else:
        # Count attempted calls too, to protect free API limits.
        st.session_state.request_times.append(now)
        st.session_state.messages.append({"role": "user", "content": question})
        with latest_reply.container():
            with st.chat_message("user", avatar="👤"):
                st.markdown(question)

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Preparing your merged answer..."):
                    try:
                        answer = st.session_state.engine.ask(
                            question,
                            fast=(mode == "Fast"),
                            web_search=web_enabled,
                        )
                        sources = st.session_state.engine.last_report.get("sources", [])
                        if not isinstance(sources, list):
                            sources = []
                    except Exception:
                        logging.exception("Merge AI request failed")
                        answer = "Sorry, I couldn't complete that answer right now. Please try again."
                        sources = []
                st.markdown(answer)
                show_sources(sources)

        st.session_state.messages.append({
            "role": "assistant", "content": answer, "sources": sources,
        })
        # Rerun so the message area grows after the first turn and displays
        # the completed conversation consistently in the same panel.
        st.rerun()
