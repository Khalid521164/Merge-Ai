"""Merge AI - Kokoro TTS service.

A small private HTTP API that turns text into natural speech with Kokoro.
It runs separately from the Streamlit app because Kokoro only supports
Python 3.10-3.12, while Streamlit Community Cloud may run a newer Python.

Endpoints
---------
GET  /health  -> {"status": "ok", "ready": bool, "voice": "am_liam"}   (no auth)
POST /tts     -> audio/wav                                          (Bearer token)
     body: {"text": "...", "voice": "am_liam", "speed": 1.03}

Environment variables (set as Space secrets / variables)
--------------------------------------------------------
TTS_API_KEY     required. Shared secret; the Streamlit app sends it as a Bearer token.
KOKORO_VOICE    optional, default "am_liam"
KOKORO_SPEED    optional, default 1.03
TTS_MAX_CHARS   optional, default 3000 (longer text is cut at a sentence end)
"""
from __future__ import annotations

import io
import logging
import os
import re
import secrets
import threading
import time
import wave

import numpy as np
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("merge-tts")

API_KEY = os.environ.get("TTS_API_KEY", "").strip()
DEFAULT_VOICE = os.environ.get("KOKORO_VOICE", "am_liam").strip() or "am_liam"
DEFAULT_SPEED = float(os.environ.get("KOKORO_SPEED", "1.03"))
MAX_CHARS = int(os.environ.get("TTS_MAX_CHARS", "3000"))
SAMPLE_RATE = 24000
REPO_ID = "hexgrad/Kokoro-82M"

# American English voices (lang_code "a"). Unknown voices fall back to the default.
VOICES = {
    "am_liam", "am_michael", "am_eric", "am_adam", "am_puck",
    "am_echo", "am_fenrir", "am_onyx", "am_santa",
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
}

_pipeline = None
_ready = threading.Event()
_load_error = ""
_synth_lock = threading.Lock()   # Kokoro pipeline is not thread-safe.


def load_pipeline() -> None:
    """Load the model once, then warm it up so the first real answer is fast."""
    global _pipeline, _load_error
    try:
        started = time.time()
        import torch
        from kokoro import KPipeline

        torch.set_num_threads(max(1, os.cpu_count() or 1))
        pipeline = KPipeline(lang_code="a", repo_id=REPO_ID, device="cpu")
        pipeline.load_voice(DEFAULT_VOICE)
        for _ in pipeline("Merge AI voice is ready.", voice=DEFAULT_VOICE, speed=DEFAULT_SPEED):
            pass
        _pipeline = pipeline
        _ready.set()
        LOG.info("Kokoro ready in %.1fs (voice=%s)", time.time() - started, DEFAULT_VOICE)
    except Exception as exc:  # keep the server alive so /health can report it
        _load_error = type(exc).__name__
        LOG.exception("Kokoro failed to load")


def limit_text(text: str, max_chars: int = MAX_CHARS) -> str:
    """Normalize whitespace and cut long text at the last sentence end."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > max_chars // 2 else cut).strip()


def to_wav(audio: np.ndarray) -> bytes:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buffer.getvalue()


def synthesize(text: str, voice: str, speed: float) -> bytes:
    with _synth_lock:
        chunks = []
        for result in _pipeline(text, voice=voice, speed=speed):
            audio = result.audio if hasattr(result, "audio") else result[2]
            if audio is None:
                continue
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
    if not chunks:
        raise RuntimeError("Kokoro returned no audio")
    # 120 ms of silence between chunks sounds more natural than a hard join.
    gap = np.zeros(int(SAMPLE_RATE * 0.12), dtype=np.float32)
    joined = [chunks[0]]
    for chunk in chunks[1:]:
        joined.extend([gap, chunk])
    return to_wav(np.concatenate(joined))


app = FastAPI(title="Merge AI Kokoro TTS", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    if not API_KEY:
        LOG.warning("TTS_API_KEY is not set - /tts will refuse every request")
    threading.Thread(target=load_pipeline, daemon=True).start()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    voice: str | None = None
    speed: float | None = None


@app.get("/")
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if not _load_error else "error",
        "ready": _ready.is_set(),
        "voice": DEFAULT_VOICE,
        "error": _load_error or None,
    }


@app.post("/tts")
def tts(request: TTSRequest, authorization: str | None = Header(default=None)) -> Response:
    if not API_KEY:
        raise HTTPException(503, "Service is not configured")
    if not secrets.compare_digest(authorization or "", f"Bearer {API_KEY}"):
        raise HTTPException(401, "Unauthorized")
    if _load_error:
        raise HTTPException(503, "Voice model failed to load")
    if not _ready.wait(timeout=90):
        raise HTTPException(503, "Voice model is still loading")

    text = limit_text(request.text)
    if not text:
        raise HTTPException(400, "No text to speak")
    voice = request.voice if request.voice in VOICES else DEFAULT_VOICE
    speed = max(0.8, min(float(request.speed or DEFAULT_SPEED), 1.3))

    started = time.time()
    try:
        wav = synthesize(text, voice, speed)
    except Exception:
        LOG.exception("Speech generation failed")
        raise HTTPException(500, "Speech generation failed") from None
    seconds = (len(wav) - 44) / (2 * SAMPLE_RATE)
    LOG.info("tts chars=%d audio=%.1fs took=%.1fs", len(text), seconds, time.time() - started)
    return Response(
        content=wav,
        media_type="audio/wav",
        headers={"X-Audio-Seconds": f"{seconds:.2f}", "Cache-Control": "no-store"},
    )
