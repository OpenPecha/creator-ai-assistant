"""Turn a script into narrated audio via Gemini TTS, saved under MEDIA_ROOT."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from django.conf import settings

from . import gemini

_AUDIO_SUBDIR = "audio"


def generate(script: str, *, voice: str | None = None) -> str:
    """Generate a WAV file and return its media-relative URL path."""
    wav_bytes = gemini.generate_audio(script, voice=voice)

    media_root = Path(settings.MEDIA_ROOT)
    audio_dir = media_root / _AUDIO_SUBDIR
    audio_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha1(script.encode("utf-8")).hexdigest()[:12]
    filename = f"{int(time.time())}-{digest}.wav"
    (audio_dir / filename).write_bytes(wav_bytes)

    return f"{settings.MEDIA_URL}{_AUDIO_SUBDIR}/{filename}"
