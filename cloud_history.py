"""Merge AI private chat and memory storage (server-side only)."""
import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class CloudHistoryError(Exception):
    """An error safe to display without revealing secrets."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CloudHistory:
    def __init__(self, base_url, secret_key, owner):
        raw = str(base_url or '').strip().rstrip('/')
        # Accept project URL as well as the pasted REST endpoint.
        if raw.endswith('/rest/v1'):
            raw = raw[:-len('/rest/v1')]
        p = urlsplit(raw)
        host = (p.hostname or '').lower()
        if (p.scheme != 'https' or not host.endswith('.supabase.co')
                or host == '.supabase.co' or p.port is not None
                or p.username or p.password or p.path not in ('', '/')
                or p.query or p.fragment):
            raise CloudHistoryError('Invalid SUPABASE_URL. Use https://PROJECT.supabase.co')
        key = str(secret_key or '').strip()
        if not key or key.startswith('sb_publishable_'):
            raise CloudHistoryError('A Supabase server secret key is required.')
        if not isinstance(owner, str) or not owner.startswith('google:') or len(owner) > 300:
            raise CloudHistoryError('Sign in with Google to save chats.')
        self.base = 'https://' + host + '/rest/v1/'
        self.key = key
        self.owner = owner
        self.opener = build_opener(_NoRedirect())

    def _call(self, method, table, filters=None, data=None):
        url = self.base + table
        if filters:
            url += '?' + urlencode(filters)
        headers = {
            'apikey': self.key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation' if method == 'GET' else 'return=minimal',
            'User-Agent': 'MergeAI-Server/2.0',
        }
        if not self.key.startswith('sb_secret_'):
            headers['Authorization'] = 'Bearer ' + self.key
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
        if payload is not None and len(payload) > 900000:
            raise CloudHistoryError('Chat too large to save; export a backup.')
        try:
            req = Request(url, data=payload, headers=headers, method=method)
            with self.opener.open(req, timeout=12) as resp:
                contents = resp.read(1500001)
                if len(contents) > 1500000:
                    raise CloudHistoryError('Cloud response too large.')
                return json.loads(contents) if contents else []
        except HTTPError as e:
            status = e.code
            e.close()
            logging.warning('Supabase error HTTP %s on %s', status, table)
            if status in (401, 403):
                raise CloudHistoryError('Supabase API key or table permissions are invalid.') from None
            if status == 404:
                raise CloudHistoryError('Supabase table missing. Run the setup SQL.') from None
            raise CloudHistoryError('Supabase could not complete the request (HTTP %s).' % status) from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise CloudHistoryError('Cannot reach Supabase right now. Check URL or connection.') from None
        except (ValueError, UnicodeError):
            raise CloudHistoryError('Supabase returned an invalid response.') from None

    def list_chats(self):
        rows = self._call('GET', 'ma2_chats', {
            'owner_sub': 'eq.' + self.owner,
            'select': 'id,title,messages,updated_at',
            'order': 'updated_at.desc', 'limit': '200',
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected chat response.')
        return rows

    def save_chat(self, chat):
        if not isinstance(chat, dict) or not isinstance(chat.get('messages'), list):
            raise CloudHistoryError('Invalid chat.')
        try:
            chat_id = str(uuid.UUID(str(chat['id'])))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid chat ID.') from None
        record = {
            'title': str(chat.get('title') or 'New chat')[:160],
            'messages': chat['messages'],
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        # Never update or delete a row that does not belong to this owner.
        found = self._call('GET', 'ma2_chats', {
            'id': 'eq.' + chat_id, 'owner_sub': 'eq.' + self.owner,
            'select': 'id', 'limit': '1',
        })
        if found:
            self._call('PATCH', 'ma2_chats', {
                'id': 'eq.' + chat_id,
                'owner_sub': 'eq.' + self.owner,
            }, record)
        else:
            self._call('POST', 'ma2_chats', data={
                'id': chat_id, 'owner_sub': self.owner, **record,
            })

    def delete_chat(self, chat_id):
        try:
            chat_id = str(uuid.UUID(str(chat_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid chat ID.') from None
        self._call('DELETE', 'ma2_chats', {
            'id': 'eq.' + chat_id, 'owner_sub': 'eq.' + self.owner,
        })

    def list_memories(self):
        rows = self._call('GET', 'ma2_memories', {
            'owner_sub': 'eq.' + self.owner,
            'select': 'id,content,created_at',
            'order': 'created_at.desc', 'limit': '50',
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected memory response.')
        return rows

    def add_memory(self, content):
        content = str(content).strip()[:500]
        if not content:
            return
        self._call('POST', 'ma2_memories', data={
            'id': str(uuid.uuid4()), 'owner_sub': self.owner,
            'content': content,
        })

    def delete_memory(self, memory_id):
        try:
            memory_id = str(uuid.UUID(str(memory_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid memory ID.') from None
        self._call('DELETE', 'ma2_memories', {
            'id': 'eq.' + memory_id, 'owner_sub': 'eq.' + self.owner,
        })
