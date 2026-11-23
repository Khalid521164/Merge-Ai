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

    def _call(self, method, table, filters=None, data=None, prefer=None):
        url = self.base + table
        if filters:
            url += '?' + urlencode(filters)
        headers = {
            'apikey': self.key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Prefer': prefer or ('return=representation' if method == 'GET' else 'return=minimal'),
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

    def list_agents(self):
        rows = self._call('GET', 'ma2_agents', {
            'owner_sub': 'eq.' + self.owner,
            'select': 'id,name,description,instructions,avatar,created_at,updated_at',
            'order': 'updated_at.desc', 'limit': '100',
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected agent response.')
        return rows

    def list_agent_aliases(self):
        rows = self._call('GET', 'ma2_agent_aliases', {
            'owner_sub': 'eq.' + self.owner,
            'select': 'agent_id,display_name',
            'order': 'updated_at.desc',
            'limit': '100',
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected agent-name response.')
        return {
            str(row['agent_id']): str(row['display_name'])
            for row in rows
            if row.get('agent_id') and row.get('display_name')
        }

    def save_agent_aliases(self, aliases):
        if not isinstance(aliases, dict) or len(aliases) > 100:
            raise CloudHistoryError('Invalid agent-name list.')
        now = datetime.now(timezone.utc).isoformat()
        records = []
        for agent_id, display_name in aliases.items():
            agent_id = str(agent_id or '').strip()
            display_name = str(display_name or '').strip()
            if (
                not agent_id
                or len(agent_id) > 80
                or not all(ch.isalnum() or ch in '-_' for ch in agent_id)
            ):
                raise CloudHistoryError('Invalid agent ID.')
            if not (1 <= len(display_name) <= 40):
                raise CloudHistoryError('Agent display names must be 1–40 characters.')
            records.append({
                'owner_sub': self.owner,
                'agent_id': agent_id,
                'display_name': display_name,
                'updated_at': now,
            })
        if not records:
            return
        self._call(
            'POST',
            'ma2_agent_aliases',
            filters={'on_conflict': 'owner_sub,agent_id'},
            data=records,
            prefer='resolution=merge-duplicates,return=minimal',
        )

    def create_control_device(self, device):
        """Create a private desktop relay session for the signed-in owner."""
        if not isinstance(device, dict):
            raise CloudHistoryError('Invalid desktop bridge session.')
        try:
            session_id = str(uuid.UUID(str(device['session_id'])))
            chat_id = str(uuid.UUID(str(device['chat_id'])))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid desktop bridge session ID.') from None
        token_hash = str(device.get('token_hash') or '')
        if len(token_hash) != 64 or any(ch not in '0123456789abcdef' for ch in token_hash.lower()):
            raise CloudHistoryError('Invalid desktop bridge token hash.')
        record = {
            'session_id': session_id,
            'chat_id': chat_id,
            'owner_sub': self.owner,
            'token_hash': token_hash,
            'status': 'pending',
            'pair_expires_at': str(device['pair_expires_at']),
            'expires_at': str(device['expires_at']),
        }
        self._call('POST', 'ma2_control_devices', data=record)
        return session_id

    def get_control_device(self, session_id):
        try:
            session_id = str(uuid.UUID(str(session_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid desktop bridge session ID.') from None
        rows = self._call('GET', 'ma2_control_devices', {
            'session_id': 'eq.' + session_id,
            'owner_sub': 'eq.' + self.owner,
            'select': 'session_id,chat_id,status,pair_expires_at,expires_at,last_seen_at,created_at',
            'limit': '1',
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected desktop bridge response.')
        return rows[0] if rows else None

    def create_control_command(self, command):
        """Queue one already-approved action for the owner's paired desktop."""
        if not isinstance(command, dict):
            raise CloudHistoryError('Invalid desktop command.')
        try:
            command_id = str(uuid.UUID(str(command.get('command_id') or uuid.uuid4())))
            session_id = str(uuid.UUID(str(command['session_id'])))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid desktop command ID.') from None
        allowed = {
            'screenshot', 'open_app', 'open_url', 'click',
            'move_mouse', 'type_text', 'hotkey', 'scroll',
        }
        action = str(command.get('action') or '')
        arguments = command.get('arguments') or {}
        if action not in allowed or not isinstance(arguments, dict):
            raise CloudHistoryError('Unsupported desktop command.')
        device = self.get_control_device(session_id)
        if not device or device.get('status') != 'active':
            raise CloudHistoryError('The desktop bridge is not connected.')
        self._call('POST', 'ma2_control_commands', data={
            'command_id': command_id,
            'session_id': session_id,
            'owner_sub': self.owner,
            'action': action,
            'arguments': arguments,
            'status': 'approved',
        })
        return command_id

    def list_control_commands(self, session_id, limit=10):
        try:
            session_id = str(uuid.UUID(str(session_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid desktop bridge session ID.') from None
        rows = self._call('GET', 'ma2_control_commands', {
            'session_id': 'eq.' + session_id,
            'owner_sub': 'eq.' + self.owner,
            'select': 'command_id,action,arguments,status,result_text,created_at,completed_at',
            'order': 'created_at.desc',
            'limit': str(max(1, min(int(limit), 20))),
        })
        if not isinstance(rows, list):
            raise CloudHistoryError('Unexpected desktop command response.')
        return rows

    def end_control_device(self, session_id):
        try:
            session_id = str(uuid.UUID(str(session_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid desktop bridge session ID.') from None
        self._call('PATCH', 'ma2_control_devices', {
            'session_id': 'eq.' + session_id,
            'owner_sub': 'eq.' + self.owner,
            'status': 'in.(pending,active)',
        }, {'status': 'stopped'})
        self._call('PATCH', 'ma2_control_commands', {
            'session_id': 'eq.' + session_id,
            'owner_sub': 'eq.' + self.owner,
            'status': 'in.(approved,running)',
        }, {'status': 'cancelled'})

    def save_agent(self, agent):
        if not isinstance(agent, dict):
            raise CloudHistoryError('Invalid agent.')
        try:
            agent_id = str(uuid.UUID(str(agent['id'])))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid agent ID.') from None

        name = str(agent.get('name') or '').strip()
        description = str(agent.get('description') or '').strip()
        instructions = str(agent.get('instructions') or '').strip()
        avatar = str(agent.get('avatar') or '🤖').strip()[:8]
        if not (2 <= len(name) <= 48) or not description or len(description) > 180:
            raise CloudHistoryError('Agent name or description is invalid.')
        if not (20 <= len(instructions) <= 6000):
            raise CloudHistoryError('Agent instructions must contain 20–6000 characters.')

        record = {
            'name': name,
            'description': description,
            'instructions': instructions,
            'avatar': avatar or '🤖',
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        found = self._call('GET', 'ma2_agents', {
            'id': 'eq.' + agent_id, 'owner_sub': 'eq.' + self.owner,
            'select': 'id', 'limit': '1',
        })
        if found:
            self._call('PATCH', 'ma2_agents', {
                'id': 'eq.' + agent_id, 'owner_sub': 'eq.' + self.owner,
            }, record)
        else:
            self._call('POST', 'ma2_agents', data={
                'id': agent_id, 'owner_sub': self.owner,
                'created_at': datetime.now(timezone.utc).isoformat(),
                **record,
            })

    def delete_agent(self, agent_id):
        try:
            agent_id = str(uuid.UUID(str(agent_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid agent ID.') from None
        self._call('DELETE', 'ma2_agents', {
            'id': 'eq.' + agent_id, 'owner_sub': 'eq.' + self.owner,
        })

    def delete_memory(self, memory_id):
        try:
            memory_id = str(uuid.UUID(str(memory_id)))
        except (ValueError, TypeError, AttributeError):
            raise CloudHistoryError('Invalid memory ID.') from None
        self._call('DELETE', 'ma2_memories', {
            'id': 'eq.' + memory_id, 'owner_sub': 'eq.' + self.owner,
        })
