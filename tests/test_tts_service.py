import os
import unittest
from unittest.mock import patch

try:
    from starlette.testclient import TestClient
    import tts_service
except ImportError:
    TestClient = None

from test_kokoro_tts import wav_fixture


@unittest.skipIf(TestClient is None, "Install requirements-tts-service.txt for service tests")
class ServiceTests(unittest.TestCase):
    def test_service_requires_key_at_startup(self):
        with patch.dict(os.environ, {"KOKORO_TTS_API_KEY": ""}):
            with self.assertRaises(RuntimeError), TestClient(tts_service.app):
                pass

    def test_authentication_validation_and_audio_contract(self):
        headers = {"Authorization": "Bearer " + "x" * 32}
        with patch.dict(os.environ, {"KOKORO_TTS_API_KEY": "x" * 32}), \
                patch.object(tts_service, "synthesize", return_value=wav_fixture()), \
                TestClient(tts_service.app) as client:
            self.assertEqual(client.get("/healthz").json()["voice"], "am_liam")
            self.assertEqual(client.post("/v1/audio/speech", json={"input": "Hello"}).status_code, 401)
            result = client.post("/v1/audio/speech", json={"input": "Hello"}, headers=headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.content, wav_fixture())
            self.assertEqual(result.headers["cache-control"], "no-store")
            for body in ({"input": ""}, {"input": "Hello", "voice": "wrong"},
                         {"input": "Hello", "speed": 9}, {"input": "x" * 6001}):
                self.assertEqual(client.post("/v1/audio/speech", json=body, headers=headers).status_code, 422)
            self.assertEqual(client.post("/v1/audio/speech", content=b"x" * 40001, headers=headers).status_code, 413)
            self.assertEqual(client.post("/v1/audio/speech", content=b"{invalid", headers=headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
