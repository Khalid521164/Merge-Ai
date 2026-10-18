"""Tavily-only web research for Merge AI (Python standard library).

One basic search per lookup, with automatic parameter selection and retries
disabled. Tavily supplies source excerpts and optional extracted page content.
The API's generated-answer field is never treated as evidence. No local model
or other search service is used. Set TAVILY_API_KEY or use Merge AI Settings.

API contract: https://docs.tavily.com/documentation/api-reference/endpoint/search
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.client import HTTPException
import ipaddress
import json
import re
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SEARCH_URL = "https://api.tavily.com/search"
SEARCH_TIMEOUT = 25
MAX_RESPONSE_BYTES = 2_000_000
MAX_SOURCES = 3
MAX_EXCERPT_CHARS = 8_000


class WebSearchError(Exception):
    """Internal classified failure; never includes keys or raw server bodies."""


def _check(cancel: threading.Event, deadline: float) -> None:
    if cancel.is_set():
        raise WebSearchError("Search stopped.")
    if time.monotonic() >= deadline:
        raise WebSearchError("Search time budget reached.")


def validate_api_key(key: str, *, required: bool = True) -> None:
    if not key:
        if required:
            raise WebSearchError("Add your Tavily API key in Settings.")
        return
    if key.lower().startswith(("your_", "paste_")) or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise WebSearchError("Enter a valid Tavily API key in Settings.")


def safe_public_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 4096 or any(ord(c) <= 32 for c in value):
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname or "@" in parts.netloc or "\\" in parts.netloc:
            return ""
        if parts.port not in (None, 80, 443):
            return ""
        host = parts.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return ""
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                return ""
        else:
            if not address.is_global:
                return ""
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    except ValueError:
        return ""


def site_name(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.").rstrip(".")


def _on_sites(url: str, sites: set[str]) -> bool:
    host = site_name(url)
    return not sites or any(host == site or host.endswith("." + site) for site in sites)


def requested_urls(question: str) -> list[str]:
    pattern = r"https?://[^\s<>\"']+|(?<![\w@])(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|edu|gov|io|ai|co|bd|us|uk|ca|au|info|biz)(?:/[^\s<>\"']*)?\b"
    found = []
    for match in re.finditer(pattern, question, re.I):
        value = match.group().rstrip(".,;:!?)]}")
        url = safe_public_url(value if "://" in value else "https://" + value)
        if url and url not in found:
            found.append(url)
    return found[:3]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the Tavily Authorization header to a redirect target.
        return None


@dataclass
class LookupResult:
    sources: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    credits_used: int | float | None = None


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(c for c in value if c in "\n\t" or ord(c) >= 32).strip()


def _sources_from_response(data: dict, sites: set[str]) -> list[dict[str, str]]:
    records = data.get("results")
    if not isinstance(records, list):
        raise WebSearchError("Tavily returned an unreadable result list.")
    sources, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            continue
        url = safe_public_url(record.get("url", ""))
        if not url or url in seen or not _on_sites(url, sites):
            continue
        content = _clean_text(record.get("content"))
        raw = _clean_text(record.get("raw_content"))
        # Retain relevant search excerpts plus page context/contact information.
        excerpt = content[:3000]
        if raw and raw != content:
            page = raw if len(raw) <= 4800 else raw[:3200] + "\n[…]\n" + raw[-1600:]
            excerpt += ("\n\nExtracted page content:\n" if excerpt else "") + page
        if not excerpt:
            continue  # A URL/title alone is not supporting evidence.
        seen.add(url)
        sources.append({
            "url": url, "title": _clean_text(record.get("title"))[:160] or site_name(url),
            "excerpt": excerpt[:MAX_EXCERPT_CHARS], "provider": "tavily",
            "retrieved": "page" if raw else "search_excerpt",
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if len(sources) >= MAX_SOURCES:
            break
    return sources


@dataclass
class WebSearch:
    """Tavily search client. Keys remain out of repr, results, and model prompts."""
    api_key: str = field(default="", repr=False)

    def lookup(self, question, cancel, deadline, on_status=None):
        _check(cancel, deadline)
        try:
            validate_api_key(self.api_key)
        except WebSearchError as exc:
            return LookupResult([], [str(exc)])
        sites = {site_name(url) for url in requested_urls(question)}
        payload = {
            "query": question[:1000], "topic": "general", "search_depth": "basic",
            "auto_parameters": False, "max_results": 5, "include_answer": False,
            "include_raw_content": "text", "include_images": False, "include_usage": True,
        }
        if sites:
            payload["include_domains"] = sorted(sites)
            payload["include_domains_mode"] = "restrict"
        request = Request(SEARCH_URL, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "Accept": "application/json", "User-Agent": "MergeAI/1.5"}, method="POST")
        if on_status:
            on_status("Searching with Tavily", [])
        try:
            timeout = max(0.1, min(SEARCH_TIMEOUT, deadline - time.monotonic()))
            with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
                _check(cancel, deadline)
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            _check(cancel, deadline)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise WebSearchError("Tavily returned too much data.")
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise WebSearchError("Tavily returned an unreadable response.")
            sources = _sources_from_response(data, sites)
            usage = data.get("usage")
            credits = usage.get("credits") if isinstance(usage, dict) else None
            if isinstance(credits, bool) or not isinstance(credits, (int, float)):
                credits = None
            if on_status and sources:
                on_status("Tavily sources ready", sources)
            return LookupResult(sources, [] if sources else ["No usable Tavily source text."], credits)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            # Store only a category and code, never response text or credentials.
            category = {400: "request", 401: "authentication", 403: "access",
                        429: "rate limit", 432: "usage limit", 433: "usage limit"}.get(status, "service")
            return LookupResult([], [f"Tavily {category} unavailable (HTTP {status})."])
        except (URLError, OSError, socket.timeout, HTTPException):
            return LookupResult([], ["Tavily connection unavailable."])
        except (UnicodeError, ValueError, WebSearchError):
            return LookupResult([], ["Tavily response unavailable."])
