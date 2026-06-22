"""Turn a script into narrated audio via Gemini TTS, saved under MEDIA_ROOT."""

from __future__ import annotations

import hashlib
from pathlib import Path

from django.conf import settings

from . import gemini

_AUDIO_SUBDIR = "audio"


def generate(script: str, *, voice: str | None = None) -> str:
    """Generate (or reuse) a WAV file and return its media-relative URL path.

    The script is narrated with a calm, motivational, and clear delivery
    direction (settings.GEMINI_TTS_STYLE). The filename is the hash of
    (voice + style + script), so an identical request reuses the existing file
    instead of paying for another TTS call.
    """
    media_root = Path(settings.MEDIA_ROOT)
    audio_dir = media_root / _AUDIO_SUBDIR
    audio_dir.mkdir(parents=True, exist_ok=True)

    voice_name = voice or settings.GEMINI_TTS_VOICE
    style = (settings.GEMINI_TTS_STYLE or "").strip()
    # Prepend the delivery direction so narration is calm, motivational, and clear.
    tts_text = f"{style}\n\n{script}" if style else script

    # Style is part of the cache key, so tuning it produces fresh audio.
    digest = hashlib.sha1(f"{voice_name}\n{style}\n{script}".encode("utf-8")).hexdigest()[:16]
    filename = f"{digest}.wav"
    target = audio_dir / filename

    if not target.exists():
        wav_bytes = gemini.generate_audio(tts_text, voice=voice)
        target.write_bytes(wav_bytes)

    return f"{settings.MEDIA_URL}{_AUDIO_SUBDIR}/{filename}"
