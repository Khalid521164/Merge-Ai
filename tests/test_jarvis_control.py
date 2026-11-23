"""Unit tests for the Jarvis desktop control protocol and relay contracts."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
import uuid

from PIL import Image

from cloud_history import CloudHistory, CloudHistoryError
from jarvis_control import (
    BridgeClient,
    encode_screenshot_jpeg,
    find_control_agent_request,
    is_device_live,
    load_pairing_file,
    normalize_desktop_action,
    parse_desktop_action_response,
    requires_extra_confirmation,
    resolve_public_key,
    supabase_api_headers,
    validate_public_key,
    validate_server_key,
)


def legacy_key(role):
    payload = base64.urlsafe_b64encode(
        json.dumps({"role": role}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return "eyJhbGciOiJIUzI1NiJ9." + payload + ".signature"


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        return None

    def json(self):
        return self.value


class FakeHttpSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.responses.pop(0))


class SupabaseKeyTests(unittest.TestCase):
    def test_prefers_publishable_key_and_accepts_legacy_anon(self):
        seen = []

        def get_secret(name):
            seen.append(name)
            return "sb_publishable_test" if name == "SUPABASE_PUBLISHABLE_KEY" else legacy_key("anon")

        self.assertEqual(resolve_public_key(get_secret), "sb_publishable_test")
        self.assertEqual(seen, ["SUPABASE_PUBLISHABLE_KEY"])
        self.assertEqual(validate_public_key(legacy_key("anon")), legacy_key("anon"))

    def test_new_public_key_is_sent_only_in_apikey_header(self):
        self.assertEqual(supabase_api_headers("sb_publishable_test"), {"apikey": "sb_publishable_test"})

    def test_legacy_public_key_keeps_compatible_bearer_header(self):
        key = legacy_key("anon")
        self.assertEqual(supabase_api_headers(key), {"apikey": key, "Authorization": "Bearer " + key})

    def test_server_key_validation_rejects_public_keys(self):
        self.assertEqual(validate_server_key("sb_secret_test"), "sb_secret_test")
        self.assertEqual(validate_server_key(legacy_key("service_role")), legacy_key("service_role"))
        with self.assertRaisesRegex(ValueError, "server secret key is required"):
            validate_server_key("sb_publishable_test")

    def test_public_key_validation_rejects_server_keys(self):
        for key in ("sb_secret_test", legacy_key("service_role")):
            with self.subTest(key_type=key[:12]):
                with self.assertRaisesRegex(ValueError, "server secret keys cannot be used"):
                    validate_public_key(key)

    def test_pairing_file_accepts_new_and_legacy_public_keys(self):
        for public_key in ("sb_publishable_test", legacy_key("anon")):
            payload = {
                "supabase_url": "https://project.supabase.co",
                "supabase_public_key": public_key,
                "session_id": str(uuid.uuid4()),
                "device_token": "A" * 64,
            }
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
                json.dump(payload, handle)
                name = handle.name
            try:
                config = load_pairing_file(name)
            finally:
                Path(name).unlink(missing_ok=True)
            self.assertEqual(config["supabase_public_key"], public_key)

    def test_pairing_file_rejects_server_key(self):
        payload = {
            "supabase_url": "https://project.supabase.co",
            "supabase_public_key": "sb_secret_do_not_ship",
            "session_id": str(uuid.uuid4()),
            "device_token": "A" * 64,
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            name = handle.name
        try:
            with self.assertRaisesRegex(ValueError, "invalid public Supabase key"):
                load_pairing_file(name)
        finally:
            Path(name).unlink(missing_ok=True)


class ActionValidationTests(unittest.TestCase):
    def test_allows_and_normalizes_supported_actions(self):
        self.assertEqual(
            normalize_desktop_action("OPEN_APP", {"app": "Notepad", "unused": True}),
            {"action": "open_app", "arguments": {"app": "notepad"}},
        )
        self.assertEqual(
            normalize_desktop_action("click", {"x": "10", "y": 20}),
            {"action": "click", "arguments": {"x": 10, "y": 20}},
        )
        self.assertEqual(
            normalize_desktop_action("hotkey", {"keys": ["CTRL", "S"]}),
            {"action": "hotkey", "arguments": {"keys": ["ctrl", "s"]}},
        )
        self.assertEqual(
            normalize_desktop_action("screenshot", {"ignored": "field"}),
            {"action": "screenshot", "arguments": {}},
        )

    def test_rejects_shell_destructive_and_malformed_actions(self):
        rejected = (
            ("run_shell", {}),
            ("open_app", {"app": "powershell"}),
            ("open_url", {"url": "javascript:alert(1)"}),
            ("open_url", {"url": "https://user:pass@example.com"}),
            ("click", {"x": True, "y": 4}),
            ("click", {"x": 10, "y": 10001}),
            ("type_text", {"text": ""}),
            ("hotkey", {"keys": ["ctrl", "alt", "delete"]}),
            ("scroll", {"direction": "down", "ticks": 16}),
        )
        for action, arguments in rejected:
            with self.subTest(action=action, arguments=arguments):
                with self.assertRaises(ValueError):
                    normalize_desktop_action(action, arguments)

    def test_parses_only_valid_action_json(self):
        self.assertEqual(
            parse_desktop_action_response('```json\n{"action":"open_app","arguments":{"app":"edge"}}\n```'),
            {"action": "open_app", "arguments": {"app": "edge"}},
        )
        self.assertIsNone(parse_desktop_action_response('{"action":"no_action","arguments":{}}'))
        self.assertIsNone(parse_desktop_action_response('{"action":"open_app","arguments":{"app":"cmd"}}'))
        self.assertIsNone(parse_desktop_action_response("not JSON"))

    def test_click_and_enter_require_an_extra_confirmation(self):
        self.assertTrue(requires_extra_confirmation("click", {"x": 10, "y": 20}))
        self.assertTrue(requires_extra_confirmation("hotkey", {"keys": ["enter"]}))
        self.assertFalse(requires_extra_confirmation("type_text", {"text": "hello"}))
        self.assertFalse(requires_extra_confirmation("hotkey", {"keys": ["ctrl", "s"]}))

    def test_routes_explicit_specialist_requests(self):
        agents = [
            {"id": "coder", "name": "Code Partner", "role_name": "Coding Engineer"},
            {"id": "researcher", "name": "Researcher", "role_name": "Researcher"},
        ]
        self.assertEqual(
            find_control_agent_request("Jarvis, ask Coding Engineer to inspect this error", agents),
            (agents[0], "inspect this error"),
        )
        self.assertEqual(
            find_control_agent_request("Please consult Researcher about this traceback", agents),
            (agents[1], "this traceback"),
        )
        self.assertIsNone(find_control_agent_request("Tell me about Python", agents))

    def test_device_requires_recent_heartbeat_and_unexpired_session(self):
        now = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
        device = {
            "status": "active",
            "last_seen_at": (now - timedelta(seconds=10)).isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }
        self.assertTrue(is_device_live(device, now=now))
        device["last_seen_at"] = (now - timedelta(seconds=45)).isoformat()
        self.assertFalse(is_device_live(device, now=now))
        device["last_seen_at"] = (now - timedelta(seconds=10)).isoformat()
        device["expires_at"] = (now - timedelta(seconds=1)).isoformat()
        self.assertFalse(is_device_live(device, now=now))

    def test_screenshot_encoding_is_bounded_jpeg(self):
        result = encode_screenshot_jpeg(Image.new("RGB", (2400, 1600), (20, 40, 60)))
        self.assertTrue(result.startswith("SCREENSHOT_JPEG_BASE64:"))
        encoded = result.split(":", 1)[1]
        image_bytes = base64.b64decode(encoded, validate=True)
        self.assertTrue(image_bytes.startswith(b"\xff\xd8"))
        self.assertLessEqual(len(encoded), 480000)


class RelayContractTests(unittest.TestCase):
    def setUp(self):
        self.session_id = str(uuid.uuid4())
        self.command_id = str(uuid.uuid4())
        self.http = FakeHttpSession([True, [{"command_id": self.command_id}], True, True])
        self.client = BridgeClient({
            "supabase_url": "https://project.supabase.co",
            "supabase_public_key": "sb_publishable_test",
            "session_id": self.session_id,
            "device_token": "T" * 64,
        }, session=self.http)

    def test_rpc_names_headers_and_payloads_match_sql_contract(self):
        self.assertTrue(self.client.heartbeat())
        self.assertEqual(self.client.claim()[0]["command_id"], self.command_id)
        self.assertTrue(self.client.complete(self.command_id, "completed", "done"))
        self.assertTrue(self.client.stop_session())
        expected = (
            "ma2_bridge_heartbeat",
            "ma2_bridge_claim_commands",
            "ma2_bridge_complete_command",
            "ma2_bridge_stop",
        )
        self.assertEqual(tuple(call[0].rsplit("/", 1)[1] for call in self.http.calls), expected)
        self.assertEqual(self.http.calls[0][1]["headers"]["apikey"], "sb_publishable_test")
        self.assertNotIn("Authorization", self.http.calls[0][1]["headers"])
        for _, kwargs in self.http.calls:
            self.assertEqual(kwargs["json"]["p_session_id"], self.session_id)
            self.assertEqual(len(kwargs["json"]["p_token_hash"]), 64)

        sql = (Path(__file__).resolve().parents[1] / "supabase_control_bridge.sql").read_text(encoding="utf-8")
        for name in expected:
            self.assertIn("function public." + name, sql)

    def test_cloud_queue_requires_same_chat_and_live_device(self):
        chat_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        device = {
            "session_id": self.session_id,
            "chat_id": chat_id,
            "status": "active",
            "last_seen_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=1)).isoformat(),
        }
        cloud = CloudHistory("https://project.supabase.co", "sb_secret_test", "google:test-owner")
        calls = []

        def fake_call(method, table, filters=None, data=None, prefer=None):
            calls.append((method, table, filters, data))
            if method == "GET" and table == "ma2_control_devices":
                return [device] if filters.get("chat_id") == "eq." + chat_id else []
            return []

        cloud._call = fake_call
        result_id = cloud.create_control_command({
            "session_id": self.session_id,
            "chat_id": chat_id,
            "action": "open_app",
            "arguments": {"app": "notepad", "extra": "dropped"},
        })
        self.assertTrue(uuid.UUID(result_id))
        queued = calls[-1][3]
        self.assertEqual(queued["arguments"], {"app": "notepad"})
        with self.assertRaisesRegex(CloudHistoryError, "not connected"):
            cloud.create_control_command({
                "session_id": self.session_id,
                "chat_id": str(uuid.uuid4()),
                "action": "open_app",
                "arguments": {"app": "notepad"},
            })


if __name__ == "__main__":
    unittest.main()
