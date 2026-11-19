"""Free-tier image generation for Merge AI using Cloudflare Workers AI.

Cloudflare Workers AI currently includes 10,000 neurons/day on its Free plan.
On the Free plan, requests stop after the daily allowance is exhausted.
"""

from __future__ import annotations

import base64
import binascii
import re

import requests


DEFAULT_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
MAX_PROMPT_CHARS = 1800
REQUEST_TIMEOUT = (15, 180)
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4/accounts"


class ImageGenerationError(Exception):
    """A safe, user-facing image-generation error."""


def generate_image(
    prompt: str,
    account_id: str,
    api_token: str,
    model: str | None = None,
) -> tuple[bytes, str, str]:
    """Generate one image and return (image_bytes, mime_type, note)."""
    prompt = str(prompt or "").strip()
    account_id = str(account_id or "").strip()
    api_token = str(api_token or "").strip()
    model = str(model or DEFAULT_IMAGE_MODEL).strip()

    if not prompt:
        raise ImageGenerationError("Write a description of the image first.")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ImageGenerationError(f"Keep the image description under {MAX_PROMPT_CHARS} characters.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", account_id):
        raise ImageGenerationError("The Cloudflare account ID is missing or invalid.")
    if not api_token:
        raise ImageGenerationError("The Cloudflare API token is not configured. Ask the account owner to add it in Streamlit Secrets.")
    if not re.fullmatch(r"@cf/[A-Za-z0-9._/-]{3,150}", model):
        raise ImageGenerationError("The configured Cloudflare image model name is invalid.")

    url = f"{CLOUDFLARE_API}/{account_id}/ai/run/{model}"
    payload = {
        "prompt": prompt,
        "steps": 4,
    }

    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ImageGenerationError("The image service took too long. Please try again.") from exc
    except requests.RequestException as exc:
        raise ImageGenerationError("Merge AI could not reach Cloudflare. Check the connection and try again.") from exc

    def safe_api_detail() -> str:
        """Extract a short provider error without ever echoing credential values."""
        try:
            body = response.json()
        except ValueError:
            return ""
        errors = body.get("errors") if isinstance(body, dict) else None
        if not isinstance(errors, list):
            return ""
        details = []
        for item in errors[:2]:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            message = str(item.get("message") or "").strip()
            if api_token:
                message = message.replace(api_token, "[hidden]")
            if account_id:
                message = message.replace(account_id, "[hidden]")
            if message:
                details.append((f"Error {code}: " if code is not None else "") + message[:180])
        return " ".join(details)

    if response.status_code == 401:
        detail = safe_api_detail()
        raise ImageGenerationError(
            "Cloudflare rejected the API token. Check that it is a Workers AI token "
            "for this account and has Workers AI permissions. " + detail
        )
    if response.status_code == 403:
        detail = safe_api_detail()
        raise ImageGenerationError(
            "This token does not have permission to run Workers AI. "
            "Create a Workers AI API Token or grant Workers AI Read and Edit permissions. " + detail
        )
    if response.status_code == 429:
        detail = safe_api_detail()
        raise ImageGenerationError(
            "Cloudflare is rate-limiting image requests or the free allowance may be exhausted. "
            "Wait for the limit to reset, then try again. " + detail
        )
    if response.status_code >= 400:
        detail = safe_api_detail()
        raise ImageGenerationError(
            f"Cloudflare image generation returned HTTP {response.status_code}. "
            + (detail or "Check the model, account, token permissions, and free allowance.")
        )

    content_type = str(response.headers.get("Content-Type", "")).lower()
    if content_type.startswith("image/") or content_type == "application/octet-stream":
        if not response.content:
            raise ImageGenerationError("Cloudflare returned an empty image response.")
        mime_type = content_type.split(";", 1)[0] if content_type.startswith("image/") else "image/jpeg"
        return response.content, mime_type, "Here is the image you asked Merge AI to create."

    try:
        data = response.json()
    except ValueError as exc:
        raise ImageGenerationError(
            "Cloudflare returned an unreadable response instead of image data. "
            "Please retry and check the selected Workers AI model."
        ) from exc

    result = data.get("result")
    if not data.get("success", True):
        errors = data.get("errors") or []
        details = []
        for item in errors[:2]:
            if isinstance(item, dict):
                code = item.get("code")
                message = str(item.get("message") or "").strip()
                if api_token:
                    message = message.replace(api_token, "[hidden]")
                if account_id:
                    message = message.replace(account_id, "[hidden]")
                if message:
                    details.append((f"Error {code}: " if code is not None else "") + message[:180])
        detail = " ".join(details)
        raise ImageGenerationError(
            "Cloudflare could not complete the image request. "
            + (detail or "Check the model, token permissions, and daily free allowance.")
        )

    encoded = result.get("image") if isinstance(result, dict) else result
    if not isinstance(encoded, str) or not encoded:
        raise ImageGenerationError("Cloudflare did not return an image. Please try a different description.")

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ImageGenerationError("Cloudflare returned an invalid image. Please try again.") from exc

    if not image_bytes:
        raise ImageGenerationError("The generated image was empty. Please try again.")

    return image_bytes, "image/jpeg", "Here is the image you asked Merge AI to create."
