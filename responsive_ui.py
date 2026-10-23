"""Merge AI's shared phone, tablet, and desktop interface.

Run with: python -m streamlit run app.py
CSS adapts native Streamlit containers; HTML wrappers never span widget calls.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
from dataclasses import replace
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from account_info import (Account, AccountError, clear_private_state, display_name,
                          is_configured, render_account_info, render_sign_in, setting)
from chat_history import (ChatHistory, HistoryError, can_retry, export_chat,
                          new_id, restore_engine)


CSS = """
<style>
:root {--canvas:#faf8f4;--paper:#fff;--ink:#183b35;--muted:#64756c;
       --accent:#326957;--line:#e0e7df;--soft:#edf3eb; color-scheme:light;}
.stApp,[data-testid="stAppViewContainer"] {background:var(--canvas);color:var(--ink);}
html,body,.stApp,input,button,textarea {font-family:Inter,"Segoe UI",Arial,sans-serif;}
[data-testid="stHeader"] {background:rgba(250,248,244,.96);}
[data-testid="stDecoration"],footer {display:none;}
[data-testid="stMainBlockContainer"] {max-width:1000px;padding:2rem clamp(1rem,4vw,3rem) 3rem;}
[data-testid="stSidebar"] {background:#f1f4ed;border-right:1px solid var(--line);}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-bottom:1rem;}
.ma-brand {display:flex;align-items:center;gap:12px;margin:0 0 18px;}
.ma-mark {display:grid;place-items:center;width:43px;height:43px;border-radius:14px;
          background:var(--accent);color:white;font-size:25px;font-weight:800;flex-shrink:0;}
.ma-name {font-weight:750;letter-spacing:-.7px;font-size:23px;color:var(--ink);}
.ma-sub {font-size:11px;letter-spacing:1px;color:var(--muted);}
.ma-header {display:flex;gap:12px;align-items:center;justify-content:space-between;
            border-bottom:1px solid var(--line);padding:0 0 14px;margin-bottom:14px;}
.ma-header .ma-brand {margin:0;}
.ma-badge {font-size:11px;color:var(--accent);padding:7px 11px;border:1px solid #cfded0;
           border-radius:20px;white-space:nowrap;background:#f1f6ef;}
.ma-intro {padding:clamp(1.5rem,7vh,5rem) 0 2rem;max-width:640px;margin:auto;}
.ma-eyebrow {color:var(--accent);font-size:11px;font-weight:700;letter-spacing:2px;}
.ma-intro h1 {font-family:Georgia,serif;font-size:clamp(29px,4.2vw,47px);line-height:1.15;
              font-weight:500;letter-spacing:-1px;color:var(--ink);margin:16px 0;}
.ma-intro p {max-width:440px;font-size:15px;line-height:1.7;color:var(--muted);}
.ma-chips {display:flex;flex-wrap:wrap;gap:8px;margin-top:23px;}
.ma-chips span {background:white;border:1px solid var(--line);font-size:11px;
                border-radius:7px;padding:6px 10px;color:var(--muted);}
[data-testid="stHeading"] h1,[data-testid="stHeading"] h2,[data-testid="stHeading"] h3 {color:var(--ink);}
[data-testid="stMarkdownContainer"] {color:var(--ink);overflow-wrap:anywhere;}
[data-testid="stCaptionContainer"] p {color:var(--muted);}
[data-testid="stCaption"] {color:var(--muted);}
[data-testid="stChatMessage"] {background:white;border:1px solid var(--line);border-radius:16px;
                               margin:10px 0;padding:18px;min-width:0;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {background:#edf3eb;}
[data-testid="stChatMessageAvatarUser"] {background:#326957;color:white;}
[data-testid="stChatMessageContent"] {min-width:0;max-width:100%;}
[data-testid="stChatMessageContent"] p {line-height:1.75;}
pre {max-width:100%;overflow-x:auto!important;}
[data-testid="stTable"],[data-testid="stDataFrame"] {max-width:100%;overflow-x:auto;}
[data-testid="stBottom"],[data-testid="stBottomBlockContainer"] {background:var(--canvas);}
[data-testid="stBottomBlockContainer"] {max-width:1000px;margin:auto;
  padding-left:clamp(1rem,4vw,3rem);padding-right:clamp(1rem,4vw,3rem);
  padding-bottom:max(1rem,env(safe-area-inset-bottom));}
[data-testid="stChatInput"] {border:1px solid #c9d8cb;border-radius:17px;background:white;
 box-shadow:0 5px 22px #1c40310d;}
[data-testid="stChatInput"] textarea {color:var(--ink);font-size:16px;}
[data-testid="stChatInput"]:focus-within {border-color:var(--accent);}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button {
 min-height:44px;border-radius:10px;border:1px solid #d5dfd4;background:white;color:var(--ink);}
.stButton>button:hover,.stFormSubmitButton>button:hover {border-color:var(--accent);color:var(--accent);}
button[kind="primary"],.stFormSubmitButton button[kind="primaryFormSubmit"] {
 background:var(--accent)!important;color:white!important;border-color:var(--accent)!important;}
button[kind="primary"] *,button[kind="primaryFormSubmit"] * {color:white!important;}
button:focus-visible,textarea:focus-visible,input:focus-visible {outline:2px solid #608d71!important;outline-offset:3px;}
.st-key-account_form {max-width:560px;margin:1rem auto;background:white;border-radius:18px;}
.st-key-history_list button {text-align:left;font-size:13px;}
.st-key-history_list button p {overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:210px;}
[data-testid="stTextInput"] input {font-size:16px;}
.ma-progress {display:flex;align-items:center;gap:10px;color:var(--muted);font-size:13px;padding:8px 0;}
.ma-progress i {width:8px;height:8px;background:#326957;border-radius:50%;animation:ma-pulse 1.2s ease-in-out infinite;}
@keyframes ma-pulse {50%{opacity:.3;transform:scale(.7);}}
@media(prefers-reduced-motion:reduce){.ma-progress i{animation:none;}}
@media(max-width:768px){
 [data-testid="stMainBlockContainer"] {padding-top:4.5rem;}
 .ma-sub {letter-spacing:.5px;font-size:10px;}
 .ma-badge {display:none;}
 [data-testid="stChatMessage"] {padding:12px;gap:10px;}
 .ma-intro {padding-top:2rem;}
 .st-key-account_form {margin:0;}
}
</style>
"""


def brand() -> str:
    return ('<div class="ma-brand"><div class="ma-mark">M</div><div>'
            '<div class="ma-name">Merge AI</div><div class="ma-sub">THINK TOGETHER. ANSWER BETTER.</div></div></div>')


def build_engine(turns: list[dict]):
    # Read server secrets directly, without changing process-wide environment
    # variables or placing provider keys into browser widgets.
    from merge_ai import MergeAI, default_providers
    providers = tuple(replace(p,
        api_key=setting(f"{p.name.upper()}_API_KEY", p.api_key),
        model=setting(f"{p.name.upper()}_MODEL", p.model),
    ) for p in default_providers())
    engine = MergeAI(providers=providers, tavily_api_key=setting("TAVILY_API_KEY"))
    restore_engine(engine, turns)
    return engine


def clean_sources(sources: object) -> list[dict]:
    from merge_ai import safe_source_url
    cleaned, seen = [], set()
    for source in sources if isinstance(sources, list) else []:
        if not isinstance(source, dict):
            continue
        url = safe_source_url(source.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        cleaned.append({"title": str(source.get("title") or urlsplit(url).hostname)[:140], "url": url})
        if len(cleaned) == 6:
            break
    return cleaned


def show_sources(sources: object, *, expanded: bool = False) -> None:
    items = clean_sources(sources)
    if items:
        with st.expander(f"Sources · {len(items)}", expanded=expanded):
            for item in items:
                st.link_button(item["title"], item["url"])


def run_engine(question: str, turns: list[dict]) -> tuple[str, list]:
    """Only the script thread touches Streamlit; worker callbacks use a queue."""
    engine = build_engine(turns)
    cancel = threading.Event()
    events = queue.Queue(maxsize=100)
    result = queue.Queue(maxsize=1)

    def on_progress(event):
        try:
            events.put_nowait(event)
        except queue.Full:
            pass

    def work():
        try:
            answer = engine.ask(question, cancel, fast=True,
                web_search=bool(engine.tavily_api_key), on_progress=on_progress)
            result.put((answer, clean_sources(engine.last_report.get("sources", []))))
        except Exception as exc:
            # Log a class name only, not prompts, keys, or provider response bodies.
            logging.warning("Merge AI generation failed: %s", type(exc).__name__)
            result.put(None)

    worker = threading.Thread(target=work, daemon=True)
    progress = st.empty()
    worker.start()
    phase, sources = "Preparing your answer", []
    try:
        while worker.is_alive():
            try:
                event = events.get(timeout=.2)
                if event.get("sources"):
                    sources = clean_sources(event["sources"])
                if event.get("provider") == "web" and event.get("state") == "working":
                    phase = "Searching the web"
                elif event.get("state") == "merging":
                    phase = "Combining available replies"
                elif event.get("provider") in {"gemini", "groq", "openrouter"}:
                    phase = "Preparing your answer"
            except queue.Empty:
                pass
            with progress.container():
                st.markdown('<div class="ma-progress"><i></i>' + escape(phase) + '</div>', unsafe_allow_html=True)
                show_sources(sources, expanded=True)
        outcome = result.get_nowait()
        if outcome is None:
            raise RuntimeError("Generation failed")
        return outcome
    finally:
        cancel.set()
        progress.empty()


def nav_to_chat(chat_id=None):
    st.session_state._ma_chat_id = chat_id
    st.session_state._ma_view = "chat"
    st.rerun()


def render_sidebar(account: Account, history: ChatHistory):
    blocked = bool(st.session_state.get("_ma_pending_save"))
    with st.sidebar:
        st.markdown(brand(), unsafe_allow_html=True)
        if st.button("New chat", icon=":material/add:", type="primary", width="stretch", disabled=blocked):
            nav_to_chat()
        st.divider()
        st.caption("YOUR CONVERSATIONS")
        search = st.text_input("Search chats", placeholder="Search chat titles…", label_visibility="collapsed", key="ma_search")
        if search != st.session_state.get("_ma_search_previous"):
            st.session_state._ma_pages = 1
            st.session_state._ma_search_previous = search
        if st.button("Refresh chats", icon=":material/refresh:", width="stretch", disabled=blocked):
            st.rerun()
        try:
            with st.container(key="history_list"):
                rows = []
                for page in range(st.session_state.get("_ma_pages", 1)):
                    rows.extend(history.list_chats(page, search))
                if not rows:
                    st.caption("No matching chats." if search else "Your saved chats will appear here.")
                for chat in rows:
                    title = re.sub(r"([\\`*_{}\[\]()#+.!|>])", r"\\\1", chat["title"])
                    if st.button(title, key=f"ma_chat_{chat['id']}", icon=":material/chat_bubble_outline:",
                                 width="stretch", disabled=blocked,
                                 type="primary" if chat["id"] == st.session_state.get("_ma_chat_id") else "secondary"):
                        nav_to_chat(chat["id"])
                if rows and len(rows) % 100 == 0 and st.button("Load more chats", disabled=blocked):
                    st.session_state._ma_pages = st.session_state.get("_ma_pages", 1) + 1
                    st.rerun()
        except HistoryError as exc:
            st.info(str(exc))
        st.divider()
        st.text(display_name(account.user))
        if st.button("Account info", icon=":material/account_circle:", width="stretch", disabled=blocked):
            st.session_state._ma_view = "account"
            st.rerun()
        if st.button("Sign out", icon=":material/logout:", width="stretch", disabled=blocked):
            account.sign_out()
            clear_private_state()
            st.rerun()


def render_unsaved(history: ChatHistory) -> None:
    pending = st.session_state._ma_pending_save
    with st.chat_message("user"):
        st.markdown(pending["question"])
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        st.markdown(pending["answer"])
    st.warning("This answer has not saved yet. Keep this tab open and retry, or download a copy.")
    if st.button("Retry saving", type="primary"):
        try:
            history.finish_turn(pending["turn_id"], pending["answer"], pending["sources"])
            del st.session_state._ma_pending_save
            st.rerun()
        except (HistoryError, AccountError) as exc:
            st.warning(str(exc))
    st.download_button("Download this answer", pending["question"] + "\n\n" + pending["answer"],
                       file_name="Merge_AI_answer.txt", mime="text/plain")
    with st.expander("Discard unsaved answer"):
        agreed = st.checkbox("I understand this answer may not be saved.")
        if st.button("Discard", disabled=not agreed):
            history.fail_turn(pending["turn_id"])
            del st.session_state._ma_pending_save
            st.rerun()


def chat_actions(history, chat, turns):
    with st.expander("Chat options"):
        with st.form("ma_rename"):
            name = st.text_input("Chat title", value=chat["title"], max_chars=100)
            rename = st.form_submit_button("Rename chat")
        if rename:
            try:
                history.rename_chat(chat["id"], name)
                st.rerun()
            except (HistoryError, AccountError) as exc:
                st.warning(str(exc))
        st.download_button("Download conversation", export_chat(chat, turns),
                           file_name="Merge_AI_chat.md", mime="text/markdown")
        confirm = st.checkbox("Delete this conversation and its messages", key=f"ma_delete_{chat['id']}")
        if st.button("Delete chat", disabled=not confirm):
            try:
                history.delete_chat(chat["id"])
                nav_to_chat()
            except (HistoryError, AccountError) as exc:
                st.warning(str(exc))


def render_chat(account, history):
    if st.session_state.get("_ma_pending_save"):
        render_unsaved(history)
        return
    chat_id = st.session_state.get("_ma_chat_id")
    chat, turns, retry = None, [], None
    if chat_id:
        try:
            chat, turns = history.load_chat(chat_id)
        except (HistoryError, AccountError) as exc:
            st.warning(str(exc))
            return
        st.subheader(chat["title"])
        st.caption("Saved to your account · Refresh chats to see changes from another device")
        chat_actions(history, chat, turns)
    else:
        first_name = escape(display_name(account.user).split()[0])
        st.markdown('<div class="ma-intro"><div class="ma-eyebrow">A LITTLE MORE PERSPECTIVE</div>'
            f'<h1>What’s on your mind,<br>{first_name}?</h1>'
            '<p>Work through an idea, understand something new, or find a clearer answer.</p>'
            '<div class="ma-chips"><span>Gemini</span><span>OpenRouter</span><span>Groq</span>'
            '<span>Tavily research</span></div></div>', unsafe_allow_html=True)
        st.caption("Conversations save to your account after you send a message.")
    for turn in turns:
        with st.chat_message("user"):
            st.markdown(turn["question"])
        if turn["status"] == "complete":
            with st.chat_message("assistant", avatar=":material/auto_awesome:"):
                st.markdown(turn["answer"])
                show_sources(turn.get("sources"))
        elif can_retry(turn):
            st.caption("This reply was interrupted. Your question is saved.")
            if st.button("Retry reply", key=f"ma_retry_{turn['id']}"):
                retry = turn
        else:
            st.info("A reply is in progress. Refresh chats in a moment. An interrupted reply can be retried after five minutes.")

    pending = any(t["status"] == "pending" and not can_retry(t) for t in turns)
    prompt = st.chat_input("Message Merge AI…", max_chars=12000, disabled=pending, key="ma_prompt")
    if not prompt and not retry:
        return
    question = retry["question"] if retry else prompt.strip()
    if not question:
        return
    now = time.monotonic()
    recent = [t for t in st.session_state.get("_ma_request_times", []) if now - t < 3600]
    if len(recent) >= 20:
        st.info("This session has reached its hourly question limit. Please try again later.")
        return
    st.session_state._ma_request_times = [*recent, now]
    turn_id = retry["id"] if retry else new_id()
    chat_id = chat_id or new_id()
    try:
        reserved = history.begin_turn(chat_id, turn_id, question)
        st.session_state._ma_chat_id = chat_id
        if reserved["status"] == "complete":
            st.rerun()
        # Reload AFTER the database lock/reservation, so another device's last
        # completed answer is present in the context used for this reply.
        _, current_turns = history.load_chat(chat_id)
    except (AccountError, HistoryError) as exc:
        st.warning(str(exc))
        return
    if not retry:
        with st.chat_message("user"):
            st.markdown(question)
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        try:
            answer, sources = run_engine(question, current_turns)
        except Exception:
            history.fail_turn(turn_id)
            st.warning("I couldn’t finish that reply. Your question is saved; you can retry it.")
            return
        st.markdown(answer)
    # Retain the result BEFORE attempting persistence. Save failures are visible,
    # can be retried idempotently, and don't cause another paid AI generation.
    st.session_state._ma_pending_save = {
        "chat_id": chat_id, "turn_id": turn_id, "question": question,
        "answer": answer, "sources": sources,
    }
    try:
        history.finish_turn(turn_id, answer, sources)
        del st.session_state._ma_pending_save
    except (AccountError, HistoryError):
        pass
    st.rerun()


def main():
    favicon = Path(__file__).with_name("merge_ai_favicon.png")
    st.set_page_config(page_title="Merge AI", page_icon=str(favicon) if favicon.exists() else "💬",
                       layout="wide", initial_sidebar_state="auto")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="ma-header">' + brand() + '<span class="ma-badge">One clearer answer</span></div>',
                unsafe_allow_html=True)
    if not is_configured():
        st.subheader("Your conversations, wherever you are")
        st.info("Account sign-in is being set up. Please check back soon.")
        return
    try:
        if "_ma_account" not in st.session_state:
            st.session_state._ma_account = Account(setting("SUPABASE_URL"), setting("SUPABASE_PUBLISHABLE_KEY"))
        account = st.session_state._ma_account
        user = account.verified_user()
    except AccountError as exc:
        render_auth_recovery(str(exc))
        return
    if not user:
        render_sign_in(account)
        return
    if st.session_state.get("_ma_owner") != str(user.id):
        # Do not carry another account's chat IDs, pending data, or AI context.
        clear_private_state()
        st.session_state._ma_account = account
        st.session_state._ma_owner = str(user.id)
        st.session_state._ma_view = "chat"
    history = ChatHistory(account)
    try:
        render_sidebar(account, history)
        if st.session_state.get("_ma_view") == "account":
            if st.button("Back to chat", icon=":material/arrow_back:"):
                nav_to_chat(st.session_state.get("_ma_chat_id"))
            render_account_info(account)
        else:
            render_chat(account, history)
    except AccountError as exc:
        render_auth_recovery(str(exc))


def render_auth_recovery(message: str) -> None:
    st.warning(message)
    pending = st.session_state.get("_ma_pending_save")
    if pending:
        st.info("An answer is waiting to be saved. Sign in to the same account to retry saving it, or download it now.")
        st.download_button("Download unsaved answer", pending["question"] + "\n\n" + pending["answer"],
                           file_name="Merge_AI_answer.txt", mime="text/plain")
    if st.button("Return to sign in"):
        # Preserve pending data while this same account reauthenticates. The
        # owner check in main clears it before a different account can see it.
        st.session_state.pop("_ma_account", None)
        st.rerun()
