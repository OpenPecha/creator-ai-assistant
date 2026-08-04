"""AI rewrite of the per-verse "AI Overview" blurb into plainer language.

The overview shown in the Commentary tab is the "Brief introduction" pulled verbatim
from a verse's Verse Synthesis in the Day-Package (see
``content_loader`` / ``day_package._synthesis_intro``). That text is faithful but
can read dense. This service does a LIGHT rewrite for readability only — same
meaning, same length, nothing invented.

All verses for a day are rewritten in a single Gemini call and cached per
(day, language). When Hindi is selected the blurb is explained in natural Hindi.
Every failure path degrades to the ORIGINAL text, so the overview always shows
something and the day endpoint never breaks when Gemini is unavailable.
"""

from __future__ import annotations

from django.conf import settings

from . import gemini
from . import language as lang_service
from .content_loader import DayContent
from .ideas import load_prompt

_SCHEMA = {
    "type": "object",
    "properties": {
        "overviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["id", "text"],
            },
        }
    },
    "required": ["overviews"],
}

# Deterministic per (day, language); the source repo is static between pulls. The
# overview text is English from the package, so English keeps it as-is while Hindi
# is a natural-Hindi explanation — hence the language is part of the cache key.
_cache: dict[tuple[int, str], dict[str, str]] = {}


def clear_cache() -> None:
    """Drop cached rewrites (call after the source repo is updated)."""
    _cache.clear()


def _originals(dc: DayContent) -> dict[str, str]:
    """{verse_id: original overview text} for verses that carry a non-empty one."""
    out: dict[str, str] = {}
    for vid, res in dc.verse_resources.items():
        text = (res.get("commentary_overview") or "").strip()
        if text:
            out[vid] = text
    return out


def _prompt(originals: dict[str, str], language: str) -> str:
    blocks = "\n\n".join(f"[id: {vid}]\n{text}" for vid, text in originals.items())
    prompt = load_prompt("overview_simplify.md").replace("{{OVERVIEWS}}", blocks)
    # For Hindi this appends the "write every text value in Devanagari" directive;
    # for English it appends nothing, so the rewrite stays in the source language.
    return prompt + lang_service.json_directive(language)


def simplify(dc: DayContent, language: str = "english") -> dict[str, str]:
    """Return {verse_id: simplified overview} for the day, in the chosen language.

    English keeps the source language; Hindi explains the blurb in natural Hindi.
    Falls back to the original overview text for any verse the model omits, and
    for every verse when Gemini is not configured or the call fails.
    """
    language = lang_service.normalize(language)
    originals = _originals(dc)
    if not originals:
        return {}

    # In local dev (DEBUG), skip the cache so prompt edits show immediately.
    key = (dc.day, language)
    if not settings.DEBUG and key in _cache:
        return _cache[key]

    if not gemini.is_configured():
        return dict(originals)

    try:
        result = gemini.generate_json(_prompt(originals, language), schema=_SCHEMA)
    except Exception:
        # Never let a rewrite failure break the day endpoint; don't cache it
        # either, so the next request can retry the LLM.
        return dict(originals)

    # Keep light **bold** and line breaks: the frontend's renderRichText renders
    # them, and the original overview uses bold too (so this preserves parity).
    rewritten = {
        item["id"]: item["text"].strip()
        for item in result.get("overviews", [])
        if item.get("id") in originals and (item.get("text") or "").strip()
    }
    # Keep the original for any verse the model dropped or returned empty.
    merged = {vid: rewritten.get(vid, original) for vid, original in originals.items()}

    if not settings.DEBUG:
        _cache[key] = merged
    return merged
