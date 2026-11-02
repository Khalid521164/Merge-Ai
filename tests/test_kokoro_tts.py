import base64
import io
import math
import struct
import unittest
from unittest.mock import patch, MagicMock
import wave

import kokoro_tts as tts


def wav_fixture():
    """A generated tone, NOT Kokoro speech; exercises audio encoding/transport."""
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(i * 2 * math.pi * 440 / 24000)))
                                 for i in range(2400)))
    return output.getvalue()


class KokoroTests(unittest.TestCase):
    def setUp(self):
        tts._retry_after = 0

    def test_markdown_cleanup_preserves_spoken_content(self):
        self.assertEqual(tts.speech_text("# Rain\n**Water** condenses. [Source](https://example.org)."),
                         "Rain Water condenses. Source.")
        self.assertNotIn("print", tts.speech_text("```python\nprint('hello')\n```"))

    def test_valid_pcm_roundtrip(self):
        wav = wav_fixture()
        self.assertEqual(tts.validate_wav(wav), wav)
        with patch.object(tts, "synthesize", return_value=wav):
            self.assertEqual(base64.b64decode(tts.audio_base64("Hi")), wav)

    def test_empty_corrupt_and_truncated_audio_rejected(self):
        for audio in (b"", b"<html>Error</html>", wav_fixture()[:-100]):
            with self.subTest(audio=len(audio)), self.assertRaises(tts.KokoroError):
                tts.validate_wav(audio)

    def test_browser_fallback_conditions_do_not_load_model(self):
        with patch.object(tts, "_local_wav") as generate:
            for kwargs in ({"language": "bn-BD"}, {"enabled": False}):
                with self.assertRaises(tts.KokoroError):
                    tts.synthesize("Hello", **kwargs)
            with self.assertRaises(tts.KokoroError):
                tts.synthesize("x" * 6001)
            generate.assert_not_called()

    def test_local_generation_returns_valid_audio(self):
        with patch.object(tts, "_local_wav", return_value=wav_fixture()) as generate:
            result = tts.synthesize("**Hello**")
            generate.assert_called_once_with("Hello")
            self.assertEqual(result, wav_fixture())

    def test_failure_cooldown_prevents_repeated_model_loads(self):
        with patch.object(tts, "_local_wav", side_effect=ImportError("not installed")) as generate:
            for _ in range(2):
                with self.assertRaises(tts.KokoroError):
                    tts.synthesize("Hello")
            self.assertEqual(generate.call_count, 1)

    def test_busy_worker_falls_back_without_queueing(self):
        tts._slot.acquire()
        try:
            with patch.object(tts, "_local_wav") as generate, self.assertRaises(tts.KokoroError):
                tts.synthesize("Hello")
            generate.assert_not_called()
        finally:
            tts._slot.release()

    def test_remote_voice_speed_and_credentials_stay_server_side(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 200
        response.iter_content.return_value = [wav_fixture()]
        with patch.object(tts.requests, "post", return_value=response) as post:
            self.assertEqual(tts.synthesize("Hello", service_url="https://tts.example.org", api_key="test-secret"), wav_fixture())
            self.assertEqual(post.call_args.kwargs["json"]["voice"], "am_liam")
            self.assertEqual(post.call_args.kwargs["json"]["speed"], 1.03)
            self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_remote_invalid_audio_falls_back(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 200
        response.iter_content.return_value = [b"not wav"]
        with patch.object(tts.requests, "post", return_value=response), self.assertRaises(tts.KokoroError):
            tts.synthesize("Hello", service_url="https://tts.example.org", api_key="test-secret")

    def test_remote_cleartext_or_missing_key_rejected(self):
        with patch.object(tts.requests, "post") as post:
            for url, key in (("http://tts.example.org", "test"), ("https://tts.example.org", "")):
                with self.assertRaises(tts.KokoroError):
                    tts.synthesize("Hello", service_url=url, api_key=key)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
