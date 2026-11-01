
"""
MERGE AI - Free-tier-friendly multi-model AI engine.

Compatible with the existing Streamlit app.py.

Providers:
    Gemini
    Groq
    OpenRouter (optional)

Research:
    Tavily

Features:
    - One final answer
    - Automatic provider fallback
    - Free-tier-friendly default models
    - No immediate retry of rate-limit errors
    - Optional research with source links
    - Conversational memory
    - Server-side API keys only

Requires:
    requests

Never put real API keys in this file.
"""

from __future__ import annotations

import os
import re
import logging
from html import unescape
from dataclasses import dataclass
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from urllib.parse import urlparse

import requests


# ==========================================
# CONFIGURATION
# ==========================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

GROQ_BACKUP_MODEL = os.getenv(
    "GROQ_BACKUP_MODEL",
    "openai/gpt-oss-120b",
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen3-32b:free",
)

# Keep OpenRouter off until its credit issue
# is resolved. Set ENABLE_OPENROUTER=true
# in Streamlit Secrets to enable it later.
ENABLE_OPENROUTER = (
    os.getenv(
        "ENABLE_OPENROUTER", "false"
    ).lower() == "true"
)

REQUEST_TIMEOUT = 35
MAX_OUTPUT_TOKENS = 1100
MAX_HISTORY_TURNS = 8
MAX_WEB_RESULTS = 5
MAX_SEARCH_CHARS = 6500

SYSTEM_PROMPT = """
You are Merge AI, a friendly, accurate AI assistant.

Always answer the user's latest actual message directly.
Never show or compare internal AI candidate answers,
model drafts, scoring, or model-selection analysis.
Do not repeat the creator's identity unless the user asks.

For introductions, acknowledge the person naturally.
For factual questions, answer directly.
If the user pastes multiple numbered questions, answer EACH
one in order. If one-line responses are requested, use one
short line per question. Never answer only one item in a list.

Follow the user's language. Use relevant earlier conversation
and approved memory. Never invent sources, facts or memories.
Never reveal private API keys.
"""


# ==========================================
# ERRORS
# ==========================================

class MergeAIError(Exception):
    """Base error for Merge AI."""


class ProviderError(MergeAIError):
    """An AI provider failed."""

    def __init__(
        self,
        provider: str,
        message: str,
        status: int | None = None,
    ):
        super().__init__(
            f"{provider}: {message}"
        )
        self.provider = provider
        self.status = status


# ==========================================
# PROVIDER CONFIG
# ==========================================

@dataclass
class Provider:
    name: str
    api_key: str
    model: str
    enabled: bool = True


def get_key(name: str) -> str:
    """Get a private key from environment."""

    value = os.environ.get(name)
    if value is not None:
        return str(value).strip()
    # BRAVE_SEARCH_API_KEY is not copied into os.environ by app.py,
    # so we also read server-side Streamlit Secrets directly.
    try:
        import streamlit as st
        return str(st.secrets.get(name, "")).strip()
    except Exception:
        return ""


def default_providers() -> tuple[Provider, ...]:
    """
    Read keys automatically.

    app.py already loads Streamlit Secrets
    into environment variables.
    """

    return (
        Provider(
            name="gemini",
            api_key=get_key("GEMINI_API_KEY"),
            model=GEMINI_MODEL,
        ),
        Provider(
            name="groq",
            api_key=get_key("GROQ_API_KEY"),
            model=GROQ_MODEL,
        ),
        Provider(
            name="openrouter",
            api_key=get_key("OPENROUTER_API_KEY"),
            model=OPENROUTER_MODEL,
            enabled=ENABLE_OPENROUTER,
        ),
    )


# ==========================================
# HTTP HELPERS
# ==========================================

SESSION = requests.Session()


def post_json(
    url: str,
    headers: dict,
    payload: dict,
    timeout: int = REQUEST_TIMEOUT,
) -> dict:

    try:
        response = SESSION.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    except requests.Timeout:
        raise MergeAIError(
            "The AI service timed out."
        )

    except requests.RequestException:
        raise MergeAIError(
            "Could not connect to the AI service."
        )

    if response.status_code >= 400:
        try:
            body = response.json()
            detail = body.get(
                "error", {}
            )

            if isinstance(detail, dict):
                message = str(
                    detail.get(
                        "message",
                        "Request failed",
                    )
                )
            else:
                message = str(detail)

        except (ValueError, TypeError):
            message = "Request failed"

        # Do not immediately retry HTTP 429:
        # doing so can make the quota problem worse.
        raise ProviderError(
            provider="API",
            message=message[:350],
            status=response.status_code,
        )

    try:
        return response.json()

    except ValueError:
        raise MergeAIError(
            "The AI service returned invalid JSON."
        )


def openai_message_text(data: dict) -> str:

    choices = data.get(
        "choices", []
    )

    if not choices:
        raise MergeAIError(
            "The model returned no choices."
        )

    message = choices[0].get(
        "message", {}
    )

    content = message.get(
        "content", ""
    )

    if isinstance(content, str):
        text = content.strip()

    elif isinstance(content, list):
        text = "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict)
        ).strip()

    else:
        text = ""

    if not text:
        raise MergeAIError(
            "The model returned an empty answer."
        )

    return text


# ==========================================
# GEMINI
# ==========================================

def call_gemini(
    api_key: str,
    messages: list[dict],
    model: str = GEMINI_MODEL,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{model}:generateContent"
    )

    contents = []

    for item in messages:
        role = (
            "model"
            if item["role"] == "assistant"
            else "user"
        )

        contents.append({
            "role": role,
            "parts": [
                {"text": item["content"]}
            ],
        })

    payload = {
        "systemInstruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.5,
        },
    }

    data = post_json(
        url,
        {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        payload,
    )

    candidates = data.get(
        "candidates", []
    )

    if not candidates:
        raise MergeAIError(
            "Gemini returned no answer."
        )

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )

    text = "".join(
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict)
    ).strip()

    if not text:
        raise MergeAIError(
            "Gemini returned no visible text."
        )

    return text


# ==========================================
# GROQ
# ==========================================

def call_groq(
    api_key: str,
    messages: list[dict],
    model: str = GROQ_MODEL,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *messages,
        ],
        "max_completion_tokens": max_tokens,
        "temperature": 0.5,
        "stream": False,
    }

    data = post_json(
        "https://api.groq.com/openai/v1/"
        "chat/completions",
        {
            "Authorization": (
                "Bearer " + api_key
            ),
            "Content-Type": "application/json",
        },
        payload,
    )

    return openai_message_text(data)


# ==========================================
# OPENROUTER
# ==========================================

def call_openrouter(
    api_key: str,
    messages: list[dict],
    model: str = OPENROUTER_MODEL,
    max_tokens: int = MAX_OUTPUT_TOKENS,
) -> str:

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            *messages,
        ],
        "max_tokens": max_tokens,
        "temperature": 0.5,
        "stream": False,
    }

    data = post_json(
        "https://openrouter.ai/api/v1/"
        "chat/completions",
        {
            "Authorization": (
                "Bearer " + api_key
            ),
            "Content-Type": "application/json",
            "HTTP-Referer": (
                "https://mergeai.streamlit.app"
            ),
            "X-Title": "Merge AI",
        },
        payload,
    )

    return openai_message_text(data)


# ==========================================
# PROVIDER ROUTING
# ==========================================

def call_provider(
    provider: Provider,
    messages: list[dict],
    max_tokens: int,
) -> str:

    if provider.name == "gemini":
        return call_gemini(
            provider.api_key,
            messages,
            provider.model,
            max_tokens,
        )

    if provider.name == "groq":
        return call_groq(
            provider.api_key,
            messages,
            provider.model,
            max_tokens,
        )

    if provider.name == "openrouter":
        return call_openrouter(
            provider.api_key,
            messages,
            provider.model,
            max_tokens,
        )

    raise MergeAIError(
        "Unknown AI provider."
    )


# ==========================================
# SAFE SOURCE LINKS
# ==========================================

def safe_source_url(value) -> str:
    """Allow ordinary HTTP/HTTPS sources only."""

    if not isinstance(value, str):
        return ""

    value = value.strip()

    if len(value) > 2000:
        return ""

    try:
        parsed = urlparse(value)

        if (
            parsed.scheme.lower()
            not in ("https", "http")
        ):
            return ""

        if not parsed.hostname:
            return ""

        if parsed.username or parsed.password:
            return ""

        return value

    except ValueError:
        return ""


# ==========================================
# BRAVE SEARCH API (PRIMARY) / SEARCH PRIVACY
# ==========================================

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def latest_question_for_search(context: str) -> str:
    """Never send Supabase memories or earlier chat history to search APIs."""
    marker = "\nCurrent question:\n"
    return (context.rsplit(marker, 1)[-1] if marker in context else context).strip()


def should_search(question: str) -> bool:
    """Keep introductions and obvious private details out of web search."""
    q = str(question or "").strip()
    if not q or len(q) > 600:
        return False
    if re.match(r"(?i)^(?:hi\b|hey\b|hello\b|i am\b|i'm\b|my name is\b|thanks\b|thank you\b)", q):
        return False
    if re.search(r"(?i)\b(?:what do you (?:know|remember) about me|my password|my api key|my address)\b", q):
        return False
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", q, re.I):
        return False
    return True


def search_brave(question: str, api_key: str) -> tuple[str, list[dict]]:
    """Fetch public web snippets with Brave. Empty results trigger Tavily fallback."""
    if not api_key or not should_search(question):
        return "", []
    try:
        response = requests.get(
            BRAVE_URL,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={
                "q": question[:600],
                "count": MAX_WEB_RESULTS,
                "safesearch": "moderate",
                "text_decorations": "false",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        results = (data.get("web") or {}).get("results") or []
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        logging.warning("Brave Search unavailable; trying Tavily fallback.")
        return "", []

    evidence, sources, seen = [], [], set()
    for item in results:
        if not isinstance(item, dict):
            continue
        url = safe_source_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        title = unescape(re.sub(r"<[^>]*>", "", str(item.get("title") or "Web source")))[:150]
        snippet = unescape(re.sub(
            r"<[^>]*>", "", str(item.get("description") or "")
        ))[:1200]
        if not snippet and isinstance(item.get("extra_snippets"), list):
            snippet = unescape(" ".join(map(str, item["extra_snippets"][:2])))[:1200]
        sources.append({"title": title, "url": url})
        evidence.append(f"Title: {title}\nURL: {url}\nExcerpt: {snippet}")
        if len(sources) >= MAX_WEB_RESULTS:
            break
    return "\n\n".join(evidence)[:MAX_SEARCH_CHARS], sources


# ==========================================
# TAVILY WEB SEARCH
# ==========================================

def search_tavily(
    question: str,
    api_key: str,
) -> tuple[str, list[dict]]:

    if not api_key:
        return "", []

    payload = {
        "api_key": api_key,
        "query": question[:400],
        "search_depth": "basic",
        "max_results": MAX_WEB_RESULTS,
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        data = post_json(
            "https://api.tavily.com/search",
            {"Content-Type": "application/json"},
            payload,
            timeout=18,
        )

    except MergeAIError:
        logging.warning(
            "Tavily search unavailable."
        )
        return "", []

    results = data.get(
        "results", []
    )

    sources = []
    evidence = []

    for result in results:
        url = safe_source_url(
            result.get("url", "")
        )

        if not url:
            continue

        title = str(
            result.get(
                "title", "Web source"
            )
        )[:150]

        content = str(
            result.get(
                "content", ""
            )
        )[:1200]

        sources.append({
            "title": title,
            "url": url,
        })

        evidence.append(
            f"Title: {title}\n"
            f"URL: {url}\n"
            f"Excerpt: {content}"
        )

    return (
        "\n\n".join(evidence)[
            :MAX_SEARCH_CHARS
        ],
        sources,
    )


# ==========================================
# MERGE / SYNTHESIS
# ==========================================

def build_merge_prompt(
    question: str,
    drafts: dict[str, str],
    research: str,
) -> str:
    """Synthesize privately while preserving the user's actual question."""
    marker = "\nCurrent question:\n"
    current = question.rsplit(marker, 1)[-1] if marker in question else question
    context = question.rsplit(marker, 1)[0][-5000:] if marker in question else ""
    pieces = [
        "You are Merge AI. Give ONE final user-facing answer.",
        "The notes below are private evidence, not answers to review.",
        "Never reveal, compare, quote or describe those evidence notes.",
        "Never produce a draft-comparison table or analyze writing styles.",
        "If the user introduces themselves, respond naturally.",
        "If they paste multiple questions, answer EVERY question in order.",
        "If they ask for one-line answers, give one line per question.",
        "",
        "LATEST USER MESSAGE (answer this):",
        current[-6500:],
        "",
    ]
    if context:
        pieces.extend(["Earlier conversation context:", context, ""])
    if research:
        pieces.extend(["Web evidence:", research[:6000], ""])
    for i, answer in enumerate(drafts.values(), start=1):
        pieces.extend([f"Private evidence note {i}:", answer[:3500], ""])
    pieces.append("Final answer to user (no internal model commentary):")
    return "\n".join(pieces)


def latest_user_question(question: str) -> str:
    """Extract the actual user request from app.py's context envelope."""
    marker = "\nCurrent question:\n"
    if marker in question:
        return question.rsplit(marker, 1)[-1].strip()
    return question.strip()


def user_requested_comparison(question: str) -> bool:
    """Public model-comparison intent is not permission to show private drafts."""
    current = latest_user_question(question).casefold()
    return bool(
        re.search(r"\b(?:compare|comparison|versus|vs\.?|difference between)\b", current)
        and re.search(r"\b(?:groq|gemini|openrouter|models?|drafts?)\b", current)
    )


def is_draft_comparison(text: str) -> bool:
    """Reject responses that review the AI's internal candidate replies."""
    if not text:
        return False
    t = text.casefold()
    return bool(
        re.search(r"\b(?:both|these|the|two) drafts?\b", t)
        or re.search(
            r"\b(?:groq|gemini|openrouter)[\s-]*(?:style[\s-]*)?draft\b", t
        )
        or ("draft" in t and ("groq" in t or "gemini" in t or "openrouter" in t))
        or ("side-by-side" in t and ("groq" in t or "gemini" in t))
        or ("tone/style" in t and "draft" in t)
        or "draft greetings" in t
        or re.search(r"\bdraft [12]\b", t)
    )


# ==========================================
# MAIN MERGE AI CLASS
# ==========================================

class MergeAI:
    """
    One conversation engine.

    app.py calls:
        engine.ask(
            question,
            fast=True,
            web_search=True
        )

    Returns one answer string.
    """

    def __init__(
        self,
        providers=None,
        merger="groq",
        *,
        tavily_api_key=None,
        brave_api_key=None,
    ):

        self.providers = tuple(
            providers
            if providers is not None
            else default_providers()
        )

        self.merger = merger

        self.tavily_api_key = (
            tavily_api_key
            if tavily_api_key is not None
            else get_key("TAVILY_API_KEY")
        )

        self.brave_api_key = (
            brave_api_key if brave_api_key is not None
            else (get_key("BRAVE_SEARCH_API_KEY") or get_key("BRAVE_API_KEY"))
        )

        self.last_report = {
            "sources": [],
            "providers": {},
            "merged": False,
        }

    # --------------------------------------
    # Chat memory
    # --------------------------------------

    def messages_for(
        self,
        question: str,
        research: str = "",
    ) -> list[dict]:

        messages = []

        # The Streamlit app already supplies the signed-in user's recent
        # conversation and approved memories inside 'question'.
        # Do not reuse process-global turns across separate accounts.
        current = question

        if research:
            current += (
                "\n\nRelevant web research:\n"
                + research
                + "\n\nUse the sources carefully."
            )

        messages.append({
            "role": "user",
            "content": current,
        })

        return messages

    # --------------------------------------
    # Get drafts concurrently
    # --------------------------------------

    def collect_drafts(
        self,
        messages: list[dict],
        max_tokens: int,
    ):

        active = [
            p for p in self.providers
            if p.enabled and p.api_key
        ]

        if not active:
            raise MergeAIError(
                "No AI providers are configured. "
                "Check your Streamlit Secrets."
            )

        drafts = {}
        errors = {}

        def worker(provider):
            try:
                result = call_provider(
                    provider,
                    messages,
                    max_tokens,
                )

                return (
                    provider.name,
                    result,
                    None,
                )

            except Exception as exc:
                return (
                    provider.name,
                    None,
                    exc,
                )

        with ThreadPoolExecutor(
            max_workers=len(active)
        ) as pool:

            futures = [
                pool.submit(worker, p)
                for p in active
            ]

            for future in as_completed(futures):
                name, answer, error = (
                    future.result()
                )

                if answer:
                    drafts[name] = answer
                else:
                    errors[name] = error

        return drafts, errors

    # --------------------------------------
    # Optional backup Groq model
    # --------------------------------------

    def groq_backup(
        self,
        messages: list[dict],
        max_tokens: int,
    ) -> str | None:

        key = get_key("GROQ_API_KEY")

        if not key:
            for provider in self.providers:
                if provider.name == "groq":
                    key = provider.api_key
                    break

        if not key:
            return None

        if GROQ_BACKUP_MODEL == GROQ_MODEL:
            return None

        try:
            return call_groq(
                key,
                messages,
                GROQ_BACKUP_MODEL,
                max_tokens,
            )

        except Exception:
            logging.warning(
                "Backup Groq model unavailable."
            )
            return None

    # --------------------------------------
    # Merge drafts
    # --------------------------------------

    def merge_drafts(
        self,
        question: str,
        drafts: dict[str, str],
        research: str,
        max_tokens: int,
    ) -> str:

        if len(drafts) == 1:
            answer = next(iter(drafts.values()))
            if not is_draft_comparison(answer):
                return answer
            return self.direct_answer(question, research, max_tokens)

        merge_prompt = build_merge_prompt(
            question,
            drafts,
            research,
        )

        merge_messages = [{
            "role": "user",
            "content": merge_prompt,
        }]

        # Prefer Groq as the final merger,
        # but use another successful provider
        # if Groq is unavailable.
        order = [
            "groq",
            "gemini",
            "openrouter",
        ]

        for name in order:
            if name not in drafts:
                continue

            provider = next(
                (
                    p for p in self.providers
                    if p.name == name
                    and p.enabled
                    and p.api_key
                ),
                None,
            )

            if provider is None:
                continue

            try:
                answer = call_provider(
                    provider,
                    merge_messages,
                    max_tokens,
                )

                if is_draft_comparison(answer):
                    logging.warning("%s returned an internal draft comparison.", name)
                    continue
                self.last_report["merged"] = True
                return answer

            except Exception:
                logging.warning(
                    "%s could not merge drafts.",
                    name,
                )

        # Important:
        # Never throw away a successful draft
        # merely because the final merge failed.
        for name in (
            "groq",
            "gemini",
            "openrouter",
        ):
            if name in drafts and not is_draft_comparison(drafts[name]):
                return drafts[name]

        # No internal comparison tables should ever be returned as the answer.
        return self.direct_answer(question, research, max_tokens)

    def direct_answer(
        self,
        question: str,
        research: str,
        max_tokens: int,
    ) -> str:
        """Recover a direct answer without passing internal model drafts."""
        current = latest_user_question(question)
        clean = (
            "Reply directly to the following user message as Merge AI. "
            "Do not mention Groq, Gemini, model drafts, comparisons, "
            "tables of draft greetings, or the internal answer process "
            "unless the user specifically requests them.\n\n"
            "User message:\n" + current
        )
        if research:
            clean += "\n\nResearch evidence:\n" + research[:4500]
        messages = [{"role": "user", "content": clean}]
        for provider in self.providers:
            if not provider.enabled or not provider.api_key:
                continue
            try:
                answer = call_provider(provider, messages, max_tokens).strip()
                if answer and not is_draft_comparison(answer):
                    return answer
            except Exception:
                logging.warning("Direct-answer recovery failed for %s.", provider.name)

        # Avoid displaying an internal comparison as the final response.
        return (
            "I couldn't generate a clear final answer this time. "
            "Please try your question again."
        )

    # --------------------------------------
    # Main public method
    # --------------------------------------

    def ask(
        self,
        question: str,
        *,
        fast: bool = True,
        web_search: bool = True,
        **kwargs,
    ) -> str:

        question = str(
            question or ""
        ).strip()

        if not question:
            raise MergeAIError(
                "Please enter a question."
            )

        question = question[:12000]

        self.last_report = {
            "sources": [],
            "providers": {},
            "merged": False,
        }

        # Brave is primary; Tavily remains fallback. Only the latest
        # question goes to a web provider (never saved account memories).
        research, sources, search_provider = "", [], None
        search_question = latest_question_for_search(question)
        if web_search and should_search(search_question):
            if self.brave_api_key:
                research, sources = search_brave(
                    search_question, self.brave_api_key
                )
                if sources:
                    search_provider = "brave"
            if not sources and self.tavily_api_key:
                research, sources = search_tavily(
                    search_question, self.tavily_api_key
                )
                if sources:
                    search_provider = "tavily"

        self.last_report["sources"] = sources
        self.last_report["search_provider"] = search_provider

        messages = self.messages_for(
            question,
            research,
        )

        max_tokens = (
            850 if fast else 1800
        )

        drafts, errors = self.collect_drafts(
            messages,
            max_tokens,
        )

        # If all regular providers fail,
        # try a second Groq model.
        if not drafts:
            backup = self.groq_backup(
                messages,
                max_tokens,
            )

            if backup:
                drafts["groq_backup"] = backup

        # Stop only if nothing works.
        if not drafts:
            details = []

            for name, error in errors.items():
                if isinstance(
                    error, ProviderError
                ):
                    status = error.status

                    if status == 429:
                        description = (
                            "rate limit reached"
                        )
                    elif status == 403:
                        description = (
                            "access or spending "
                            "limit reached"
                        )
                    elif status == 401:
                        description = (
                            "invalid API key"
                        )
                    else:
                        description = (
                            f"HTTP {status}"
                        )

                else:
                    description = (
                        "request failed"
                    )

                details.append(
                    f"{name}: {description}"
                )

            raise MergeAIError(
                "No AI provider could answer. "
                + "; ".join(details)
                + ". Check your API limits."
            )

        self.last_report["providers"] = {
            name: (
                "success"
                if name in drafts
                else "unavailable"
            )
            for name in [
                "gemini",
                "groq",
                "openrouter",
            ]
        }

        # FAST mode returns a direct provider answer. Only DEEP mode
        # tries synthesis. Never expose the hidden draft-review table.
        if fast:
            answer = next((
                drafts[name] for name in ("groq", "gemini", "openrouter", "groq_backup")
                if name in drafts and not is_draft_comparison(drafts[name])
            ), "")
        else:
            answer = self.merge_drafts(
                question, drafts, research, max_tokens
            ).strip()

        if answer and is_draft_comparison(answer):
            answer = self.direct_answer(question, research, max_tokens)

        if not answer:
            answer = self.direct_answer(question, research, max_tokens)

        if not answer:
            raise MergeAIError(
                "The AI returned an empty answer."
            )

        # Conversation history is supplied per user by app.py; do not
        # accumulate a shared cache_resource instance's history here.
        return answer
