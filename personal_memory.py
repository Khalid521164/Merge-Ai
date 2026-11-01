"""Privacy-first, account-based memory suggestions for Merge AI.

Suggestions are derived from the current user's own message, never saved
automatically, and require explicit approval before Supabase storage.
"""
from __future__ import annotations
import re
from typing import Iterable

_BLOCK = re.compile(
    r"(?i)\b(?:password|passcode|pin\s*code|secret\s*key|api[_ -]?key|"
    r"access[_ -]?token|bearer\s+|credit\s*card|bank\s*account|ssn|"
    r"social\s*security|passport|home\s*address|street\s*address|"
    r"phone\s*number|medical|diagnos(?:ed|is)|prescription|"
    r"hospital|medication|depress(?:ed|ion)|self.harm|suicide|"
    r"political\s*party|vote\s*for|religion|muslim|christian|"
    r"jewish|sexual|gender\s*identity|immigration|visa|"
    r"i\s+(?:live|reside)\s+(?:at|in)\b|"
    r"my\s+(?:mom|dad|mother|father|sister|brother|wife|husband|"
    r"son|daughter)\b)"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?:\+?\d[\s().-]*){9,}")
_URL = re.compile(r"https?://|www\.", re.I)

_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^(?:my name is|i am called|call me)\s+(.+)$", "My name is {value}."),
    (r"^(?:i am|i'm)\s+in\s+(\d{1,2}(?:st|nd|rd|th)?\s+grade)\b.*$", "I am in {value}."),
    (r"^(?:i play)\s+([a-z][\w -]{2,35})$", "I play {value}."),
    (r"^(?:i (?:love|enjoy|like))\s+([a-z][\w -]{2,65})$", "I enjoy {value}."),
    (r"^(?:i(?:'m| am) (?:building|making|developing|working on))\s+(.+)$", "I am building {value}."),
    (r"^(?:my (?:goal|dream) is(?: to)?)\s+(.+)$", "My goal is to {value}."),
    (r"^(?:i (?:prefer|usually prefer))\s+(.+)$", "I prefer {value}."),
    (r"^(?:my favorite (sport|food|subject|hobby|color|game) is)\s+(.+)$", "My favorite {category} is {value}."),
    (r"^(?:i am studying|i'm studying)\s+(.+)$", "I am studying {value}."),
)

def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def _safe(value: str) -> bool:
    return bool(value) and not (
        _BLOCK.search(value) or _EMAIL.search(value)
        or _PHONE.search(value) or _URL.search(value)
    )

def _segments(message: str) -> list[str]:
    if not isinstance(message, str) or len(message) > 1800:
        return []
    if "```" in message or message.lstrip().startswith((">", "{")):
        return []
    raw = re.sub(r"^remember\s+(?:that\s+)?", "", message.strip(), flags=re.I)
    segments = re.split(
        r"(?<=[.!?])\s+|\s*[,;]\s*|\s+and\s+(?=(?:i\b|my\b))",
        raw, flags=re.I,
    )
    return [re.sub(r"^and\s+", "", s.strip(), flags=re.I).rstrip(".!? ")
            for s in segments if s.strip()]

def suggest_memories(message: str, existing: Iterable[str] = (), limit: int = 4) -> list[str]:
    """Suggest non-sensitive first-person facts. NEVER writes to storage."""
    if not _safe(message):
        return []
    known = {_normalize(str(x)) for x in existing}
    seen: set[str] = set()
    suggestions: list[str] = []
    for segment in _segments(message):
        if len(segment) > 115 or not _safe(segment):
            continue
        for pattern, template in _PATTERNS:
            matched = re.fullmatch(pattern, segment, flags=re.I)
            if not matched:
                continue
            category = matched.group(1).strip() if "{category}" in template else ""
            value = matched.group(2 if category else 1).strip().strip('"\' .,!?:;')
            if not 2 <= len(value) <= 75 or not _safe(value):
                continue
            candidate = template.format(value=value, category=category)
            fingerprint = _normalize(candidate)
            if fingerprint not in known and fingerprint not in seen:
                seen.add(fingerprint)
                suggestions.append(candidate)
            break
        if len(suggestions) >= max(0, min(limit, 4)):
            break
    return suggestions

def relevant_memories(question: str, memories: list[dict], limit: int = 12) -> list[str]:
    """Select approved records already scoped to this Google user."""
    words = set(re.findall(r"[a-z]{3,}", (question or "").casefold()))
    rows = [str(m.get("content", ""))[:500] for m in memories if m.get("content")]
    scored: list[tuple[int, int, str]] = []
    for i, entry in enumerate(rows):
        entry_words = set(re.findall(r"[a-z]{3,}", entry.casefold()))
        match = len(words & entry_words)
        evergreen = int(bool(re.search(r"\b(my name|grade|i prefer|my goal)\b", entry, re.I)))
        scored.append((match * 3 + evergreen, -i, entry))
    scored.sort(reverse=True)
    return [entry for _, _, entry in scored[:max(0, min(limit, 20))]]

def is_memory_question(question: str) -> bool:
    q = re.sub(r"\s+", " ", str(question).lower()).strip(" ?!.")
    return bool(re.search(
        r"(?:what (?:do you|have you) (?:know|remember|saved) about me|"
        r"what (?:are|is) my (?:saved )?memories|"
        r"show (?:me )?my (?:saved )?memories|"
        r"what is (?:in|inside) my memory)", q
    ))

def is_forget_request(question: str) -> bool:
    return bool(re.match(
        r"^\s*(?:please\s+)?(?:forget|delete|remove)\s+"
        r"(?:that\s+|my memory\b|the memory\b)", str(question), flags=re.I,
    ))
