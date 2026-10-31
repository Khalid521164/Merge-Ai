
"""Kokoro natural voice for Merge AI."""

import io
import logging
import os
import re
import threading
import wave

import numpy as np

_LOG = logging.getLogger(__name__)
_LOCK = threading.Lock()
_PIPELINE = None

VOICES = {
    "am_liam",
    "am_michael",
    "am_eric",
    "am_adam",
    "am_puck",
    "am_echo",
    "am_fenrir",
    "am_onyx",
}


def clean_for_speech(text):
    text = str(text)

    text = re.sub(
        r"```[\s\S]*?```",
        " Code omitted. ",
        text
    )

    text = re.sub(
        r"https?://\S+",
        "a source link",
        text
    )

    text = re.sub(
        r"[`*_#>\[\]|]",
        " ",
        text
    )

    text = re.sub(r"\s+", " ", text).strip()

    return text[:900]


def get_pipeline():
    global _PIPELINE

    if _PIPELINE is None:
        import torch
        from kokoro import KPipeline

        torch.set_num_threads(
            min(2, max(1, os.cpu_count() or 1))
        )

        _LOG.info(
            "Starting Kokoro CPU pipeline"
        )

        _PIPELINE = KPipeline(
            lang_code="a",
            device="cpu"
        )

        _LOG.info(
            "Kokoro pipeline initialized"
        )

    return _PIPELINE


def synthesize(
    text,
    *,
    voice="am_liam",
    speed=1.03
):
    text = clean_for_speech(text)

    if not text:
        raise ValueError("No text to speak")

    if voice not in VOICES:
        voice = "am_liam"

    speed = max(
        0.8,
        min(float(speed), 1.3)
    )

    try:
        with _LOCK:
            pipeline = get_pipeline()

            chunks = [
                np.asarray(audio, dtype=np.float32)
                for _, _, audio in pipeline(
                    text,
                    voice=voice,
                    speed=speed
                )
                if audio is not None
            ]

        if not chunks:
            raise RuntimeError(
                "Kokoro returned no audio"
            )

        audio = np.concatenate(chunks)

        pcm = (
            np.clip(audio, -1, 1) * 32767
        ).astype("<i2")

        output = io.BytesIO()

        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(pcm.tobytes())

        return output.getvalue()

    except Exception:
        _LOG.exception(
            "Kokoro speech generation failed"
        )
        raise
