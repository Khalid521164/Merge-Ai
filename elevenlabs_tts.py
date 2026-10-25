"""Server-only ElevenLabs TTS. Never expose the API key in browser data."""
from __future__ import annotations
import json
import logging
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class VoiceGenerationError(Exception):
    pass

def synthesize(text: str, api_key: str, voice_id: str, model: str = 'eleven_multilingual_v2') -> bytes:
    if not api_key or not voice_id:
        raise VoiceGenerationError('ElevenLabs is not configured.')
    if not re.fullmatch(r'[A-Za-z0-9]{8,80}', voice_id):
        raise VoiceGenerationError('Invalid ElevenLabs voice ID.')
    # An intentionally short answer keeps free-tier usage predictable.
    spoken = re.sub(r'```[\s\S]*?```', ' Code example omitted. ', text)
    spoken = re.sub(r'https?://\S+', ' source link ', spoken)
    spoken = re.sub(r'[#*_`|>]', ' ', spoken).strip()[:1100]
    if not spoken:
        raise VoiceGenerationError('Nothing to speak.')
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128'
    payload = json.dumps({'text': spoken, 'model_id': model}).encode('utf-8')
    req = Request(url, data=payload, method='POST', headers={
        'xi-api-key': api_key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'
    })
    try:
        with urlopen(req, timeout=25) as response:
            audio = response.read(3_000_001)
            if len(audio) > 3_000_000 or not audio:
                raise VoiceGenerationError('Audio response was empty or too large.')
            return audio
    except HTTPError as error:
        status = error.code
        error.close()
        logging.warning('ElevenLabs TTS failed with HTTP %s', status)
        if status in (401, 403):
            raise VoiceGenerationError('ElevenLabs key or voice permissions are invalid.') from None
        if status in (402, 429):
            raise VoiceGenerationError('ElevenLabs credits or rate limits reached.') from None
        raise VoiceGenerationError('ElevenLabs audio is temporarily unavailable.') from None
    except (URLError, TimeoutError, OSError):
        logging.warning('ElevenLabs TTS network request failed')
        raise VoiceGenerationError('Could not connect to ElevenLabs.') from None
