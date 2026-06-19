"""Thin wrapper around the google-genai client."""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings


class GeminiNotConfigured(Exception):
    """Raised when no GEMINI_API_KEY is set."""


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


@lru_cache(maxsize=1)
def get_client():
    if not is_configured():
        raise GeminiNotConfigured(
            "GEMINI_API_KEY is not set. Add it to backend/.env to enable "
            "script and audio generation."
        )
    from google import genai  # imported lazily so the app boots without the key

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_text(prompt: str, *, model: str | None = None) -> str:
    client = get_client()
    resp = client.models.generate_content(
        model=model or settings.GEMINI_TEXT_MODEL,
        contents=prompt,
    )
    return (resp.text or "").strip()


def generate_json(prompt: str, *, schema, model: str | None = None):
    """Generate a structured JSON response validated against `schema`."""
    from google.genai import types

    client = get_client()
    resp = client.models.generate_content(
        model=model or settings.GEMINI_TEXT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    import json

    return json.loads(resp.text)


def generate_audio(text: str, *, voice: str | None = None, model: str | None = None) -> bytes:
    """Generate speech audio. Returns WAV bytes (Gemini TTS emits raw PCM)."""
    from google.genai import types

    client = get_client()
    resp = client.models.generate_content(
        model=model or settings.GEMINI_TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice or settings.GEMINI_TTS_VOICE,
                    )
                )
            ),
        ),
    )
    part = resp.candidates[0].content.parts[0]
    pcm = part.inline_data.data
    return _pcm_to_wav(pcm)


def _pcm_to_wav(pcm: bytes, *, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw little-endian PCM (Gemini TTS default: 24kHz/16-bit/mono) in a WAV container."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return buf.getvalue()
