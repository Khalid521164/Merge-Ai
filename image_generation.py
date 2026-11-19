"""Gemini image generation for Merge AI.

Image generation is deliberately opt-in because Gemini image output can incur
API charges. The app must also have ENABLE_IMAGE_GENERATION=true configured
by the account owner before this module can be called from the UI.
"""

from __future__ import annotations

import base64
import os
import re

import requests


DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
MAX_PROMPT_CHARS = 1500
REQUEST_TIMEOUT = (15, 120)


class ImageGenerationError(Exception):
    """A safe, user-facing image-generation error."""


def generate_image(prompt: str, api_key: str, model: str | None = None) -> tuple[bytes, str, str]:
    """Generate one image with Gemini and return (image_bytes, mime_type, note)."""
    prompt = str(prompt or "").strip()
    api_key = str(api_key or "").strip()
    model = str(model or os.getenv("GEMINI_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL).strip()

    if not prompt:
        raise ImageGenerationError("Write a description of the image first.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ImageGenerationError(f"Keep the image description under {MAX_PROMPT_CHARS} characters.")
    if not api_key:
        raise ImageGenerationError("The Gemini API key is not configured. Ask the account owner to check Streamlit Secrets.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", model):
        raise ImageGenerationError("The configured Gemini image model name is invalid.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    try:
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ImageGenerationError("Gemini took too long to create the image. Please try again.") from exc
    except requests.RequestException as exc:
        raise ImageGenerationError("Merge AI could not reach Gemini. Check the connection and try again.") from exc

    if response.status_code == 429:
        raise ImageGenerationError("Gemini's image-generation rate limit was reached. Please try again later.")
    if response.status_code in (401, 403):
        raise ImageGenerationError("Gemini rejected the API key or this model is not enabled for the account. Ask the account owner to check Google AI Studio.")
    if response.status_code >= 400:
        raise ImageGenerationError(f"Gemini image generation failed (HTTP {response.status_code}). Please check the model setting and try again.")

    try:
        data = response.json()
    except ValueError as exc:
        raise ImageGenerationError("Gemini returned an unreadable response. Please try again.") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        raise ImageGenerationError("Gemini did not return an image. Try a clearer or simpler description.")

    parts = (candidates[0].get("content") or {}).get("parts") or []
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline_data = part.get("inlineData") or part.get("inline_data")
        if not isinstance(inline_data, dict):
            continue
        encoded = inline_data.get("data")
        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png"
        if not isinstance(encoded, str) or not mime_type.startswith("image/"):
            continue
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ImageGenerationError("Gemini returned an invalid image. Please try again.") from exc
        if not image_bytes:
            continue
        note = next(
            (str(item.get("text", "")).strip() for item in parts
             if isinstance(item, dict) and item.get("text")),
            "Here is the image you asked Merge AI to create.",
        )
        return image_bytes, mime_type, note[:1000]

    # A safety block or unsupported prompt can yield text without image bytes.
    explanation = " ".join(
        str(item.get("text", "")).strip()
        for item in parts
        if isinstance(item, dict) and item.get("text")
    ).strip()
    if explanation:
        raise ImageGenerationError(explanation[:500])
    raise ImageGenerationError("Gemini did not return an image. Try changing your description.")
