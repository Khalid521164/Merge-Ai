"""Optional private Kokoro service. Run behind HTTPS, with one Uvicorn worker."""
from contextlib import asynccontextmanager
import hmac
import os
import json

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from kokoro_tts import KokoroError, synthesize


@asynccontextmanager
async def lifespan(app):
    key = os.environ.get("KOKORO_TTS_API_KEY", "")
    if len(key) < 32:
        raise RuntimeError("Set KOKORO_TTS_API_KEY to a random value of at least 32 characters.")
    app.state.key = key
    # Fail startup if dependencies or weights cannot load; /healthz means ready.
    await run_in_threadpool(synthesize, "Hey! I'm ready to help.")
    yield


async def health(request):
    return JSONResponse({"status": "ready", "voice": "am_liam", "speed": 1.03})


async def speech(request):
    if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + request.app.state.key):
        return Response(status_code=401)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 40000:
            return Response(status_code=413)
    try:
        body = json.loads(raw)
        if (not isinstance(body, dict) or not isinstance(body.get("input"), str)
                or not 1 <= len(body["input"]) <= 6000 or body.get("voice", "am_liam") != "am_liam"
                or body.get("speed", 1.03) != 1.03 or body.get("response_format", "wav") != "wav"):
            return Response(status_code=422)
    except (ValueError, UnicodeError):
        return Response(status_code=400)
    try:
        audio = await run_in_threadpool(synthesize, body["input"])
    except KokoroError:
        return JSONResponse({"error": "Speech is temporarily unavailable."}, status_code=503)
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})


app = Starlette(lifespan=lifespan, routes=[
    Route("/healthz", health), Route("/v1/audio/speech", speech, methods=["POST"]),
])
