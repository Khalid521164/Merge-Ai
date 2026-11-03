"""Deterministic speech preparation; never edits or shortens the written answer."""
from html import unescape
import re


class UnsafeSpeechText(ValueError):
    """Internal provider commentary must not be read aloud by either voice."""


def check_final_answer(text: str) -> None:
    # Guard the speech boundary without changing the application's answer engine.
    # An explicit public comparison of provider capabilities remains allowed.
    plain = re.sub(r"```[\s\S]*?(?:```|$)", "", text).casefold()
    internal = r"\b(?:private evidence note|internal (?:draft|candidate)|draft [123]|candidate answer [123]|(?:both|these|the|two) drafts?|(?:gemini|groq|openrouter)[ -]+draft)\b"
    attribution = r"\b(?:gemini|groq|openrouter)\s+(?:says|said|answered|responded)\b"
    provider_table = "|" in plain and len(set(re.findall(r"\b(?:gemini|groq|openrouter)\b", plain))) >= 2
    if re.search(internal, plain) or re.search(attribution, plain) or (provider_table and re.search(r"\b(?:answer|draft|response|candidate)s?\b", plain)):
        raise UnsafeSpeechText("This reply contains provider commentary; please request one final answer.")


def prepare_speech_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    # Never speak private reasoning, including a malformed unclosed reasoning tag.
    text = re.sub(r"<think(?:ing)?>[\s\S]*?(?:</think(?:ing)?>|$)", "", text, flags=re.I)
    lines, fence = [], None
    for line in text.replace("\r\n", "\n").splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1]
                lines.append("A code example is available in the chat.")
            elif marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        if re.fullmatch(r"\s*(?:[-*_]\s*){3,}", line) or re.fullmatch(r"[\s|:\-]+", line):
            continue
        line = re.sub(r"^\s{0,3}#{1,6}\s+|\s+#+\s*$", "", line)
        line = re.sub(r"^\s*>\s?", "", line)
        line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(?:\[[ xX]\]\s*)?", "", line)
        if "|" in line:
            line = "; ".join(part.strip() for part in line.strip().strip("|").split("|") if part.strip())
        line = line.strip()
        if line:
            # Preserve line boundaries as pauses rather than merging list items into one word.
            lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"!\[([^\]]*)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^()\n]|\([^()\n]*\))*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*\[[^\]]+\]:\s*https?://.*$", "", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"https?://[^\s<>]+", lambda m: re.search(r"[.,;!?]+$", m[0])[0] if re.search(r"[.,;!?]+$", m[0]) else "", text)
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)
    text = unescape(text)
    for pattern in (r"\*\*(.+?)\*\*", r"__(.+?)__", r"~~(.+?)~~",
                    r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"(?<!\w)_([^_\n]+)_(?!\w)", r"`+([^`\n]+)`+"):
        text = re.sub(pattern, r"\1", text)
    text = re.sub(r"([!?])\1+", r"\1", text)
    text = re.sub(r"\.{3,}|…+", ".", text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def browser_chunks(text: str, maximum: int = 220) -> list[str]:
    """Split without dropping characters or breaking decimal numbers at periods."""
    words = re.findall(r"\S+\s*", text)
    chunks, current = [], ""
    for word in words:
        if current and len(current) + len(word) > maximum:
            chunks.append(current)
            current = ""
        current += word
    if current:
        chunks.append(current)
    return chunks
