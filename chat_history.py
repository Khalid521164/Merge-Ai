"""Per-visitor, multi-conversation history for the Merge AI Streamlit UI.

Chats and MergeAI engines live in st.session_state, not in shared globals/files.
This is intentionally session-only storage, not cross-device account sync.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from typing import Callable
from uuid import uuid4

import streamlit as st

MAX_CHATS = 20


def _new_record(messages=None):
    messages = list(messages or [])
    first_question = next(
        (m.get("content", "") for m in messages if m.get("role") == "user"),
        "",
    )
    title = title_from_question(first_question) if first_question else "New conversation"
    return {
        "id": uuid4().hex,
        "title": title,
        "messages": messages,
        "updated": time.time(),
    }


def title_from_question(question: str) -> str:
    cleaned = " ".join(str(question).split())
    return cleaned[:42] + ("…" if len(cleaned) > 42 else "") or "New conversation"


def init_history(make_engine: Callable):
    """Initialize chat history, migrating a running older app's chat if present."""
    if "merge_chats" not in st.session_state:
        old_messages = st.session_state.get("messages", [])
        record = _new_record(old_messages if isinstance(old_messages, list) else [])
        st.session_state.merge_chats = {record["id"]: record}
        st.session_state.merge_active_id = record["id"]
        old_engine = st.session_state.get("engine")
        st.session_state.merge_engines = {
            record["id"]: old_engine if old_engine is not None else make_engine()
        }
    if st.session_state.merge_active_id not in st.session_state.merge_chats:
        st.session_state.merge_active_id = next(iter(st.session_state.merge_chats))


def active_chat() -> dict:
    return st.session_state.merge_chats[st.session_state.merge_active_id]


def active_engine():
    return st.session_state.merge_engines[st.session_state.merge_active_id]


def create_chat(make_engine: Callable) -> bool:
    """Create one new chat. Return False at the cap (never silently discard chats)."""
    if not active_chat()["messages"]:
        return True  # Reuse an existing empty chat instead of stacking blanks.
    if len(st.session_state.merge_chats) >= MAX_CHATS:
        return False
    record = _new_record()
    st.session_state.merge_chats[record["id"]] = record
    st.session_state.merge_engines[record["id"]] = make_engine()
    st.session_state.merge_active_id = record["id"]
    return True


def select_chat(chat_id: str) -> None:
    if chat_id in st.session_state.merge_chats:
        st.session_state.merge_active_id = chat_id


def delete_chat(chat_id: str, make_engine: Callable) -> None:
    chats = st.session_state.merge_chats
    chats.pop(chat_id, None)
    st.session_state.merge_engines.pop(chat_id, None)
    if not chats:
        record = _new_record()
        chats[record["id"]] = record
        st.session_state.merge_engines[record["id"]] = make_engine()
    if st.session_state.merge_active_id not in chats:
        st.session_state.merge_active_id = max(chats, key=lambda k: chats[k]["updated"])


def rename_chat(chat_id: str, title: str) -> None:
    if chat_id in st.session_state.merge_chats:
        title = " ".join(title.split())[:60]
        if title:
            st.session_state.merge_chats[chat_id]["title"] = title


def add_message(role: str, content: str, sources=None) -> None:
    record = active_chat()
    msg = {"role": role, "content": content}
    if role == "assistant" and sources:
        msg["sources"] = sources
    record["messages"].append(msg)
    record["updated"] = time.time()
    if role == "user" and not any(
        m["role"] == "user" for m in record["messages"][:-1]
    ):
        record["title"] = title_from_question(content)


def export_history() -> str:
    """Provide a manual backup: no credentials, no engine objects."""
    chats = st.session_state.merge_chats.values()
    return json.dumps(
        {
            "app": "Merge AI",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "chats": [
                {
                    "title": c["title"],
                    "messages": c["messages"],
                }
                for c in chats if c["messages"]
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def history_popover(make_engine: Callable) -> None:
    """The same History control appears on desktop, tablet, and phone."""
    with st.popover("History", use_container_width=True):
        st.markdown("##### Chat history")
        st.caption("Private to this browser session. Download a backup before refreshing or closing.")
        ordered = sorted(
            st.session_state.merge_chats.values(),
            key=lambda item: item["updated"], reverse=True,
        )
        with st.container(height=230, border=False):
            for chat in ordered:
                prefix = "● " if chat["id"] == st.session_state.merge_active_id else ""
                if st.button(
                    prefix + chat["title"],
                    key="open_" + chat["id"],
                    help="Open this conversation",
                    use_container_width=True,
                ):
                    select_chat(chat["id"])
                    st.rerun()

        with st.expander("Rename or delete selected chat"):
            current = active_chat()
            title = st.text_input(
                "Conversation name",
                value=current["title"],
                max_chars=60,
                key="rename_" + current["id"],
            )
            if st.button("Save name", key="save_" + current["id"]):
                rename_chat(current["id"], title)
                st.rerun()
            if st.button("Delete selected chat", key="delete_" + current["id"]):
                delete_chat(current["id"], make_engine)
                st.rerun()

        st.download_button(
            "Download history backup",
            data=export_history(),
            file_name="merge_ai_chats.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption(f"{len(ordered)} / {MAX_CHATS} conversations")
