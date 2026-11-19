"""Gemini image generation for Merge AI.

Image generation is deliberately opt-in because Gemini image output can incur
API charges. The app must also have ENABLE_IMAGE_GENERATION=true configured
by the account owner before this module can be called from the UI.
"""

from __future__ import annotations

import base64
import binascii
import os
import re

import requests


DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-lite-image"
MAX_PROMPT_CHARS = 1500
REQUEST_TIMEOUT = (15, 120)
INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
API_REVISION = "2026-05-20"


class ImageGenerationError(Exception):
    """A safe, user-facing image-generation error."""


def _output_blocks(data: dict) -> list[dict]:
    """Read the current Interactions API steps, with compatibility fallbacks."""
    blocks = []
    for step in data.get("steps") or data.get("outputs") or []:
        if not isinstance(step, dict):
            continue
        content = step.get("content")
        if isinstance(content, list):
            blocks.extend(item for item in content if isinstance(item, dict))
        elif isinstance(content, dict):
            blocks.append(content)

    # Some SDK-shaped responses expose this convenience field directly.
    image = data.get("output_image") or data.get("outputImage")
    if isinstance(image, dict):
        blocks.append({
            "type": "image",
            "data": image.get("data"),
            "mime_type": image.get("mime_type") or image.get("mimeType"),
        })
    return blocks


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

    # The current Gemini image-generation guide uses the Interactions API.
    # store=false avoids retaining this one-off generation as a stored interaction.
    payload = {
        "model": model,
        "input": prompt,
        "store": False,
    }

    try:
        response = requests.post(
            INTERACTIONS_URL,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
                "Api-Revision": API_REVISION,
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

    if data.get("status") == "failed":
        raise ImageGenerationError("Gemini could not complete this image request. Please try again with a different description.")

    blocks = _output_blocks(data)
    for part in blocks:
        part_type = str(part.get("type") or "").lower()
        encoded = part.get("data")
        mime_type = part.get("mime_type") or part.get("mimeType") or "image/png"
        if part_type == "image" and isinstance(encoded, str) and mime_type.startswith("image/"):
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ImageGenerationError("Gemini returned an invalid image. Please try again.") from exc
            if image_bytes:
                note = next(
                    (str(item.get("text", "")).strip() for item in blocks
                     if item.get("type") == "text" and item.get("text")),
                    "Here is the image you asked Merge AI to create.",
                )
                return image_bytes, mime_type, note[:1000]

    # A safety block or unsupported prompt can yield text without image bytes.
    explanation = " ".join(
        str(item.get("text", "")).strip()
        for item in blocks
        if item.get("type") == "text" and item.get("text")
    ).strip()
    if explanation:
        raise ImageGenerationError(explanation[:500])
    raise ImageGenerationError("Gemini did not return an image. Try changing your description.")
