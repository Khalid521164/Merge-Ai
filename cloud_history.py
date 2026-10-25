"""Merge AI cloud chat history, for the existing app.py.

Server-only Supabase REST access. Never import this module in browser JavaScript,
and never commit SUPABASE_SECRET_KEY to GitHub. `owner` MUST come from the
verified Streamlit st.user identity, not from a form, URL or chat message.

Works with the SQL table public.merge_chats previously created:
  id uuid, owner_sub text, title text, messages jsonb, updated_at timestamptz.
Requires no third-party Python packages.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class CloudHistoryError(Exception):
    """A safe error to show in Streamlit, without exposing credentials."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudHistory:
    """Private chat storage scoped to one *server-verified* Google account."""

    def __init__(self, base_url: str, secret_key: str, owner: str):
        parsed = urlsplit((base_url or "").strip().rstrip("/"))
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not hostname.endswith(".supabase.co")
            or hostname == ".supabase.co"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment
        ):
            raise CloudHistoryError("Invalid SUPABASE_URL configuration.")
        if not isinstance(secret_key, str) or not secret_key.strip():
            raise CloudHistoryError("Missing SUPABASE_SECRET_KEY.")
        if (not isinstance(owner, str) or not owner.startswith("google:")
                or owner in ("google:", "google:unknown") or len(owner) > 300):
            raise CloudHistoryError("Please sign in with Google to use cloud history.")

        self.endpoint = f"https://{hostname}/rest/v1/merge_chats"
        self._secret = secret_key.strip()
        self.owner = owner
        self._opener = build_opener(_NoRedirect())

    def _request(self, method: str, filters: dict | None = None,
                 body: object | None = None):
        url = self.endpoint + ("?" + urlencode(filters) if filters else "")
        headers = {
            "apikey": self._secret,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MergeAI-CloudHistory/1.1",
            "Prefer": "return=minimal",
        }
        # Supabase legacy service_role JWT keys also need an Authorization header.
        # Newer sb_secret_* keys authenticate via apikey, not a Bearer JWT.
        if not self._secret.startswith("sb_secret_"):
            headers["Authorization"] = "Bearer " + self._secret
        payload = (json.dumps(body, ensure_ascii=False).encode("utf-8")
                   if body is not None else None)
        if payload is not None and len(payload) > 900_000:
            raise CloudHistoryError("This conversation is too large to save.")
        request = Request(url, data=payload, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=12) as response:
                content = response.read(1_500_001)
                if len(content) > 1_500_000:
                    raise CloudHistoryError("The chat history response is too large.")
                return json.loads(content) if content else None
        except HTTPError as exc:
            status = exc.code
            exc.close()
            logging.warning("Cloud history HTTP error: %s", status)
            if status in (401, 403):
                raise CloudHistoryError("Cloud history credentials or permissions are invalid.") from None
            raise CloudHistoryError("Cloud history is temporarily unavailable.") from None
        except (URLError, OSError, ValueError, UnicodeError):
            logging.warning("Cloud history request failed", exc_info=False)
            raise CloudHistoryError("Could not connect to cloud history. Please retry.") from None

    def list_chats(self) -> list[dict]:
        records = self._request("GET", {
            "select": "id,title,messages,updated_at",
            "owner_sub": "eq." + self.owner,
            "order": "updated_at.desc",
            "limit": "20",
        })
        if not isinstance(records, list):
            raise CloudHistoryError("Unexpected cloud history response.")
        return records

    def upsert(self, chat: dict) -> None:
        """Insert or update a chat without ever updating its owner."""
        if not isinstance(chat, dict) or not isinstance(chat.get("messages"), list):
            raise CloudHistoryError("Invalid chat data.")
        try:
            chat_id = str(uuid.UUID(str(chat["id"])))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise CloudHistoryError("Invalid chat identifier.") from None
        title = str(chat.get("title") or "New conversation")[:60]
        existing = self._request("GET", {
            "select": "id", "owner_sub": "eq." + self.owner,
            "id": "eq." + chat_id, "limit": "1",
        })
        if not isinstance(existing, list):
            raise CloudHistoryError("Could not verify chat ownership.")
        if existing:
            self._request("PATCH", {
                "id": "eq." + chat_id,
                "owner_sub": "eq." + self.owner,
            }, {
                "title": title,
                "messages": chat["messages"],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            # Insert has an owner value from the trusted server session only.
            # A UUID collision with an existing other user's row will fail safely.
            self._request("POST", body={
                "id": chat_id,
                "owner_sub": self.owner,
                "title": title,
                "messages": chat["messages"],
            })

    def delete(self, chat_id: str) -> None:
        try:
            normalized = str(uuid.UUID(str(chat_id)))
        except (TypeError, ValueError, AttributeError):
            raise CloudHistoryError("Invalid chat identifier.") from None
        self._request("DELETE", {
            "id": "eq." + normalized,
            "owner_sub": "eq." + self.owner,
        })
