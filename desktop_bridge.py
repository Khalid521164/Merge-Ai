"""Visible Windows companion for Merge AI Desktop Control Mode.

This companion makes an outbound HTTPS connection to Supabase. It does not
open a listening port, accept arbitrary shell commands, or run invisibly.
Only explicitly approved, allowlisted actions are executed.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from urllib.parse import urlsplit
import uuid
import webbrowser

import mss
from PIL import Image
import pyautogui
import pyperclip
import requests


APP_NAME = "Merge AI Desktop Bridge"
ALLOWED_APPS = {"notepad", "calculator", "paint", "explorer", "chrome", "edge"}
ALLOWED_KEYS = {
    "enter", "esc", "tab", "space", "backspace", "delete",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
}
ALLOWED_HOTKEYS = {
    ("ctrl", "a"), ("ctrl", "c"), ("ctrl", "v"), ("ctrl", "x"),
    ("ctrl", "s"), ("ctrl", "z"), ("ctrl", "y"), ("ctrl", "f"),
    ("ctrl", "w"), ("ctrl", "t"), ("alt", "tab"), ("alt", "f4"),
    ("win", "d"), ("win", "e"),
}
MAX_TEXT_LENGTH = 3000
MAX_SCROLL_TICKS = 15
POLL_SECONDS = 2.0
HEARTBEAT_SECONDS = 5.0
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


def app_data_dir() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local")
    directory = root / "MergeAI"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def secure_config_path() -> Path:
    return app_data_dir() / "bridge_pairing.json"


def load_pairing_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    base_url = str(data.get("supabase_url", "")).strip().rstrip("/")
    anon_key = str(data.get("supabase_anon_key", "")).strip()
    session_id = str(data.get("session_id", "")).strip()
    token = str(data.get("device_token", "")).strip()
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").endswith(".supabase.co")
        or parsed.username or parsed.password or parsed.port
        or parsed.path not in ("", "/") or parsed.query or parsed.fragment
    ):
        raise ValueError("The pairing file contains an invalid Supabase project URL.")
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise ValueError("The pairing file contains an invalid session ID.") from None
    if not anon_key or len(token) < 32:
        raise ValueError("The pairing file is missing its public key or session token.")
    return {
        "supabase_url": base_url,
        "supabase_anon_key": anon_key,
        "session_id": session_id,
        "device_token": token,
    }


def token_hash(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class BridgeClient:
    def __init__(self, config: dict):
        self.config = config
        self.base = config["supabase_url"] + "/rest/v1/rpc/"
        self.headers = {
            "apikey": config["supabase_anon_key"],
            "Authorization": "Bearer " + config["supabase_anon_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MergeAI-Desktop-Bridge/1.0",
        }
        self.session_id = config["session_id"]
        self.secret_hash = token_hash(config["device_token"])
        self.http = requests.Session()

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
        value = self.rpc("ma2_bridge_heartbeat", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
        })
        return bool(value)

    def claim(self):
        value = self.rpc("ma2_bridge_claim_commands", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
            "p_limit": 2,
        })
        return value if isinstance(value, list) else []

    def complete(self, command_id: str, status: str, result_text: str):
        return self.rpc("ma2_bridge_complete_command", {
            "p_session_id": self.session_id,
            "p_token_hash": self.secret_hash,
            "p_command_id": command_id,
            "p_status": status,
            "p_result_text": result_text[:480000],
        })


def screen_size():
    width, height = pyautogui.size()
    return int(width), int(height)


def take_screenshot() -> str:
    with mss.mss() as capture:
        monitor = capture.monitors[1]
        shot = capture.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
    image.thumbnail((1400, 1000))
    from io import BytesIO
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=58, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "SCREENSHOT_JPEG_BASE64:" + encoded


def resolve_app(app_name: str) -> str:
    name = str(app_name or "").strip().lower()
    if name not in ALLOWED_APPS:
        raise ValueError("That application is not on the allowed-app list.")
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    system32 = windows / "System32"
    fixed = {
        "notepad": system32 / "notepad.exe",
        "calculator": system32 / "calc.exe",
        "paint": system32 / "mspaint.exe",
        "explorer": system32 / "explorer.exe",
    }
    if name in fixed:
        return str(fixed[name])
    candidates = []
    if name == "edge":
        candidates.extend([
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Microsoft/Edge/Application/msedge.exe",
        ])
        found = shutil.which("msedge")
    else:
        candidates.extend([
            Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
            / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
            / "Google/Chrome/Application/chrome.exe",
        ])
        found = shutil.which("chrome")
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    if found:
        return found
    raise ValueError(f"{name.title()} was not found on this computer.")


def validate_and_execute(action: str, args: dict) -> str:
    if not isinstance(args, dict):
        raise ValueError("Command arguments must be an object.")

    if action == "screenshot":
        return take_screenshot()

    if action == "open_app":
        app_name = str(args.get("app", "")).lower()
        executable = resolve_app(app_name)
        subprocess.Popen([executable], shell=False)
        return f"Opened {app_name.title()}."

    if action == "open_url":
        url = str(args.get("url", "")).strip()
        parsed = urlsplit(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Only ordinary HTTP/HTTPS web addresses are allowed.")
        webbrowser.open(url, new=2)
        return "Opened the approved web address in your default browser."

    width, height = screen_size()

    if action in ("click", "move_mouse"):
        x, y = int(args.get("x", -1)), int(args.get("y", -1))
        if x < 0 or y < 0 or x >= width or y >= height:
            raise ValueError(f"Coordinates must be within the {width}×{height} screen.")
        if action == "click":
            pyautogui.click(x, y)
            return f"Clicked at ({x}, {y})."
        pyautogui.moveTo(x, y, duration=0.2)
        return f"Moved the pointer to ({x}, {y})."

    if action == "type_text":
        text = str(args.get("text", ""))
        if not text or len(text) > MAX_TEXT_LENGTH:
            raise ValueError(f"Text must contain 1–{MAX_TEXT_LENGTH} characters.")
        old_clipboard = None
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            pass
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        if old_clipboard is not None:
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
        return f"Typed {len(text)} characters."

    if action == "hotkey":
        keys = args.get("keys")
        if not isinstance(keys, list) or not 1 <= len(keys) <= 3:
            raise ValueError("Hotkey must contain 1–3 approved keys.")
        keys = tuple(str(key).lower() for key in keys)
        if not all(key in {"ctrl", "alt", "shift", "win"} | ALLOWED_KEYS for key in keys):
            raise ValueError("That keyboard key is not allowed.")
        if keys not in ALLOWED_HOTKEYS and not (
            len(keys) == 1 and keys[0] in ALLOWED_KEYS
        ):
            raise ValueError("That keyboard shortcut is not on the allowlist.")
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return "Pressed " + "+".join(keys) + "."

    if action == "scroll":
        direction = str(args.get("direction", "")).lower()
        ticks = int(args.get("ticks", 3))
        if direction not in ("up", "down") or not 1 <= ticks <= MAX_SCROLL_TICKS:
            raise ValueError("Scroll direction or amount is invalid.")
        pyautogui.scroll(ticks if direction == "up" else -ticks)
        return f"Scrolled {direction} {ticks} steps."

    raise ValueError("This action is not supported by the desktop bridge.")


class DesktopBridgeWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("560x430")
        self.root.minsize(520, 390)
        self.root.configure(bg="#101827")
        self.config = None
        self.client = None
        self.worker = None
        self.stop_event = threading.Event()
        self.events = queue.Queue()
        self.connected = False

        tk.Label(
            root, text="MERGE AI", fg="#8fe8dc", bg="#101827",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=22, pady=(20, 0))
        tk.Label(
            root, text="Desktop Bridge", fg="#f6f8fb", bg="#101827",
            font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w", padx=22, pady=(2, 4))
        tk.Label(
            root,
            text="A visible, permission-based connection between Jarvis and this PC.",
            fg="#9db0c5", bg="#101827", font=("Segoe UI", 10),
        ).pack(anchor="w", padx=22, pady=(0, 18))

        self.status = tk.Label(
            root, text="● DISCONNECTED", fg="#f3bd70", bg="#101827",
            font=("Segoe UI", 11, "bold"),
        )
        self.status.pack(anchor="w", padx=22, pady=(0, 10))

        self.session_label = tk.Label(
            root, text="No pairing file loaded.", fg="#a9b7c8",
            bg="#101827", font=("Segoe UI", 9),
        )
        self.session_label.pack(anchor="w", padx=22, pady=(0, 14))

        self.consent = tk.BooleanVar(value=False)
        tk.Checkbutton(
            root,
            text="I allow commands that I explicitly approve in Merge AI.",
            variable=self.consent,
            fg="#e8eef5", bg="#101827", activebackground="#101827",
            activeforeground="#fff", selectcolor="#203148",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self.load_button = tk.Button(
            root, text="Load one-time pairing file…",
            command=self.load_file, bg="#24364d", fg="#f7f9fc",
            activebackground="#314965", activeforeground="#fff",
            relief="flat", padx=14, pady=10,
        )
        self.load_button.pack(fill="x", padx=22, pady=4)

        self.start_button = tk.Button(
            root, text="Start secure connection",
            command=self.start, bg="#147d72", fg="#fff",
            activebackground="#189688", activeforeground="#fff",
            relief="flat", padx=14, pady=10, state="disabled",
        )
        self.start_button.pack(fill="x", padx=22, pady=4)

        self.stop_button = tk.Button(
            root, text="■  STOP REMOTE CONTROL",
            command=self.stop, bg="#9d283b", fg="#fff",
            activebackground="#bb3149", activeforeground="#fff",
            relief="flat", padx=14, pady=12, state="disabled",
        )
        self.stop_button.pack(fill="x", padx=22, pady=(10, 5))

        tk.Label(
            root,
            text="The window stays visible while connected. Use STOP or move the mouse to the top-left corner for the emergency failsafe. Only approved, allowlisted actions run; arbitrary shell commands are blocked.",
            wraplength=500, justify="left", fg="#8ca1b7",
            bg="#101827", font=("Segoe UI", 8),
        ).pack(anchor="w", padx=22, pady=(12, 0))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(250, self.process_events)

    def load_file(self):
        filename = filedialog.askopenfilename(
            title="Select Merge AI pairing file",
            filetypes=[("Merge AI pairing file", "*.json"), ("JSON files", "*.json")],
        )
        if not filename:
            return
        try:
            config = load_pairing_file(filename)
            target = secure_config_path()
            target.write_text(json.dumps(config), encoding="utf-8")
            self.config = config
            self.client = BridgeClient(config)
            self.session_label.config(
                text="Session " + config["session_id"][:8] + "… · Pairing loaded"
            )
            self.start_button.config(state="normal")
            messagebox.showinfo(
                APP_NAME,
                "Pairing file loaded. Its session token was saved inside your Windows user profile.",
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def start(self):
        if not self.config or not self.client:
            messagebox.showwarning(APP_NAME, "Load the pairing file first.")
            return
        if not self.consent.get():
            messagebox.showwarning(
                APP_NAME,
                "Check the permission box to confirm that you allow explicitly approved commands.",
            )
            return
        self.stop_event.clear()
        self.start_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status.config(text="● CONNECTING…", fg="#f3bd70")
        self.worker = threading.Thread(target=self.run_loop, daemon=True)
        self.worker.start()

    def run_loop(self):
        last_heartbeat = 0.0
        try:
            while not self.stop_event.is_set():
                now = time.time()
                if now - last_heartbeat >= HEARTBEAT_SECONDS:
                    if not self.client.heartbeat():
                        raise RuntimeError("Pairing expired, was revoked, or is no longer active.")
                    last_heartbeat = now
                    self.events.put(("status", "● ACTIVE — REMOTE CONTROL READY"))
                for command in self.client.claim():
                    if self.stop_event.is_set():
                        break
                    self.execute_command(command)
                self.stop_event.wait(POLL_SECONDS)
        except pyautogui.FailSafeException:
            self.events.put(("error", "Emergency mouse failsafe activated."))
        except Exception as exc:
            self.events.put(("error", str(exc)[:220]))
        finally:
            self.events.put(("stopped", ""))

    def execute_command(self, command: dict):
        command_id = str(command.get("command_id") or "")
        try:
            uuid.UUID(command_id)
            action = str(command.get("action") or "")
            arguments = command.get("arguments") or {}
            self.events.put(("command", f"Running approved action: {action}"))
            result = validate_and_execute(action, arguments)
            self.client.complete(command_id, "completed", result)
            self.events.put(("result", f"Completed: {result[:180]}"))
        except Exception as exc:
            try:
                if command_id:
                    self.client.complete(command_id, "failed", str(exc)[:500])
            except Exception:
                pass
            self.events.put(("result", f"Action failed: {str(exc)[:180]}"))

    def stop(self):
        self.stop_event.set()
        self.status.config(text="● STOPPING", fg="#f3bd70")
        self.stop_button.config(state="disabled")
        self.load_button.config(state="normal")
        self.start_button.config(state="normal")

    def process_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.connected = True
                    self.status.config(text=value, fg="#80e6b5")
                elif kind == "command":
                    self.status.config(text="● ACTIVE · " + value[:48], fg="#f5cc7b")
                elif kind == "result":
                    self.status.config(text="● ACTIVE · " + value[:50], fg="#80e6b5")
                elif kind == "error":
                    self.connected = False
                    self.status.config(text="● ERROR · " + value[:55], fg="#ff8492")
                    self.stop_event.set()
                elif kind == "stopped":
                    self.connected = False
                    self.status.config(text="● DISCONNECTED", fg="#f3bd70")
                    self.start_button.config(state="normal")
                    self.load_button.config(state="normal")
                    self.stop_button.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(250, self.process_events)

    def on_close(self):
        self.stop_event.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    DesktopBridgeWindow(root)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        try:
            config = load_pairing_file(sys.argv[1])
            target = secure_config_path()
            target.write_text(json.dumps(config), encoding="utf-8")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
    main()
