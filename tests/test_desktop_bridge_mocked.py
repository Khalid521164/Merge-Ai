"""Desktop execution tests with the OS and input devices mocked."""
from __future__ import annotations

import base64
import importlib
import queue
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from PIL import Image


class FakeCapture:
    monitors = [{}, {"left": 0, "top": 0, "width": 2, "height": 2}]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def grab(self, monitor):
        return SimpleNamespace(size=(2, 2), rgb=bytes([40, 80, 120] * 4))


def load_bridge_with_mocks():
    pyautogui = ModuleType("pyautogui")
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    pyautogui.FailSafeException = type("FailSafeException", (Exception,), {})
    pyautogui.size = Mock(return_value=(640, 480))
    pyautogui.click = Mock()
    pyautogui.moveTo = Mock()
    pyautogui.hotkey = Mock()
    pyautogui.press = Mock()
    pyautogui.scroll = Mock()

    mss = ModuleType("mss")
    mss.mss = FakeCapture

    pyperclip = ModuleType("pyperclip")
    pyperclip.paste = Mock(return_value="previous clipboard")
    pyperclip.copy = Mock()

    tkinter = ModuleType("tkinter")
    tkinter.filedialog = ModuleType("tkinter.filedialog")
    tkinter.messagebox = ModuleType("tkinter.messagebox")
    modules = {
        "pyautogui": pyautogui,
        "mss": mss,
        "pyperclip": pyperclip,
        "tkinter": tkinter,
        "tkinter.filedialog": tkinter.filedialog,
        "tkinter.messagebox": tkinter.messagebox,
    }
    with patch.dict(sys.modules, modules):
        sys.modules.pop("desktop_bridge", None)
        bridge = importlib.import_module("desktop_bridge")
    return bridge, pyautogui, pyperclip


class DesktopBridgeExecutionTests(unittest.TestCase):
    def setUp(self):
        self.bridge, self.pyautogui, self.pyperclip = load_bridge_with_mocks()

    def test_click_uses_validated_coordinates(self):
        result = self.bridge.validate_and_execute("click", {"x": 10, "y": 20})
        self.assertIn("(10, 20)", result)
        self.pyautogui.click.assert_called_once_with(10, 20)

    def test_rejects_unlisted_shell_action_before_execution(self):
        with patch.object(self.bridge.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(ValueError, "not supported"):
                self.bridge.validate_and_execute("run_shell", {"command": "whoami"})
        popen.assert_not_called()

    def test_open_app_uses_allowlisted_executable_without_shell(self):
        with patch.object(self.bridge, "resolve_app", return_value="C:\\Windows\\notepad.exe"), \
                patch.object(self.bridge.subprocess, "Popen") as popen:
            result = self.bridge.validate_and_execute("open_app", {"app": "notepad"})
        self.assertEqual(result, "Opened Notepad.")
        popen.assert_called_once_with(["C:\\Windows\\notepad.exe"], shell=False)

    def test_text_action_restores_previous_clipboard(self):
        result = self.bridge.validate_and_execute("type_text", {"text": "hello Jarvis"})
        self.assertEqual(result, "Typed 12 characters.")
        self.assertEqual(self.pyperclip.copy.call_args_list[0].args[0], "hello Jarvis")
        self.assertEqual(self.pyperclip.copy.call_args_list[-1].args[0], "previous clipboard")
        self.pyautogui.hotkey.assert_called_once_with("ctrl", "v")

    def test_screenshot_is_encoded_without_capturing_a_real_screen(self):
        result = self.bridge.take_screenshot()
        self.assertTrue(result.startswith("SCREENSHOT_JPEG_BASE64:"))
        image_bytes = base64.b64decode(result.split(":", 1)[1], validate=True)
        self.assertEqual(Image.open(__import__("io").BytesIO(image_bytes)).size, (2, 2))

    def test_action_result_is_not_reported_as_failed_if_result_upload_fails(self):
        window = object.__new__(self.bridge.DesktopBridgeWindow)
        window.events = queue.Queue()
        window.client = SimpleNamespace(complete=Mock(return_value=False))
        with patch.object(self.bridge, "validate_and_execute", return_value="Opened Notepad."):
            window.execute_command({"command_id": "6aa539d1-811b-44a2-97cc-1d625413a202", "action": "open_app", "arguments": {"app": "notepad"}})
        self.assertEqual(window.events.get()[0], "command")
        result = window.events.get()[1]
        self.assertIn("may have run", result)
        self.assertNotIn("Action failed", result)


if __name__ == "__main__":
    unittest.main()
