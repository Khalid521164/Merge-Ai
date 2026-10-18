r"""Encrypted, per-user Windows settings for Merge AI (standard library only).

The desktop screen saves after a successful Settings apply and loads on startup.
Only DPAPI-protected bytes reach disk; there is no plaintext fallback.
The file lives at %LOCALAPPDATA%\MergeAI\settings.dpapi, outside the project.
Chat history is not saved. Saving makes no network requests.

Windows API references:
https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata
https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata
"""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile


MAGIC = b"MergeAI-DPAPI-v1\x00"
MAX_PLAIN_BYTES = 64 * 1024
MAX_FILE_BYTES = 128 * 1024
LOAD_ERROR = "Saved settings couldn’t be loaded. Open Settings and save your keys again."
SAVE_ERROR = "Couldn’t save settings on this computer. Click Save & apply to try again."
_PROVIDERS = {"gemini", "openrouter", "groq"}


class SettingsStoreError(Exception):
    """A safe message that never contains credentials or native error details."""


def storage_available() -> bool:
    return sys.platform == "win32"


def settings_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    if not base.is_absolute():
        raise SettingsStoreError(SAVE_ERROR)
    return base / "MergeAI" / "settings.dpapi"


class _DataBlob(ctypes.Structure):
    # Windows DWORD is 32 bits on both 32-bit and 64-bit Windows.
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, *, decrypt: bool) -> bytes:
    """Use Windows DPAPI with current-user scope and no interactive prompts."""
    error = LOAD_ERROR if decrypt else SAVE_ERROR
    if not storage_available() or not data or len(data) > MAX_FILE_BYTES:
        raise SettingsStoreError(error)
    try:
        crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    except (AttributeError, OSError):
        raise SettingsStoreError(error) from None
    blob_pointer = ctypes.POINTER(_DataBlob)
    tail = [blob_pointer, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, blob_pointer]
    crypt32.CryptProtectData.argtypes = [blob_pointer, ctypes.c_wchar_p, *tail]
    crypt32.CryptProtectData.restype = ctypes.c_int
    crypt32.CryptUnprotectData.argtypes = [blob_pointer, ctypes.POINTER(ctypes.c_wchar_p), *tail]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _DataBlob()
    try:
        operation = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
        # CRYPTPROTECT_UI_FORBIDDEN = 1. Do not use LOCAL_MACHINE scope.
        ok = operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
        if not ok or not output.pbData or not 0 < output.cbData <= MAX_FILE_BYTES:
            raise SettingsStoreError(error)
        return ctypes.string_at(output.pbData, output.cbData)
    except (OSError, ctypes.ArgumentError):
        raise SettingsStoreError(error) from None
    finally:
        ctypes.memset(buffer, 0, len(data))
        if output.pbData:
            if decrypt and output.cbData <= MAX_FILE_BYTES:
                ctypes.memset(output.pbData, 0, output.cbData)
            kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p))


def _validate_settings(data: object) -> dict:
    fields = {"providers", "tavily_api_key", "merger", "fast_mode", "web_search", "allow_partial"}
    if not isinstance(data, dict) or set(data) != fields:
        raise SettingsStoreError(LOAD_ERROR)
    providers = data["providers"]
    if not isinstance(providers, list) or len(providers) != 3:
        raise SettingsStoreError(LOAD_ERROR)
    names = []
    for provider in providers:
        if not isinstance(provider, dict) or set(provider) != {"name", "model", "api_key"}:
            raise SettingsStoreError(LOAD_ERROR)
        if not all(isinstance(provider[k], str) for k in ("name", "model", "api_key")):
            raise SettingsStoreError(LOAD_ERROR)
        names.append(provider["name"])
    if set(names) != _PROVIDERS:
        raise SettingsStoreError(LOAD_ERROR)
    if not isinstance(data["merger"], str) or data["merger"] not in _PROVIDERS:
        raise SettingsStoreError(LOAD_ERROR)
    if not isinstance(data["tavily_api_key"], str):
        raise SettingsStoreError(LOAD_ERROR)
    if not all(type(data[name]) is bool for name in ("fast_mode", "web_search", "allow_partial")):
        raise SettingsStoreError(LOAD_ERROR)
    return data


def load_settings() -> dict | None:
    """Return saved settings, or None on first launch/non-Windows systems."""
    if not storage_available():
        return None
    try:
        with settings_path().open("rb") as file:
            encrypted = file.read(MAX_FILE_BYTES + 1)
        if len(encrypted) > MAX_FILE_BYTES or not encrypted.startswith(MAGIC):
            raise SettingsStoreError(LOAD_ERROR)
        raw = _crypt(encrypted[len(MAGIC):], decrypt=True)
        if len(raw) > MAX_PLAIN_BYTES:
            raise SettingsStoreError(LOAD_ERROR)
        document = json.loads(raw.decode("utf-8"))
        if not isinstance(document, dict) or type(document.get("version")) is not int or document["version"] != 1:
            raise SettingsStoreError(LOAD_ERROR)
        return _validate_settings(document.get("settings"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, ValueError, RuntimeError, RecursionError, SettingsStoreError):
        raise SettingsStoreError(LOAD_ERROR) from None


def save_settings(settings: dict) -> None:
    """Encrypt first, then atomically replace the previous encrypted file."""
    if not storage_available():
        raise SettingsStoreError("Automatic key saving is available on Windows.")
    temporary = None
    try:
        data = _validate_settings(settings)
        raw = json.dumps({"version": 1, "settings": data}, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_PLAIN_BYTES:
            raise SettingsStoreError(SAVE_ERROR)
        encrypted = MAGIC + _crypt(raw, decrypt=False)
        if len(encrypted) > MAX_FILE_BYTES:
            raise SettingsStoreError(SAVE_ERROR)
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=path.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as file:
            file.write(encrypted)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError, TypeError, RuntimeError, SettingsStoreError):
        raise SettingsStoreError(SAVE_ERROR) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # A leftover temporary file also contains only encrypted bytes.
