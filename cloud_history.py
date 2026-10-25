"""Merge AI cloud chat history for the existing app.py.

Server-side Supabase access only. The owner must come from a verified
Streamlit Google login, never from user input.
"""
from __future__ import annotations

import json
import logging
import socket
import ssl
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class CloudHistoryError(Exception):
    """Safe cloud-history error with no credential details."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudHistory:
    """Store conversations belonging to one verified Google account."""

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
            or parsed.query
            or parsed.fragment
        ):
            raise CloudHistoryError("Invalid SUPABASE_URL configuration.")

        if not isinstance(secret_key, str) or not secret_key.strip():
            raise CloudHistoryError("Missing SUPABASE_SECRET_KEY.")

        if secret_key.strip().startswith("sb_publishable_"):
            raise CloudHistoryError(
                "Use a Supabase secret key, not a publishable key."
            )

        if (
            not isinstance(owner, str)
            or not owner.startswith("google:")
            or owner in ("google:", "google:unknown")
            or len(owner) > 300
        ):
            raise CloudHistoryError(
                "Please sign in with Google to use cloud history."
            )

        self.endpoint = f"https://{hostname}/rest/v1/merge_chats"
        self._secret = secret_key.strip()
        self.owner = owner
        self._opener = build_opener(_NoRedirect())

    def _request(
        self,
        method: str,
        filters: dict | None = None,
        body: object | None = None,
    ):
        url = self.endpoint + ("?" + urlencode(filters) if filters else "")

        headers = {
            "apikey": self._secret,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MergeAI-CloudHistory/1.1",
            "Prefer": "return=minimal",
        }

        # Legacy service_role JWT keys require Bearer authentication.
        # New sb_secret_* keys authenticate with the apikey header.
        if not self._secret.startswith("sb_secret_"):
            headers["Authorization"] = "Bearer " + self._secret

        payload = (
            json.dumps(body, ensure_ascii=False).encode("utf-8")
            if body is not None
            else None
        )

        if payload is not None and len(payload) > 900_000:
            raise CloudHistoryError("This conversation is too large to save.")

        request = Request(url, data=payload, headers=headers, method=method)

        try:
            with self._opener.open(request, timeout=12) as response:
                content = response.read(1_500_001)

                if len(content) > 1_500_000:
                    raise CloudHistoryError(
                        "The chat history response is too large."
                    )

                return json.loads(content) if content else None

        except HTTPError as exc:
            status = exc.code
            exc.close()
            logging.warning("Cloud history HTTP error: %s", status)

            if status in (401, 403):
                raise CloudHistoryError(
                    "Cloud history credentials or permissions are invalid."
                ) from None

            raise CloudHistoryError(
                "Cloud history is temporarily unavailable."
            ) from None

        except URLError as exc:
            reason = exc.reason

            if isinstance(reason, socket.gaierror):
                category = "DNS lookup failed"
                hint = (
                    "Supabase host could not be found. "
                    "Check SUPABASE_URL against the project's Data API URL."
                )
            elif isinstance(reason, (TimeoutError, socket.timeout)):
                category = "connection timed out"
                hint = (
                    "Supabase connection timed out. "
                    "Check project status and try again."
                )
            elif isinstance(reason, ssl.SSLError):
                category = "TLS validation failed"
                hint = "The secure Supabase connection could not be verified."
            else:
                category = "URL/network error (" + type(reason).__name__ + ")"
                hint = (
                    "Could not reach Supabase. "
                    "Verify the project URL and server connectivity."
                )

            logging.warning("Cloud history network failure: %s", category)
            raise CloudHistoryError(hint) from None

        except (TimeoutError, socket.timeout):
            logging.warning("Cloud history network failure: timeout")
            raise CloudHistoryError(
                "Supabase connection timed out. Please retry."
            ) from None

        except (ValueError, UnicodeError) as exc:
            logging.warning(
                "Cloud history response decoding failed: %s",
                type(exc).__name__,
            )
            raise CloudHistoryError(
                "Supabase returned an unreadable response. "
                "Check the project URL."
            ) from None

        except OSError as exc:
            logging.warning(
                "Cloud history transport failure: %s",
                type(exc).__name__,
            )
            raise CloudHistoryError(
                "The connection to Supabase failed. Please retry."
            ) from None

    def list_chats(self) -> list[dict]:
        records = self._request(
            "GET",
            {
                "select": "id,title,messages,updated_at",
                "owner_sub": "eq." + self.owner,
                "order": "updated_at.desc",
                "limit": "20",
            },
        )

        if not isinstance(records, list):
            raise CloudHistoryError("Unexpected cloud history response.")

        return records

    def upsert(self, chat: dict) -> None:
        """Save or update only conversations owned by this Google user."""
        if not isinstance(chat, dict) or not isinstance(
            chat.get("messages"), list
        ):
            raise CloudHistoryError("Invalid chat data.")

        try:
            chat_id = str(uuid.UUID(str(chat["id"])))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise CloudHistoryError("Invalid chat identifier.") from None

        title = str(chat.get("title") or "New conversation")[:60]

        existing = self._request(
            "GET",
            {
                "select": "id",
                "owner_sub": "eq." + self.owner,
                "id": "eq." + chat_id,
                "limit": "1",
            },
        )

        if not isinstance(existing, list):
            raise CloudHistoryError("Could not verify chat ownership.")

        if existing:
            self._request(
                "PATCH",
                {
                    "id": "eq." + chat_id,
                    "owner_sub": "eq." + self.owner,
                },
                {
                    "title": title,
                    "messages": chat["messages"],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            self._request(
                "POST",
                body={
                    "id": chat_id,
                    "owner_sub": self.owner,
                    "title": title,
                    "messages": chat["messages"],
                },
            )

    def delete(self, chat_id: str) -> None:
        try:
            normalized = str(uuid.UUID(str(chat_id)))
        except (TypeError, ValueError, AttributeError):
            raise CloudHistoryError("Invalid chat identifier.") from None

        self._request(
            "DELETE",
            {
                "id": "eq." + normalized,
                "owner_sub": "eq." + self.owner,
            },
        )
