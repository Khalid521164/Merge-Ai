"""Lazy, bounded CPU Kokoro synthesis shared by Live Voice and Listen.

Only model resources are shared; user text and audio are not cached globally.
Kokoro imports are lazy so ordinary chat still works if its dependencies fail.
"""
from __future__ import annotations

import base64
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
import importlib.util
import io
import logging
import os
import threading
import time
import traceback
import wave

from voice_config import VoiceConfig, VOICE_SAMPLE_RATE, get_voice_config
from voice_text import check_final_answer, prepare_speech_text, UnsafeSpeechText

LOG = logging.getLogger(__name__)
MODEL_REPO = "hexgrad/Kokoro-82M"
MAX_WAV_BYTES = VOICE_SAMPLE_RATE * 2 * 600 + 44
_pipeline = None
_model_lock = threading.Lock()
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kokoro-inference")
_slot = threading.BoundedSemaphore(1)
_delivery = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kokoro-delivery")
_delivery_slots = threading.BoundedSemaphore(2)
_retry_after = 0.0


class KokoroError(RuntimeError):
    def __init__(self, message: str, code: str = "unavailable"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SpeechResult:
    audio_b64: str = ""
    status: str = "unavailable"
    message: str = "Kokoro is unavailable."
    allow_fallback: bool = True


def availability(config: VoiceConfig | None = None) -> dict:
    config = config or get_voice_config()
    if not config.enabled:
        return {"configured": False, "ready": False, "status": "disabled"}
    missing = []
    for name in ("kokoro", "torch", "numpy", "en_core_web_sm"):
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ImportError, ValueError):
            missing.append(name)
    return {"configured": not missing, "ready": not missing and _pipeline is not None,
            "status": "missing_dependency" if missing else "ready" if _pipeline is not None else "cold"}


def _asset(filename):
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import LocalEntryNotFoundError
    try:
        return hf_hub_download(repo_id=MODEL_REPO, filename=filename, local_files_only=True)
    except LocalEntryNotFoundError:
        return hf_hub_download(repo_id=MODEL_REPO, filename=filename)


def _load_pipeline(config: VoiceConfig):
    global _pipeline
    with _model_lock:
        if _pipeline is None:
            started = time.monotonic()
            os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
            os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
            import torch
            from kokoro import KModel, KPipeline
            torch.set_num_threads(min(config.threads, os.cpu_count() or 1))
            LOG.info("Kokoro loading: device=cpu torch=%s", torch.__version__)
            model = KModel(repo_id=MODEL_REPO, config=_asset("config.json"),
                           model=_asset("kokoro-v1_0.pth")).to("cpu").eval()
            pipeline = KPipeline(lang_code="a", repo_id=MODEL_REPO, model=model, device="cpu")
            pipeline.voices[config.name] = pipeline.load_voice(_asset("voices/" + config.name + ".pt"))
            _pipeline = pipeline  # Publish only after model AND voice initialization succeed.
            LOG.info("Kokoro ready: load_seconds=%.2f", time.monotonic() - started)
        elif config.name not in _pipeline.voices:
            voice = _pipeline.load_voice(_asset("voices/" + config.name + ".pt"))
            _pipeline.voices.clear()  # Retain one selected voice, not an unbounded voice cache.
            _pipeline.voices[config.name] = voice
        return _pipeline


def _local_wav(text: str, config: VoiceConfig) -> bytes:
    import numpy as np
    import torch
    pipeline = _load_pipeline(config)
    buffer = io.BytesIO()
    total = 0
    with wave.open(buffer, "wb") as wav, torch.inference_mode():
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(VOICE_SAMPLE_RATE)
        for result in pipeline(text, voice=config.name, speed=config.speed):
            audio = result.audio if hasattr(result, "audio") else result[2]
            if audio is None:
                raise KokoroError("Kokoro omitted a speech segment.", "invalid_audio")
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            samples = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not np.isfinite(samples).all():
                raise KokoroError("Kokoro returned invalid samples.", "invalid_audio")
            audible = np.flatnonzero(np.abs(samples) > 0.001)
            if not audible.size:
                raise KokoroError("Kokoro returned an inaudible segment.", "invalid_audio")
            # Preserve natural pauses, but cap excessive boundary silence between chunks.
            start = max(0, int(audible[0]) - int(VOICE_SAMPLE_RATE * .03))
            end = min(len(samples), int(audible[-1]) + int(VOICE_SAMPLE_RATE * .12) + 1)
            pcm = (np.clip(samples[start:end], -1, 1) * 32767).astype("<i2").tobytes()
            total += len(pcm)
            if total + 44 > MAX_WAV_BYTES:
                raise KokoroError("This answer needs browser playback because its audio exceeds the limit.", "audio_limit")
            wav.writeframesraw(pcm)
    if total == 0:
        raise KokoroError("Kokoro returned no audio.", "invalid_audio")
    return buffer.getvalue()


def validate_wav(audio: bytes) -> bytes:
    if not audio or len(audio) > MAX_WAV_BYTES:
        raise KokoroError("Invalid audio size.", "invalid_audio")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, VOICE_SAMPLE_RATE) or not wav.getnframes():
                raise ValueError("Unexpected format")
            if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                raise ValueError("Truncated WAV")
    except (wave.Error, ValueError, EOFError) as exc:
        raise KokoroError("Kokoro returned invalid audio.", "invalid_audio") from exc
    return audio


def synthesize(text: str, *, language: str = "en-US", config: VoiceConfig | None = None) -> bytes:
    """Return complete 24-kHz WAV bytes or raise; never return a partial answer."""
    global _retry_after
    config = config or get_voice_config()
    if not isinstance(text, str) or not text.strip():
        raise KokoroError("There is no text to speak.", "empty")
    try:
        check_final_answer(text)
    except UnsafeSpeechText as exc:
        raise KokoroError(str(exc), "blocked") from None
    text = prepare_speech_text(text)
    if not text:
        raise KokoroError("There is no text to speak.", "empty")
    if not config.enabled:
        raise KokoroError("Kokoro is disabled in the server settings.", "disabled")
    if language.lower().split("-")[0] != "en":
        raise KokoroError("Browser voice is used for this language.", "language")
    if not availability(config)["configured"]:
        LOG.warning("Kokoro missing dependencies; install requirements-kokoro.txt with Python 3.12")
        raise KokoroError("Kokoro dependencies are unavailable.", "missing_dependency")
    if time.monotonic() < _retry_after:
        raise KokoroError("Kokoro is recovering from an error; retry shortly.", "recovering")
    if not _slot.acquire(blocking=False):
        raise KokoroError("Kokoro is serving another speech request.", "busy")
    started = time.monotonic()
    try:
        future = _worker.submit(_local_wav, text, config)
    except Exception:
        _slot.release()
        raise
    future.add_done_callback(lambda _: _slot.release())
    try:
        result = validate_wav(future.result(timeout=120 if _pipeline is None else 90))
        LOG.info("Kokoro generated: seconds=%.2f bytes=%d voice=%s speed=%.2f",
                 time.monotonic() - started, len(result), config.name, config.speed)
        return result
    except Exception as exc:
        _retry_after = time.monotonic() + 30
        locations = " -> ".join(f"{f.name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__))
        LOG.error("Kokoro failed: type=%s stack=%s", type(exc).__name__, locations)
        if isinstance(exc, KokoroError):
            raise
        code = "timeout" if isinstance(exc, TimeoutError) else "inference"
        raise KokoroError("Kokoro could not prepare speech; browser voice is available.", code) from exc


def _deliver(text, language, config):
    try:
        audio = synthesize(text, language=language, config=config)
        return SpeechResult(base64.b64encode(audio).decode("ascii"), "ready", "Kokoro ready", config.browser_fallback)
    except KokoroError as exc:
        return SpeechResult(status=exc.code, message=str(exc),
                            allow_fallback=config.browser_fallback and exc.code not in ("blocked", "empty"))
    except Exception as exc:
        LOG.error("Kokoro delivery failed: type=%s", type(exc).__name__)
        return SpeechResult(allow_fallback=config.browser_fallback)


def start_audio(text: str, *, language: str = "en-US", config: VoiceConfig | None = None) -> Future:
    config = config or get_voice_config()
    # Even a saturated queue must never authorize reading internal drafts aloud.
    try:
        check_final_answer(text if isinstance(text, str) else "")
    except UnsafeSpeechText as exc:
        future = Future()
        future.set_result(SpeechResult(status="blocked", message=str(exc), allow_fallback=False))
        return future
    if not _delivery_slots.acquire(blocking=False):
        future = Future()
        future.set_result(SpeechResult(status="busy", message="Kokoro is busy.", allow_fallback=config.browser_fallback))
        return future
    try:
        future = _delivery.submit(_deliver, text, language, config)
    except Exception:
        _delivery_slots.release()
        raise
    future.add_done_callback(lambda _: _delivery_slots.release())
    return future


def smoke_test(output="kokoro-smoke.wav"):
    from pathlib import Path
    text = "Hello! I'm Merge AI, created by Khalid. How can I help you today?"
    audio = synthesize(text)
    Path(output).write_bytes(audio)
    return Path(output)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="kokoro-smoke.wav")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print("Generated", smoke_test(args.output))
