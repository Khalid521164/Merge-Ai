"""Lightweight backend tests. Model operations are mocked; no downloads or API keys.

Real inference is a separate explicit check: python -m kokoro_tts --output smoke.wav
"""
from concurrent.futures import Future, TimeoutError
from contextlib import nullcontext
import io
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import wave

import numpy as np
import kokoro_tts as tts
from voice_config import VoiceConfig, get_voice_config


def wav_bytes(rate=24000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x01\x01" * 2400)
    return buffer.getvalue()


class BackendTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("_pipeline", None), ("_retry_after", 0.0)):
            p = patch.object(tts, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(tts.importlib.util, "find_spec", return_value=object())
        p.start()
        self.addCleanup(p.stop)

    def test_availability_cold_ready_disabled_and_missing(self):
        self.assertEqual(tts.availability()["status"], "cold")
        with patch.object(tts, "_pipeline", object()):
            self.assertTrue(tts.availability()["ready"])
        self.assertEqual(tts.availability(VoiceConfig(enabled=False))["status"], "disabled")
        with patch.object(tts.importlib.util, "find_spec", return_value=None):
            self.assertFalse(tts.availability()["configured"])

    def test_successful_initialization_and_model_cache(self):
        model = MagicMock()
        model.to.return_value = model
        model.eval.return_value = model
        model_class = MagicMock(return_value=model)
        pipeline = MagicMock()
        pipeline.voices = {}
        pipeline.load_voice.return_value = "voice-tensor"
        pipeline_class = MagicMock(return_value=pipeline)
        torch = MagicMock(__version__="test")
        with patch.dict("sys.modules", {"torch": torch, "kokoro": SimpleNamespace(KModel=model_class, KPipeline=pipeline_class)}), patch.object(tts, "_asset", side_effect=lambda name: "/cache/" + name):
            first = tts._load_pipeline(VoiceConfig())
            self.assertIs(first, tts._load_pipeline(VoiceConfig()))
        model_class.assert_called_once_with(repo_id=tts.MODEL_REPO, config="/cache/config.json", model="/cache/kokoro-v1_0.pth")
        pipeline_class.assert_called_once_with(lang_code="a", repo_id=tts.MODEL_REPO, model=model, device="cpu")
        self.assertEqual(pipeline.voices, {"am_liam": "voice-tensor"})
        model.to.assert_called_once_with("cpu")

    def test_failed_load_does_not_poison_model_cache(self):
        broken = MagicMock(side_effect=RuntimeError("download failed"))
        with patch.dict("sys.modules", {"torch": MagicMock(__version__="test"), "kokoro": SimpleNamespace(KModel=broken, KPipeline=MagicMock())}), patch.object(tts, "_asset", return_value="cached"):
            with self.assertRaises(RuntimeError):
                tts._load_pipeline(VoiceConfig())
        self.assertIsNone(tts._pipeline)

    def test_wav_encoder_correct_rate_and_voice_and_full_text(self):
        pipeline = MagicMock(return_value=[SimpleNamespace(audio=np.array([0, .25, -.25, 0]))] * 2)
        torch = SimpleNamespace(inference_mode=nullcontext)
        text = "Arbitrary new sentence. " * 500
        with patch.object(tts, "_load_pipeline", return_value=pipeline), patch.dict("sys.modules", {"torch": torch}):
            audio = tts._local_wav(text, VoiceConfig())
        pipeline.assert_called_once_with(text, voice="am_liam", speed=1.03)
        with wave.open(io.BytesIO(tts.validate_wav(audio))) as wav:
            self.assertEqual((wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getnframes()), (24000, 1, 2, 8))

    def test_invalid_segments_are_not_silently_omitted(self):
        for samples in (None, [], [0, 0], [float("nan"), .1]):
            with self.subTest(samples=samples), patch.object(tts, "_load_pipeline", return_value=lambda *a, **k: [SimpleNamespace(audio=samples)]), patch.dict("sys.modules", {"torch": SimpleNamespace(inference_mode=nullcontext)}):
                with self.assertRaises(tts.KokoroError):
                    tts._local_wav("An answer", VoiceConfig())

    def test_repeated_requests_and_cleanup(self):
        with patch.object(tts, "_local_wav", return_value=wav_bytes()) as generate:
            for _ in range(3):
                self.assertEqual(tts.synthesize("The capital of **Japan** is Tokyo."), wav_bytes())
            self.assertEqual(generate.call_count, 3)
            self.assertEqual(generate.call_args.args[0], "The capital of Japan is Tokyo.")

    def test_empty_input(self):
        for text in ("", " \n ", None):
            with self.subTest(text=text), self.assertRaises(tts.KokoroError) as caught:
                tts.synthesize(text)
            self.assertEqual(caught.exception.code, "empty")

    def test_missing_dependency(self):
        with patch.object(tts.importlib.util, "find_spec", return_value=None), self.assertRaises(tts.KokoroError) as caught:
            tts.synthesize("Hello")
        self.assertEqual(caught.exception.code, "missing_dependency")

    def test_other_language_and_disabled(self):
        for kwargs, expected in (({"language": "bn-BD"}, "language"), ({"config": VoiceConfig(enabled=False)}, "disabled")):
            with self.assertRaises(tts.KokoroError) as caught:
                tts.synthesize("Hello", **kwargs)
            self.assertEqual(caught.exception.code, expected)

    def test_error_recovery_and_safe_logging(self):
        with patch.object(tts, "_local_wav", side_effect=[RuntimeError("secret-input-do-not-log"), wav_bytes()]):
            with self.assertLogs(tts.LOG, level="ERROR") as logs, self.assertRaises(tts.KokoroError):
                tts.synthesize("An answer")
            self.assertNotIn("secret-input-do-not-log", str(logs.output))
            self.assertIn("RuntimeError", str(logs.output))
            with self.assertRaises(tts.KokoroError) as caught:
                tts.synthesize("An answer")
            self.assertEqual(caught.exception.code, "recovering")
            with patch.object(tts, "_retry_after", 0):
                self.assertEqual(tts.synthesize("Retry"), wav_bytes())

    def test_busy_request_does_not_queue_more_inference(self):
        with patch.object(tts, "_slot") as slot, patch.object(tts, "_worker") as worker:
            slot.acquire.return_value = False
            with self.assertRaises(tts.KokoroError) as caught:
                tts.synthesize("Hello")
            self.assertEqual(caught.exception.code, "busy")
            worker.submit.assert_not_called()

    def test_timeout_returns_fallback_without_releasing_running_inference(self):
        future = MagicMock()
        future.result.side_effect = TimeoutError()
        with patch.object(tts, "_slot") as slot, patch.object(tts, "_worker") as worker:
            slot.acquire.return_value = True
            worker.submit.return_value = future
            with self.assertRaises(tts.KokoroError) as caught:
                tts.synthesize("Hello")
            self.assertEqual(caught.exception.code, "timeout")
            slot.release.assert_not_called()
            # Only worker completion releases its slot, preventing overlapping models.
            future.add_done_callback.call_args.args[0](future)
            slot.release.assert_called_once()

    def test_validate_wav_rejects_wrong_rate_invalid_and_truncated(self):
        for audio in (b"", b"not wav", wav_bytes(16000), wav_bytes()[:-8]):
            with self.subTest(size=len(audio)), self.assertRaises(tts.KokoroError):
                tts.validate_wav(audio)

    def test_delivery_returns_real_base64_wav(self):
        import base64
        with patch.object(tts, "synthesize", return_value=wav_bytes()):
            result = tts.start_audio("Hello").result(timeout=2)
        self.assertEqual(result.status, "ready")
        self.assertEqual(base64.b64decode(result.audio_b64), wav_bytes())

    def test_fallback_can_be_disabled(self):
        with patch.object(tts, "synthesize", side_effect=tts.KokoroError("Missing", "missing_dependency")):
            result = tts.start_audio("Hello", config=VoiceConfig(browser_fallback=False)).result(timeout=2)
        self.assertFalse(result.allow_fallback)
        self.assertEqual(result.status, "missing_dependency")

    def test_raw_provider_comparison_never_falls_back_even_when_busy(self):
        with patch.object(tts, "_delivery_slots") as slots:
            slots.acquire.return_value = False
            result = tts.start_audio("Gemini says one. Groq says two.").result()
            slots.acquire.assert_not_called()
        self.assertEqual(result.status, "blocked")
        self.assertFalse(result.allow_fallback)

    def test_browser_chunks_are_not_authorized_for_empty_text(self):
        self.assertFalse(tts.start_audio("").result(timeout=2).allow_fallback)


class VoiceConfigTests(unittest.TestCase):
    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = get_voice_config()
        self.assertEqual((config.name, config.speed, config.sample_rate, config.language), ("am_liam", 1.03, 24000, "a"))

    def test_secret_overrides_environment(self):
        with patch.dict(os.environ, {"VOICE_SPEED": "1.2", "KOKORO_ENABLED": "false"}):
            config = get_voice_config({"VOICE_SPEED": 1.05, "KOKORO_ENABLED": True})
        self.assertEqual(config.speed, 1.05)
        self.assertTrue(config.enabled)

    def test_invalid_config_falls_back_and_cannot_select_arbitrary_path(self):
        with patch.dict(os.environ, {}, clear=True):
            config = get_voice_config({"VOICE_NAME": "../../somewhere", "VOICE_SPEED": "NaN", "KOKORO_THREADS": 500})
        self.assertEqual(config, VoiceConfig())


if __name__ == "__main__":
    unittest.main()
