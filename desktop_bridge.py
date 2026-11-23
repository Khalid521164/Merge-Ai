"""Visible Windows companion for Merge AI Desktop Control Mode.

This companion makes an outbound HTTPS connection to Supabase. It does not
open a listening port, accept arbitrary shell commands, or run invisibly.
Only explicitly approved, allowlisted actions are executed.
"""
from __future__ import annotations

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

from jarvis_control import (
    ALLOWED_APPS,
    ALLOWED_KEYS,
    ALLOWED_HOTKEYS,
    MAX_TEXT_LENGTH,
    MAX_SCROLL_TICKS,
    BridgeClient,
    encode_screenshot_jpeg,
    load_pairing_file,
    normalize_desktop_action,
)


APP_NAME = "Merge AI Desktop Bridge"
POLL_SECONDS = 2.0
HEARTBEAT_SECONDS = 5.0
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


def screen_size():
    width, height = pyautogui.size()
    return int(width), int(height)


def take_screenshot() -> str:
    with mss.mss() as capture:
        monitor = capture.monitors[1]
        shot = capture.grab(monitor)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
    return encode_screenshot_jpeg(image)


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
    if name == "vscode":
        candidates.extend([
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
            / "Programs/Microsoft VS Code/Code.exe",
            Path(os.environ.get("ProgramFiles", r"C:\\Program Files"))
            / "Microsoft VS Code/Code.exe",
        ])
        found = shutil.which("code")
    elif name == "edge":
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
    normalized = normalize_desktop_action(action, args)
    action = normalized["action"]
    args = normalized["arguments"]

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
        position = str(args.get("position", "")).lower()
        if position in {"top-left", "top-right", "bottom-left", "bottom-right", "center"}:
            positions = {"top-left": (8, 8), "top-right": (width - 8, 8), "bottom-left": (8, height - 8), "bottom-right": (width - 8, height - 8), "center": (width // 2, height // 2)}
            x, y = positions[position]
        else:
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
        self.last_disconnect_error = ""

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
            root, text="Load temporary pairing file…",
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
            self.config = config
            self.client = BridgeClient(config)
            self.last_disconnect_error = ""
            self.session_label.config(
                text="Session " + config["session_id"][:8] + "… · Pairing loaded"
            )
            self.start_button.config(state="normal")
            messagebox.showinfo(
                APP_NAME,
                "Pairing loaded. The session token stays in memory while this companion is open.",
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
        self.last_disconnect_error = ""
        self.start_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status.config(text="● CONNECTING…", fg="#f3bd70")
        self.worker = threading.Thread(target=self.run_loop, daemon=True)
        self.worker.start()

    def run_loop(self):
        last_heartbeat = 0.0
        retry_delay = 1.0
        try:
            while not self.stop_event.is_set():
                now = time.time()
                try:
                    if now - last_heartbeat >= HEARTBEAT_SECONDS:
                        if not self.client.heartbeat():
                            raise RuntimeError("Pairing expired, was revoked, or is no longer active.")
                        last_heartbeat = now
                        retry_delay = 1.0
                        self.events.put(("status", "● ACTIVE — REMOTE CONTROL READY"))
                    for command in self.client.claim():
                        if self.stop_event.is_set():
                            break
                        self.execute_command(command)
                    self.stop_event.wait(POLL_SECONDS)
                except requests.exceptions.RequestException as exc:
                    response = getattr(exc, "response", None)
                    status_code = getattr(response, "status_code", 0) or 0
                    retryable = (
                        isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
                        or status_code in (408, 425, 429)
                        or status_code >= 500
                    )
                    if not retryable:
                        raise
                    self.events.put(("status", "● RECONNECTING — temporary network interruption"))
                    self.stop_event.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, 30.0)
                    last_heartbeat = 0.0
        except pyautogui.FailSafeException:
            self.events.put(("error", "Emergency mouse failsafe activated."))
        except Exception as exc:
            self.last_disconnect_error = str(exc)[:220]
            self.events.put(("error", str(exc)[:220]))
        finally:
            if self.client:
                threading.Thread(
                    target=self._revoke_remote_session,
                    args=(self.client,),
                    daemon=True,
                ).start()
            self.events.put(("stopped", ""))

    def execute_command(self, command: dict):
        command_id = str(command.get("command_id") or "")
        try:
            uuid.UUID(command_id)
            action = str(command.get("action") or "")
            arguments = command.get("arguments") or {}
            self.events.put(("command", f"Running approved action: {action}"))
            result = validate_and_execute(action, arguments)
        except Exception as exc:
            try:
                if command_id:
                    recorded = self.client.complete(command_id, "failed", str(exc)[:500])
                else:
                    recorded = False
            except Exception:
                recorded = False
            if recorded:
                self.events.put(("result", f"Action failed: {str(exc)[:160]}"))
            else:
                self.events.put(("result", "Action failed, but Jarvis could not confirm the result."))
            return

        try:
            recorded = self.client.complete(command_id, "completed", result)
        except Exception:
            recorded = False
        if recorded:
            self.events.put(("result", f"Completed: {result[:180]}"))
        else:
            self.events.put((
                "result",
                "The action may have run, but Jarvis could not confirm the result. Check this PC before retrying.",
            ))

    def stop(self):
        self.stop_event.set()
        if self.client:
            threading.Thread(target=self._revoke_remote_session, args=(self.client,), daemon=True).start()
        self.status.config(text="● STOPPING", fg="#f3bd70")
        self.stop_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.start_button.config(state="disabled")

    def _revoke_remote_session(self, client):
        try:
            client.stop_session()
        except Exception:
            pass

    def process_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.connected = True
                    color = "#f3bd70" if value.startswith("● RECONNECTING") else "#80e6b5"
                    self.status.config(text=value, fg=color)
                elif kind == "command":
                    self.status.config(text="● ACTIVE · " + value[:48], fg="#f5cc7b")
                elif kind == "result":
                    self.status.config(text="● ACTIVE · " + value[:50], fg="#80e6b5")
                elif kind == "error":
                    self.connected = False
                    self.last_disconnect_error = value
                    self.status.config(text="● ERROR · " + value[:55], fg="#ff8492")
                    self.stop_event.set()
                elif kind == "stopped":
                    self.connected = False
                    label = "● DISCONNECTED"
                    if self.last_disconnect_error:
                        label += " · " + self.last_disconnect_error[:36]
                    self.status.config(text=label, fg="#ff8492" if self.last_disconnect_error else "#f3bd70")
                    self.config = None
                    self.client = None
                    self.start_button.config(state="disabled")
                    self.load_button.config(state="normal")
                    self.stop_button.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(250, self.process_events)

    def on_close(self):
        self.stop_event.set()
        if self.client:
            threading.Thread(target=self._revoke_remote_session, args=(self.client,), daemon=True).start()
        self.root.destroy()


def main():
    root = tk.Tk()
    DesktopBridgeWindow(root)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_file():
        try:
            config = load_pairing_file(sys.argv[1])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
    main()
