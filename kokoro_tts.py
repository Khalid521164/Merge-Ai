"""Optional local Kokoro synthesis. No API key or ElevenLabs required.

Kokoro model weights download on first use and can require significant RAM.
If dependencies are unavailable, caller falls back to browser TTS.
"""
from __future__ import annotations
import io
import re
import threading
import wave
import numpy as np

_PIPELINE = None
_LOCK = threading.Lock()
_ALLOWED = {'am_liam', 'am_michael', 'am_eric', 'am_adam', 'am_puck', 'am_echo'}


def prepare_text(text: str) -> str:
    text = re.sub(r'```[\s\S]*?```', ' code example omitted. ', str(text))
    text = re.sub(r'https?://\S+', ' a source link ', text)
    text = re.sub(r'[`*_#>\[\]|]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1100]


def synthesize(text: str, *, voice='am_liam', speed=1.03) -> bytes:
    """Return 24 kHz mono WAV for Streamlit playback & Live Voice component."""
    if voice not in _ALLOWED:
        voice = 'am_liam'
    speed = max(0.8, min(float(speed), 1.3))
    text = prepare_text(text)
    if not text:
        raise ValueError('Nothing to speak')
    with _LOCK:
        # generator may load voices lazily; don't share pipeline concurrently
        chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in
                  _pipeline_no_lock(text, voice, speed)]
    if not chunks:
        raise RuntimeError('No speech generated')
    pcm = (np.clip(np.concatenate(chunks), -1, 1) * 32767).astype('<i2')
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm.tobytes())
    return out.getvalue()


def _pipeline_no_lock(text, voice, speed):
    # initialize under same lock without double-locking
    global _PIPELINE
    if _PIPELINE is None:
        from kokoro import KPipeline
        _PIPELINE = KPipeline(lang_code='a', device='cpu')
    return _PIPELINE(text, voice=voice, speed=speed, split_pattern=r'\n+')
