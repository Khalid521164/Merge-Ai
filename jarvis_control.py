"""Shared validation and relay helpers for Jarvis desktop control."""
from __future__ import annotations

import base64
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit


PUBLIC_KEY_SECRET_NAMES = ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY")
ALLOWED_APPS = frozenset({"notepad", "calculator", "paint", "explorer", "chrome", "edge", "vscode"})
ALLOWED_KEYS = frozenset({
    "enter", "esc", "tab", "space", "backspace", "delete", "up", "down",
    "left", "right", "home", "end", "pageup", "pagedown",
})
ALLOWED_HOTKEYS = frozenset({
    ("ctrl", "a"), ("ctrl", "c"), ("ctrl", "v"), ("ctrl", "x"),
    ("ctrl", "s"), ("ctrl", "z"), ("ctrl", "y"), ("ctrl", "f"),
    ("ctrl", "w"), ("ctrl", "t"), ("alt", "tab"), ("alt", "f4"),
    ("win", "d"), ("win", "e"),
})
ALLOWED_POSITIONS = frozenset({"top-left", "top-right", "bottom-left", "bottom-right", "center"})
MAX_TEXT_LENGTH = 3000
MAX_SCROLL_TICKS = 15
MAX_SCREENSHOT_SIZE = (1400, 1000)
MAX_SCREENSHOT_RESULT_BYTES = 480000
SCREENSHOT_PREFIX = "SCREENSHOT_JPEG_BASE64:"
MAX_RPC_RESULT_LENGTH = 500000
HEARTBEAT_FRESH_SECONDS = 30


def resolve_public_key(secret_getter):
    """Prefer the current publishable key, then accept the legacy anon key."""
    for name in PUBLIC_KEY_SECRET_NAMES:
        value = str(secret_getter(name) or "").strip()
        if value:
            return value
    return ""


def _legacy_jwt_role(key):
    parts = str(key or "").split(".")
    if len(parts) != 3 or not parts[0].startswith("eyJ"):
        return None
    try:
        encoded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")))
    except (ValueError, UnicodeError, json.JSONDecodeError):
        return None
    return claims.get("role") if isinstance(claims, dict) else None


def validate_server_key(key: str) -> str:
    key = str(key or "").strip()
    if key.startswith("sb_secret_") or _legacy_jwt_role(key) == "service_role":
        return key
    if key.startswith("sb_publishable_") or _legacy_jwt_role(key) == "anon":
        raise ValueError("A Supabase server secret key is required; a publishable or anon key cannot access private chat storage.")
    raise ValueError("Use SUPABASE_SECRET_KEY or the legacy SUPABASE_SERVICE_ROLE_KEY for server-side storage.")


def validate_public_key(key: str) -> str:
    key = str(key or "").strip()
    if key.startswith("sb_publishable_"):
        return key
    if key.startswith("sb_secret_"):
        raise ValueError("A public Supabase publishable or legacy anon key is required; server secret keys cannot be used by the desktop companion.")
    # Legacy Supabase public and service-role keys are JWTs. Inspect only the
    # untrusted role claim to prevent accidentally packaging a service-role key.
    role = _legacy_jwt_role(key)
    if role:
        if role == "anon":
            return key
        if role == "service_role":
            raise ValueError("A public Supabase publishable or legacy anon key is required; server secret keys cannot be used by the desktop companion.")
    raise ValueError("The desktop companion requires a Supabase publishable key or legacy anon key.")


def supabase_api_headers(public_key: str) -> dict:
    """Build headers without treating new opaque keys as JWT bearer tokens."""
    key = validate_public_key(public_key)
    headers = {"apikey": key}
    if not key.startswith("sb_"):
        headers["Authorization"] = "Bearer " + key
    return headers


def _integer(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value)
    raise ValueError(f"{label} must be an integer.")


def normalize_desktop_action(action, arguments):
    """Validate and strip an action payload to its supported fields."""
    action = str(action or "").strip().lower()
    if not isinstance(arguments, dict):
        raise ValueError("Command arguments must be an object.")

    if action == "screenshot":
        return {"action": action, "arguments": {}}
    if action == "open_app":
        name = str(arguments.get("app") or "").strip().lower()
        if name not in ALLOWED_APPS:
            raise ValueError("That application is not on the allowed-app list.")
        return {"action": action, "arguments": {"app": name}}
    if action == "open_url":
        url = arguments.get("url")
        if not isinstance(url, str):
            raise ValueError("Only ordinary HTTP/HTTPS web addresses are allowed.")
        url = url.strip()
        parsed = urlsplit(url)
        if (
            len(url) > 2000
            or parsed.scheme.lower() not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(ord(ch) < 32 for ch in url)
        ):
            raise ValueError("Only ordinary HTTP/HTTPS web addresses are allowed.")
        return {"action": action, "arguments": {"url": url}}
    if action in ("click", "move_mouse"):
        position = str(arguments.get("position") or "").strip().lower()
        if position in ALLOWED_POSITIONS:
            return {"action": action, "arguments": {"position": position}}
        x = _integer(arguments.get("x"), "X coordinate")
        y = _integer(arguments.get("y"), "Y coordinate")
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            raise ValueError("Screen coordinates must be between 0 and 10000.")
        return {"action": action, "arguments": {"x": x, "y": y}}
    if action == "type_text":
        value = arguments.get("text")
        if not isinstance(value, str) or not (1 <= len(value) <= MAX_TEXT_LENGTH):
            raise ValueError(f"Text must contain 1–{MAX_TEXT_LENGTH} characters.")
        return {"action": action, "arguments": {"text": value}}
    if action == "hotkey":
        keys = arguments.get("keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 3:
            raise ValueError("Hotkey must contain 1–3 approved keys.")
        if any(not isinstance(key, str) for key in keys):
            raise ValueError("That keyboard key is not allowed.")
        normalized = tuple(key.strip().lower() for key in keys)
        if normalized not in ALLOWED_HOTKEYS and not (
            len(normalized) == 1 and normalized[0] in ALLOWED_KEYS
        ):
            raise ValueError("That keyboard shortcut is not on the allowlist.")
        return {"action": action, "arguments": {"keys": list(normalized)}}
    if action == "scroll":
        direction = str(arguments.get("direction") or "").strip().lower()
        ticks = _integer(arguments.get("ticks", 3), "Scroll amount")
        if direction not in ("up", "down") or not 1 <= ticks <= MAX_SCROLL_TICKS:
            raise ValueError("Scroll direction or amount is invalid.")
        return {"action": action, "arguments": {"direction": direction, "ticks": ticks}}
    raise ValueError("This action is not supported by the desktop bridge.")


def requires_extra_confirmation(action, arguments=None):
    """Add a second approval before clicks or Enter can submit/activate UI."""
    action = str(action or "").strip().lower()
    if action == "click":
        return True
    if action == "hotkey":
        arguments = arguments if isinstance(arguments, dict) else {}
        return "enter" in tuple(str(key).strip().lower() for key in (arguments.get("keys") or []))
    return False


def parse_desktop_action_response(text):
    """Parse a model response and validate its single proposed action."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw[3:]
        if raw[:4].lower() == "json":
            raw = raw[4:]
        raw = raw.split("```", 1)[0].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    action = str(parsed.get("action") or "no_action").strip().lower()
    if action == "no_action":
        return None
    try:
        return normalize_desktop_action(action, parsed.get("arguments") or {})
    except (TypeError, ValueError):
        return None


def find_control_agent_request(question, agents):
    """Match an explicit ask-to-agent phrase against configured agents."""
    clean = str(question or "").strip()
    clean = re.sub(r"^(?:hey\s+)?jarvis\b[,:]?\s*", "", clean, flags=re.IGNORECASE)
    available = [agent for agent in agents if isinstance(agent, dict)]
    available.sort(key=lambda item: len(str(item.get("name") or "")), reverse=True)
    for agent in available:
        names = list(dict.fromkeys((
            str(agent.get("name") or "").strip(),
            str(agent.get("role_name") or "").strip(),
        )))
        for name in names:
            if not name:
                continue
            pattern = (
                r"^(?:please\s+)?(?:ask|have|tell|consult)\s+"
                + re.escape(name)
                + r"\s+(?:to|about|for|:)\s*(.+)$"
            )
            match = re.match(pattern, clean, flags=re.IGNORECASE | re.DOTALL)
            if match and match.group(1).strip():
                return agent, match.group(1).strip()
    return None


def is_device_live(device, now=None, freshness_seconds=HEARTBEAT_FRESH_SECONDS):
    """Require active status, an unexpired session, and a recent heartbeat."""
    if not isinstance(device, dict) or device.get("status") != "active":
        return False
    now = now or datetime.now(timezone.utc)

    def parse_timestamp(value):
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    last_seen = parse_timestamp(device.get("last_seen_at"))
    expires_at = parse_timestamp(device.get("expires_at"))
    if not last_seen or not expires_at:
        return False
    age = (now.astimezone(timezone.utc) - last_seen).total_seconds()
    return -5 <= age <= freshness_seconds and expires_at > now.astimezone(timezone.utc)


def load_pairing_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("The pairing file is not a JSON object.")
    base_url = str(data.get("supabase_url", "")).strip().rstrip("/")
    public_key = str(
        data.get("supabase_public_key") or data.get("supabase_publishable_key")
        or data.get("supabase_anon_key") or ""
    ).strip()
    session_id = str(data.get("session_id", "")).strip()
    token = str(data.get("device_token", "")).strip()
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").lower().endswith(".supabase.co")
        or parsed.hostname == ".supabase.co"
        or parsed.username or parsed.password or parsed.port
        or parsed.path not in ("", "/") or parsed.query or parsed.fragment
    ):
        raise ValueError("The pairing file contains an invalid Supabase project URL.")
    try:
        session_id = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("The pairing file contains an invalid session ID.") from None
    try:
        validate_public_key(public_key)
    except ValueError as exc:
        raise ValueError("The pairing file contains an invalid public Supabase key.") from exc
    if not (32 <= len(token) <= 128) or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ValueError("The pairing file is missing a valid temporary session token.")
    return {
        "supabase_url": base_url,
        "supabase_public_key": public_key,
        "session_id": session_id,
        "device_token": token,
    }


def token_hash(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def encode_screenshot_jpeg(image) -> str:
    """Return a bounded JPEG data URL payload for the command result relay."""
    from io import BytesIO

    image = image.copy()
    image.thumbnail(MAX_SCREENSHOT_SIZE)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=58, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    if len(encoded) > MAX_SCREENSHOT_RESULT_BYTES:
        raise ValueError("Screenshot is too large to return to Jarvis.")
    return SCREENSHOT_PREFIX + encoded


class BridgeClient:
    """Small Supabase RPC client shared by the visible desktop companion."""
    def __init__(self, config: dict, session=None):
        self.config = config
        self.base = config["supabase_url"].rstrip("/") + "/rest/v1/rpc/"
        self.headers = {
            **supabase_api_headers(config["supabase_public_key"]),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MergeAI-Desktop-Bridge/1.0",
        }
        self.session_id = str(uuid.UUID(str(config["session_id"])))
        self.secret_hash = token_hash(config["device_token"])
        if session is None:
            import requests
            session = requests.Session()
        self.http = session

    def rpc(self, name: str, payload: dict):
        response = self.http.post(
            self.base + name,
            headers=self.headers,
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        return response.json()

    def heartbeat(self) -> bool:
        return bool(self.rpc("ma2_bridge_heartbeat", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
        }))

    def claim(self):
        value = self.rpc("ma2_bridge_claim_commands", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
            "p_limit": 2,
        })
        return value if isinstance(value, list) else []

    def stop_session(self):
        return self.rpc("ma2_bridge_stop", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
        })

    def complete(self, command_id: str, status: str, result_text: str):
        if status not in ("completed", "failed"):
            raise ValueError("Invalid desktop command result status.")
        result_text = str(result_text or "")
        if result_text.startswith(SCREENSHOT_PREFIX) and len(result_text) > MAX_SCREENSHOT_RESULT_BYTES + len(SCREENSHOT_PREFIX):
            raise ValueError("Screenshot result is too large.")
        return self.rpc("ma2_bridge_complete_command", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
            "p_command_id": str(uuid.UUID(str(command_id))),
            "p_status": status,
            "p_result_text": result_text[:MAX_RPC_RESULT_LENGTH],
        })
