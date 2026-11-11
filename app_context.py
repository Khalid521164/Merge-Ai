"""Pure conversation-context serialization shared by chat and voice."""
from __future__ import annotations

from typing import Any

DEFAULT_CONTEXT_CHARS = 18000


def serialize_conversation(chat: dict[str, Any], *, max_chars: int = DEFAULT_CONTEXT_CHARS) -> str:
    """Serialize trusted transcript text and safe citation/attachment metadata.

    The app's storage layer remains the authority for ownership. Client-side file
    paths are intentionally ignored; this helper never opens arbitrary files.
    """
    from merge_ai import is_draft_comparison

    messages = chat.get("messages", []) if isinstance(chat, dict) else []
    if not isinstance(messages, list):
        return ""
    try:
        budget = max(200, min(int(max_chars), 40000))
    except (TypeError, ValueError):
        budget = DEFAULT_CONTEXT_CHARS

    rendered: list[str] = []
    used = 0
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "user"))[:20]
        if role not in {"user", "assistant", "system"}:
            continue
        content = str(message.get("content", ""))
        if role == "assistant" and is_draft_comparison(content):
            continue

        metadata: list[str] = []
        attachments = message.get("attachments") or message.get("files") or []
        if isinstance(attachments, list):
            for item in attachments[:8]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or item.get("filename") or "attached file")[:160]
                mime = str(item.get("mime_type") or item.get("type") or "")[:80]
                # Never use client-supplied filesystem paths as retrievable data.
                file_id = str(item.get("id") or item.get("file_id") or "")[:160]
                if file_id:
                    metadata.append(f"[Attachment reference: {name} ({mime}), id={file_id}]")
                else:
                    metadata.append(f"[Attachment metadata only: {name} ({mime}); no authorized retriever is configured]")

        sources = message.get("sources") or []
        if role == "assistant" and isinstance(sources, list):
            citations = []
            for source in sources[:6]:
                if isinstance(source, dict):
                    title = str(source.get("title") or "Source")[:120]
                    url = str(source.get("url") or "")[:500]
                    if url.startswith(("https://", "http://")):
                        citations.append(f"{title}: {url}")
                elif isinstance(source, str) and source.startswith(("https://", "http://")):
                    citations.append(source[:500])
            if citations:
                metadata.append("[Previously cited sources: " + "; ".join(citations) + "]")

        entry = f"{role}: {content}"
        if metadata:
            entry += "\n" + "\n".join(metadata)
        remaining = budget - used
        if remaining <= 0:
            break
        if len(entry) > remaining:
            if remaining < 240:
                break
            entry = entry[:remaining - 24] + " …[older context excerpt]"
        rendered.append(entry)
        used += len(entry) + 1

    return "\n".join(reversed(rendered))
