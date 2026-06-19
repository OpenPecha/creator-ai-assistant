"""Turn a script into narrated audio via Gemini TTS, saved under MEDIA_ROOT."""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings

from . import gemini

_AUDIO_SUBDIR = "audio"


def generate(script: str, *, voice: str | None = None) -> str:
    """Generate (or reuse) a WAV file and return its media-relative URL path.

    The filename is the hash of (voice + script), so an identical request reuses
    the existing file instead of paying for another TTS call.
    """
    media_root = Path(settings.MEDIA_ROOT)
    audio_dir = media_root / _AUDIO_SUBDIR
    audio_dir.mkdir(parents=True, exist_ok=True)

    voice_name = voice or settings.GEMINI_TTS_VOICE
    digest = hashlib.sha1(f"{voice_name}\n{script}".encode("utf-8")).hexdigest()[:16]
    filename = f"{digest}.wav"
    target = audio_dir / filename

    if not target.exists():
        wav_bytes = gemini.generate_audio(script, voice=voice)
        target.write_bytes(wav_bytes)

    return f"{settings.MEDIA_URL}{_AUDIO_SUBDIR}/{filename}"
