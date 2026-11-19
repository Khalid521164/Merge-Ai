"""Unit tests for the Cloudflare Workers AI image adapter."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import patch

import image_generation
from image_generation import ImageGenerationError, generate_image


class FakeResponse:
    def __init__(self, status_code=200, *, payload=None, headers=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = content

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON body")
        return self._payload


class ImageGenerationTests(unittest.TestCase):
    def test_decodes_cloudflare_base64_image(self):
        encoded = base64.b64encode(b"fake-jpeg-bytes").decode("ascii")
        response = FakeResponse(
            payload={"success": True, "result": {"image": encoded}}
        )
        with patch.object(image_generation.requests, "post", return_value=response) as post:
            image_bytes, mime_type, note = generate_image(
                "a green robot", "1234567890abcdef", "test-token"
            )

        self.assertEqual(image_bytes, b"fake-jpeg-bytes")
        self.assertEqual(mime_type, "image/jpeg")
        self.assertIn("image", note.lower())
        self.assertIn("/accounts/1234567890abcdef/ai/run/@cf/black-forest-labs/flux-1-schnell", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-token")

    def test_accepts_raw_image_response(self):
        response = FakeResponse(
            headers={"Content-Type": "image/jpeg"},
            content=b"raw-image-bytes",
        )
        with patch.object(image_generation.requests, "post", return_value=response):
            image_bytes, mime_type, _ = generate_image(
                "a green robot", "1234567890abcdef", "test-token"
            )
        self.assertEqual(image_bytes, b"raw-image-bytes")
        self.assertEqual(mime_type, "image/jpeg")

    def test_reports_missing_worker_ai_permission(self):
        response = FakeResponse(
            status_code=403,
            payload={"errors": [{"code": 10000, "message": "Workers AI permission missing"}]},
        )
        with patch.object(image_generation.requests, "post", return_value=response):
            with self.assertRaisesRegex(ImageGenerationError, "permission"):
                generate_image("a green robot", "1234567890abcdef", "test-token")

    def test_rejects_empty_prompt_before_request(self):
        with patch.object(image_generation.requests, "post") as post:
            with self.assertRaisesRegex(ImageGenerationError, "description"):
                generate_image("", "1234567890abcdef", "test-token")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
