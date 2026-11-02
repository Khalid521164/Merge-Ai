"""Kokoro audio for both chat and Live Voice; no credentials reach the browser.

Local inference uses a single lazy CPU model and one bounded worker. An optional
private HTTP service can host the same model outside Streamlit Community Cloud.
Only the model is shared between accounts, never response text or audio.
"""
from __future__ import annotations

import base64
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
import importlib.util
import io
import logging
import os
import re
import threading
import time
from urllib.parse import urlparse
import wave

import requests

VOICE = "am_liam"
SPEED = 1.03
SAMPLE_RATE = 24000
MAX_TEXT_CHARS = 6000
MAX_WAV_BYTES = 16 * 1024 * 1024
LOG = logging.getLogger(__name__)
_pipeline = None
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kokoro")
_slot = threading.BoundedSemaphore(1)
_retry_after = 0.0
_delivery_worker = ThreadPoolExecutor(max_workers=2, thread_name_prefix="voice-delivery")
_delivery_slots = threading.BoundedSemaphore(2)


class KokoroError(RuntimeError):
    """Safe user-facing failure; diagnosis goes to the server log."""


def configured(service_url: str = "", enabled: bool = True) -> bool:
    """Configured is not a claim that weights are already loaded or healthy."""
    return enabled and bool(service_url or importlib.util.find_spec("kokoro"))


def speech_text(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " A code example is available in the chat. ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"[`*_~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_pipeline():
    global _pipeline
    if _pipeline is None:
        started = time.monotonic()
        # Limit network waits on first download, and avoid CUDA packages/devices.
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")
        os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "10")
        import torch
        from kokoro import KModel, KPipeline
        from huggingface_hub import hf_hub_download
        from huggingface_hub.errors import LocalEntryNotFoundError
        torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
        LOG.info("Kokoro loading: torch=%s device=cpu voice=%s", torch.__version__, VOICE)
        repo = "hexgrad/Kokoro-82M"

        def asset(filename):
            try:
                return hf_hub_download(repo_id=repo, filename=filename, local_files_only=True)
            except LocalEntryNotFoundError:
                return hf_hub_download(repo_id=repo, filename=filename)

        # A cached model must work offline; avoid HEAD requests on every restart.
        model = KModel(repo_id=repo, config=asset("config.json"), model=asset("kokoro-v1_0.pth")).to("cpu").eval()
        pipeline = KPipeline(lang_code="a", repo_id=repo, model=model, device="cpu")
        pipeline.voices[VOICE] = pipeline.load_voice(asset("voices/" + VOICE + ".pt"))
        _pipeline = pipeline
        LOG.info("Kokoro ready: load_seconds=%.2f", time.monotonic() - started)
    return _pipeline


def _local_wav(text: str) -> bytes:
    import numpy as np
    import torch
    pipeline = _load_pipeline()
    chunks = []
    with torch.inference_mode():
        for result in pipeline(text, voice=VOICE, speed=SPEED):
            audio = result.audio if hasattr(result, "audio") else result[2]
            if audio is None:
                continue
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            samples = np.asarray(audio, dtype=np.float32).reshape(-1)
            if not np.isfinite(samples).all():
                raise KokoroError("Invalid audio from Kokoro.")
            audible = np.flatnonzero(np.abs(samples) > 0.001)
            if audible.size:
                # Trim only long boundary silence, retaining a natural short pause.
                start = max(0, int(audible[0]) - int(SAMPLE_RATE * 0.03))
                end = min(len(samples), int(audible[-1]) + int(SAMPLE_RATE * 0.08) + 1)
                chunks.append(samples[start:end])
            if sum(len(c) for c in chunks) * 2 > MAX_WAV_BYTES - 44:
                raise KokoroError("This answer is too long for Kokoro playback.")
    if not chunks:
        raise KokoroError("Kokoro returned no audible speech.")
    # One WAV, rather than separate players with gaps between sentences.
    pcm = (np.clip(np.concatenate(chunks), -1, 1) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def validate_wav(audio: bytes) -> bytes:
    if not audio or len(audio) > MAX_WAV_BYTES:
        raise KokoroError("Invalid audio size.")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2
                    or wav.getframerate() != SAMPLE_RATE or wav.getnframes() == 0):
                raise ValueError("Unexpected audio format")
            frames = wav.readframes(wav.getnframes())
            if len(frames) != wav.getnframes() * 2:
                raise ValueError("Truncated audio")
    except (wave.Error, EOFError, ValueError) as exc:
        raise KokoroError("Kokoro returned an invalid WAV file.") from exc
    return audio


def _remote_wav(text: str, service_url: str, api_key: str) -> bytes:
    parsed = urlparse(service_url)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise KokoroError("The Kokoro service needs a secure URL.")
    if not api_key:
        raise KokoroError("The Kokoro service key is missing.")
    with requests.post(
        service_url.rstrip("/") + "/v1/audio/speech",
        headers={"Authorization": "Bearer " + api_key},
        json={"input": text, "voice": VOICE, "speed": SPEED, "response_format": "wav"},
        timeout=(5, 60), stream=True, allow_redirects=False,
    ) as response:
        if response.status_code != 200:
            LOG.warning("Kokoro service failed: status=%s", response.status_code)
            raise KokoroError("The Kokoro service is unavailable.")
        chunks, size = [], 0
        started = time.monotonic()
        for chunk in response.iter_content(65536):
            size += len(chunk)
            if size > MAX_WAV_BYTES or time.monotonic() - started > 65:
                raise KokoroError("The Kokoro service response exceeded its limit.")
            chunks.append(chunk)
    return validate_wav(b"".join(chunks))


def synthesize(text: str, *, language: str = "en-US", service_url: str = "", api_key: str = "", enabled: bool = True) -> bytes:
    """Return validated PCM WAV or raise; callers preserve browser fallback."""
    global _retry_after
    if not enabled or not language.lower().startswith("en"):
        raise KokoroError("Use the browser voice for this language or configuration.")
    cleaned = speech_text(text)
    if not cleaned or len(cleaned) > MAX_TEXT_CHARS:
        raise KokoroError("This answer needs browser speech playback.")
    if service_url:
        try:
            return _remote_wav(cleaned, service_url, api_key)
        except Exception as exc:
            LOG.warning("Kokoro remote failed: error=%s", type(exc).__name__)
            raise KokoroError("Kokoro is unavailable; browser voice is available.") from exc
    if time.monotonic() < _retry_after or not _slot.acquire(blocking=False):
        raise KokoroError("Kokoro is busy; browser voice is available.")
    started = time.monotonic()
    future = _worker.submit(_local_wav, cleaned)
    future.add_done_callback(lambda _: _slot.release())
    try:
        audio = validate_wav(future.result(timeout=120 if _pipeline is None else 45))
        LOG.info("Kokoro generated: seconds=%.2f bytes=%d voice=%s speed=%.2f",
                 time.monotonic() - started, len(audio), VOICE, SPEED)
        return audio
    except Exception as exc:
        _retry_after = time.monotonic() + 60
        # Log type and stack locations without request text, credentials or response bodies.
        import traceback
        locations = " -> ".join(f"{f.name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__))
        LOG.error("Kokoro local failed: error=%s timeout=%s stack=%s",
                  type(exc).__name__, isinstance(exc, TimeoutError), locations)
        raise KokoroError("Kokoro is unavailable; browser voice is available.") from exc


def audio_base64(text: str, **kwargs) -> str:
    return base64.b64encode(synthesize(text, **kwargs)).decode("ascii")


def start_audio(text: str, **kwargs) -> Future:
    """Live Voice can show the final answer immediately while speech prepares."""
    if not _delivery_slots.acquire(blocking=False):
        future = Future()
        future.set_result("")
        return future
    future = _delivery_worker.submit(audio_base64, text, **kwargs)
    future.add_done_callback(lambda _: _delivery_slots.release())
    return future


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Generate and validate a real am_liam smoke-test WAV.")
    parser.add_argument("--output", default="kokoro-smoke.wav")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    data = synthesize("Hey! I'm Merge AI. How can I help you today?")
    Path(args.output).write_bytes(data)
    print(f"Wrote {len(data)} bytes to {args.output}; play it to check pronunciation and sound.")
