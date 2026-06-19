"""Generate a simple, humanized bullet-point summary of a day's verses.

Context comes ONLY from the verse text (not the commentary or day plan). Output
is a short list of plain-language points in the chosen language (English/Hindi).
"""

from __future__ import annotations

from django.conf import settings

from . import gemini
from .content_loader import DayContent
from .ideas import load_prompt
from .script_generator import strip_markdown

# Supported output languages: key -> (display name, extra guidance for the model).
LANGUAGES = {
    "english": ("English", ""),
    "hindi": (
        "Hindi",
        "Write in simple, natural spoken Hindi (Devanagari), the way a Hindi speaker "
        "would explain this to a friend — NOT a word-for-word translation of the "
        "English, which sounds awkward. Grasp each idea, then say it the way it is "
        "naturally said in Hindi.\n"
        "- Do not start points with 'यह श्लोक', 'इस श्लोक में', or 'श्लोक के अनुसार'. "
        "Skip the wind-up and state the idea directly.\n"
        "- Never translate religious terms or poetic epithets literally. Use the "
        "natural, established Hindi: bodhisattvas → 'बोधिसत्व' (NEVER 'बुद्ध के बच्चे'); "
        "the buddhas / tathagatas → 'बुद्ध'; the dharma → 'धर्म' or 'बुद्ध की शिक्षा'.\n"
        "- Avoid stiff, heavily Sanskritized, textbook Hindi. Everyday English "
        "loanwords are fine where people naturally use them.",
    ),
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


def _prompt(dc: DayContent, display_name: str, note: str) -> str:
    template = load_prompt("verse_summary.md")
    return (
        template.replace("{{LANGUAGE}}", display_name)
        .replace("{{LANGUAGE_NOTE}}", note)
        .replace("{{VERSE_TEXT}}", dc.verse_block or "(no verse text found)")
    )


def summarize(dc: DayContent, language: str) -> list[str]:
    """Return a list of simple summary points for the day's verses."""
    lang = (language or "").lower()
    if lang not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}. Use 'english' or 'hindi'.")

    # In local dev (DEBUG), skip the cache so prompt edits show immediately.
    # In production, cache per (day, language) to save repeat LLM calls.
    key = (dc.day, lang)
    if not settings.DEBUG and key in _cache:
        return _cache[key]

    display_name, note = LANGUAGES[lang]
    result = gemini.generate_json(_prompt(dc, display_name, note), schema=_SCHEMA)
    points = [strip_markdown(p) for p in result.get("points", []) if p and p.strip()]

    if not settings.DEBUG:
        _cache[key] = points
    return points
