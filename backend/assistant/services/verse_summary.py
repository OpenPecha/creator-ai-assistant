"""Generate a simple, humanized bullet-point summary of a day's verses.

Context comes ONLY from the verse text (not the commentary or day plan). Output
is a short list of plain-language points in the chosen language.

English and Hindi are generated INDEPENDENTLY, each explaining the verse directly
from its own skill prompt (verse_summary.md and verse_summary_hindi.md).
"""

from __future__ import annotations

from django.conf import settings

from . import gemini
from .content_loader import DayContent
from .ideas import load_prompt
from .script_generator import strip_markdown

# Supported output languages. English is generated from the verse; Hindi is a
# natural-Hindi rendering of the English points (see module docstring).
LANGUAGES = {
    "english": "English",
    "hindi": "Hindi",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 5,
        }
    },
    "required": ["points"],
}

# Deterministic per (day, language); the source repo is static between pulls.
_cache: dict[tuple[int, str], list[str]] = {}


def clear_cache() -> None:
    _cache.clear()


def _english_prompt(dc: DayContent) -> str:
    template = load_prompt("verse_summary.md")
    return (
        template.replace("{{LANGUAGE}}", "English")
        .replace("{{LANGUAGE_NOTE}}", "")
        .replace("{{VERSE_TEXT}}", dc.verse_block or "(no verse text found)")
    )


def _hindi_prompt(dc: DayContent) -> str:
    template = load_prompt("verse_summary_hindi.md")
    return template.replace("{{VERSE_TEXT}}", dc.verse_block or "(no verse text found)")


def _generate(prompt: str) -> list[str]:
    result = gemini.generate_json(prompt, schema=_SCHEMA)
    return [strip_markdown(p) for p in result.get("points", []) if p and p.strip()]


def summarize(dc: DayContent, language: str) -> list[str]:
    """Return a list of simple summary points for the day's verses.

    English and Hindi are generated independently from their own skill prompts.
    """
    lang = (language or "").lower()
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}. Use 'english' or 'hindi'.")

    # In local dev (DEBUG), skip the cache so prompt edits show immediately.
    # In production, cache per (day, language) to save repeat LLM calls.
    key = (dc.day, lang)
    if not settings.DEBUG and key in _cache:
        return _cache[key]

    prompt = _hindi_prompt(dc) if lang == "hindi" else _english_prompt(dc)
    points = _generate(prompt)

    if not settings.DEBUG:
        _cache[key] = points
    return points
