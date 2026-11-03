"""Voice defaults and validated server-side overrides. No credentials."""
from dataclasses import dataclass
import logging
import math
import os
import re
from collections.abc import Mapping

VOICE_ENGINE = "kokoro"
VOICE_NAME = "am_liam"
VOICE_LANGUAGE = "a"
VOICE_SPEED = 1.03
VOICE_SAMPLE_RATE = 24000
BROWSER_FALLBACK = True


@dataclass(frozen=True)
class VoiceConfig:
    enabled: bool = True
    name: str = VOICE_NAME
    language: str = VOICE_LANGUAGE
    speed: float = VOICE_SPEED
    sample_rate: int = VOICE_SAMPLE_RATE
    browser_fallback: bool = BROWSER_FALLBACK
    threads: int = 2


def get_voice_config(secrets: Mapping | None = None) -> VoiceConfig:
    """Secrets override environment when supplied by the Streamlit main thread."""
    def value(name, default):
        return secrets.get(name, os.getenv(name, default)) if secrets is not None else os.getenv(name, default)

    def boolean(name, default):
        v = str(value(name, default)).strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
        logging.warning("Invalid voice setting %s; using default", name)
        return default

    name = str(value("VOICE_NAME", VOICE_NAME)).strip()
    if not re.fullmatch(r"a[fm]_[a-z0-9_]{1,40}", name):
        logging.warning("Invalid VOICE_NAME; using default")
        name = VOICE_NAME
    try:
        speed = float(value("VOICE_SPEED", VOICE_SPEED))
        if not math.isfinite(speed) or not 0.5 <= speed <= 2:
            raise ValueError
    except (TypeError, ValueError):
        logging.warning("Invalid VOICE_SPEED; using default")
        speed = VOICE_SPEED
    try:
        threads = int(value("KOKORO_THREADS", 2))
        if not 1 <= threads <= 4:
            raise ValueError
    except (TypeError, ValueError):
        threads = 2
    return VoiceConfig(enabled=boolean("KOKORO_ENABLED", True), name=name, speed=speed,
                       browser_fallback=boolean("BROWSER_FALLBACK", True), threads=threads)
