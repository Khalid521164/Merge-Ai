"""Single submission pipeline primitives shared by chat and Live Voice."""
from __future__ import annotations

from typing import Any, Callable


class DuplicateTurnError(ValueError):
    """Raised when a voice event has already been processed."""


def claim_voice_event(event_id: str, seen: list[str], *, limit: int = 100) -> bool:
    """Return True once per nonempty voice event ID."""
    identifier = str(event_id or "").strip()[:160]
    if not identifier:
        return True
    if identifier in seen:
        return False
    seen.append(identifier)
    if len(seen) > limit:
        del seen[:-limit]
    return True


def process_turn(
    chat: dict[str, Any],
    question: str,
    *,
    answer: Callable[[dict[str, Any], str], tuple[str, list]],
    persist: Callable[[dict[str, Any]], None],
    source: str = "chat",
) -> tuple[str, list]:
    """Call the shared answerer and append one normalized user/assistant pair."""
    text = str(question or "").strip()
    if not text:
        raise ValueError("A non-empty question is required.")
    response, citations = answer(chat, text)
    chat.setdefault("messages", []).extend([
        {"role": "user", "content": text, "input_mode": source},
        {"role": "assistant", "content": str(response), "sources": citations or []},
    ])
    if chat.get("title") == "New chat":
        chat["title"] = text[:60]
    persist(chat)
    return str(response), citations or []
