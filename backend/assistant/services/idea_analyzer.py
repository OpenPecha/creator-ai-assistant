"""Decide which video ideas a given day's content can support.

Concept / Practice / Testimony are always offered. Story and Extra info are
conditional: a single Gemini call inspects the day's content and flags whether a
genuine story or fun fact is present, with a one-line teaser per available idea.

If Gemini is not configured, falls back to a lightweight keyword heuristic so the
app remains usable offline.
"""

from __future__ import annotations

from . import gemini
from .content_loader import DayContent
from .ideas import IDEAS

_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "story": {"type": "boolean"},
        "story_teaser": {"type": "string"},
        "extra_info": {"type": "boolean"},
        "extra_info_teaser": {"type": "string"},
        "concept_teaser": {"type": "string"},
        "practice_teaser": {"type": "string"},
    },
    "required": ["story", "extra_info"],
}


def _analysis_prompt(dc: DayContent) -> str:
    return f"""Analyze the source material for Day {dc.day} (verses {dc.verses_label}) of a
Buddhist video series. Decide which short-video ideas it can genuinely support.

Return JSON with:
- "story" (bool): true ONLY if the material contains a narrative, parable, sūtra
  anecdote, or vivid analogy that could anchor a story video.
- "story_teaser" (string): if story is true, one short line naming/teasing it.
- "extra_info" (bool): true ONLY if there is a surprising detail, scholastic
  distinction, etymology, or lesser-known fact worth a "fun fact" video.
- "extra_info_teaser" (string): if extra_info is true, one short teasing line.
- "concept_teaser" (string): one short line teasing the core concept of the verses.
- "practice_teaser" (string): one short line teasing today's practice challenge.

Be honest — only flag story/extra_info as true if the material really supports it.

--- DAY PLAN ---
{dc.plan_markdown}

--- VERSE COMMENTARY ---
{dc.synthesis_text or "(no per-verse commentary synthesis available for these verses)"}
"""


def _heuristic(dc: DayContent) -> dict:
    text = (dc.plan_markdown + "\n" + dc.synthesis_text).lower()
    story_markers = ["sūtra", "sutra", "story", "parable", "analogy", "like a", "once ", "tells"]
    info_markers = ["distinction", "etymolog", "literally means", "originally", "scholastic",
                    "cites", "citation", "in fact", "technically"]
    return {
        "story": any(m in text for m in story_markers),
        "story_teaser": "A story or analogy from today's verses.",
        "extra_info": any(m in text for m in info_markers),
        "extra_info_teaser": "A surprising detail from the texts.",
        "concept_teaser": "Explain the idea behind today's verses.",
        "practice_teaser": "Invite viewers to today's practice.",
    }


def analyze(dc: DayContent) -> dict:
    """Return the raw analysis dict (booleans + teasers)."""
    if not gemini.is_configured():
        return _heuristic(dc)
    try:
        return gemini.generate_json(_analysis_prompt(dc), schema=_ANALYSIS_SCHEMA)
    except Exception:
        # Never let analysis failure break the day endpoint.
        return _heuristic(dc)


def available_ideas(dc: DayContent) -> list[dict]:
    """Return the ordered list of available ideas: {key, label, teaser}."""
    analysis = analyze(dc)
    teasers = {
        "concept": analysis.get("concept_teaser") or IDEAS["concept"]["blurb"],
        "practice": analysis.get("practice_teaser") or IDEAS["practice"]["blurb"],
        "testimony": IDEAS["testimony"]["blurb"],
        "story": analysis.get("story_teaser") or IDEAS["story"]["blurb"],
        "extra_info": analysis.get("extra_info_teaser") or IDEAS["extra_info"]["blurb"],
    }
    result = []
    for key, meta in IDEAS.items():
        present = meta["always"] or bool(analysis.get(key))
        if present:
            result.append({"key": key, "label": meta["label"], "teaser": teasers[key]})
    return result
