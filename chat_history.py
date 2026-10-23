"""Durable, user-owned conversations backed by Supabase Postgres RLS.

All operations require a verified Account. UUIDs are identifiers, never proof
of ownership. The database enforces ownership even if Python filters are bypassed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from account_info import AccountError


class HistoryError(Exception):
    pass


def uuid_text(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise HistoryError("This conversation could not be opened.") from None


class ChatHistory:
    def __init__(self, account):
        self.account = account

    @property
    def owner(self) -> str:
        if not self.account.user:
            raise AccountError("Sign in to access your saved chats.")
        return str(self.account.user.id)

    def _db(self):
        if not self.account.verified_user():
            raise AccountError("Sign in to access your saved chats.")
        return self.account.client

    def list_chats(self, page: int = 0, search: str = "") -> list[dict]:
        try:
            query = self._db().table("merge_conversations").select(
                "id,title,created_at,updated_at"
            ).eq("user_id", self.owner)
            if search.strip():
                literal = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                query = query.ilike("title", f"%{literal}%")
            return query.order("updated_at", desc=True).order("id").range(
                page * 100, page * 100 + 99
            ).execute().data
        except AccountError:
            raise
        except Exception:
            raise HistoryError("Saved chats could not load. Please try Refresh chats.") from None

    def load_chat(self, chat_id: str) -> tuple[dict, list[dict]]:
        chat_id = uuid_text(chat_id)
        try:
            client = self._db()
            rows = client.table("merge_conversations").select("id,title,created_at,updated_at").eq(
                "id", chat_id).eq("user_id", self.owner).execute().data
            if not rows:
                raise HistoryError("This chat is unavailable or was deleted on another device.")
            turns = []
            offset = 0
            while True:
                batch = client.table("merge_turns").select(
                    "id,question,answer,sources,status,created_at,finished_at"
                ).eq("conversation_id", chat_id).eq("user_id", self.owner).order(
                    "created_at").order("id").range(offset, offset + 199).execute().data
                turns.extend(batch)
                if len(batch) < 200:
                    break
                offset += 200
            return rows[0], turns
        except (AccountError, HistoryError):
            raise
        except Exception:
            raise HistoryError("This chat could not load. Please try again.") from None

    def begin_turn(self, chat_id: str, turn_id: str, question: str) -> dict:
        try:
            data = self._db().rpc("merge_begin_turn", {
                "p_chat": uuid_text(chat_id), "p_turn": uuid_text(turn_id),
                "p_question": question.strip(),
            }).execute().data
            if not data:
                raise HistoryError("The question could not be saved.")
            return data[0]
        except (AccountError, HistoryError):
            raise
        except Exception as exc:
            # Match only known codes; never show response bodies or SQL errors.
            message = str(exc)
            if "TURN_IN_PROGRESS" in message:
                raise HistoryError("A reply is still running in this chat. Refresh in a moment or start a new chat.") from None
            raise HistoryError("The question could not be saved. Please try again.") from None

    def finish_turn(self, turn_id: str, answer: str, sources: list) -> None:
        try:
            self._db().rpc("merge_finish_turn", {
                "p_turn": uuid_text(turn_id), "p_answer": answer,
                "p_sources": sources,
            }).execute()
        except AccountError:
            raise
        except Exception:
            raise HistoryError("Your answer is ready, but it has not saved yet.") from None

    def fail_turn(self, turn_id: str) -> None:
        try:
            self._db().table("merge_turns").update({"status": "error"}).eq(
                "id", uuid_text(turn_id)).eq("user_id", self.owner).eq("status", "pending").execute()
        except Exception:
            pass  # Stale pending turns are recoverable after five minutes.

    def rename_chat(self, chat_id: str, title: str) -> None:
        title = title.strip()
        if not 1 <= len(title) <= 100:
            raise HistoryError("Use a chat title between 1 and 100 characters.")
        try:
            data = self._db().table("merge_conversations").update({"title": title}).eq(
                "id", uuid_text(chat_id)).eq("user_id", self.owner).execute().data
            if not data:
                raise ValueError("Missing chat")
        except AccountError:
            raise
        except Exception:
            raise HistoryError("The chat could not be renamed. Refresh and try again.") from None

    def delete_chat(self, chat_id: str) -> None:
        try:
            self._db().table("merge_conversations").delete().eq(
                "id", uuid_text(chat_id)).eq("user_id", self.owner).execute()
        except AccountError:
            raise
        except Exception:
            raise HistoryError("The chat could not be deleted. Please try again.") from None


def new_id() -> str:
    return str(uuid4())


def can_retry(turn: dict) -> bool:
    if turn.get("status") == "error":
        return True
    try:
        created = datetime.fromisoformat(turn["created_at"].replace("Z", "+00:00"))
        return turn.get("status") == "pending" and (datetime.now(timezone.utc) - created).total_seconds() > 300
    except (ValueError, KeyError, TypeError):
        return False


def restore_engine(engine, turns: list[dict]) -> None:
    """Adapter for the existing MergeAI v2026-10-18 class's history buffer.

    Restores context without sending earlier questions to APIs a second time.
    Only completed turns enter model context; failed questions are excluded.
    """
    from merge_ai import MAX_HISTORY_TURNS
    pairs = [(t["question"], t["answer"]) for t in turns
             if t.get("status") == "complete" and isinstance(t.get("answer"), str)]
    with engine._lock:
        engine._turns = pairs[-MAX_HISTORY_TURNS:]


def export_chat(chat: dict, turns: list[dict]) -> str:
    sections = [f"# {chat['title']}"]
    for turn in turns:
        sections.append("## You\n\n" + turn["question"])
        if turn.get("status") == "complete":
            sections.append("## Merge AI\n\n" + turn["answer"])
            for source in turn.get("sources") or []:
                sections.append(str(source.get("url", "")))
    return "\n\n".join(sections)
