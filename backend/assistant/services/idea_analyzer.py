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
        "creative_teaser": {"type": "string"},
    },
    "required": ["story", "extra_info"],
}


def _analysis_prompt(dc: DayContent) -> str:
    return f"""Analyze the source material for Day {dc.day} (verses {dc.verses_label}) of a
Buddhist short-video series. Decide which video ideas it can genuinely support,
and write an irresistible one-line teaser for each — the hook a creator would put
on the thumbnail.

Teaser craft (this matters):
- Make a creator think "ooh, I want to make THAT." Curiosity, a bold claim, a
  surprise, or a relatable sting — not a dry summary.
- Specific and human. No "explore the concept of" or "learn about" openers. No
  clichés. Talk like a real person, max ~12 words.
- Base every teaser on what's actually in the source. Tease, don't fabricate.

Return JSON with:
- "story" (bool): true ONLY if the material contains an ACTUAL self-contained
  story you could retell — a sūtra narrative with characters and events, a named
  parable, or a teacher's illustrative anecdote. A passing simile ("like a candle")
  or a one-word comparison is NOT a story. When in doubt, return false.
- "story_teaser" (string): only if story is true — a teasing line hinting at the
  story without spoiling it. If story is false, return "".
- "extra_info" (bool): true ONLY if there's a genuinely surprising, concrete fact
  a viewer wouldn't already assume — a scholastic distinction, an etymology, a
  scriptural cross-reference, a historical detail. General explanation of the
  verse's meaning does NOT count (that's the Concept video). When in doubt,
  return false.
- "extra_info_teaser" (string): only if extra_info is true — a "wait, what?"
  teasing line. If extra_info is false, return "".
- "concept_teaser" (string): a teaser for the single most powerful idea in the verses.
- "practice_teaser" (string): a teaser for today's practice, framed as a tempting dare.
- "creative_teaser" (string): a teaser for a fun, universal video about the everyday
  life lesson behind the verse — secular, for everyone, with NO mention of Buddhism,
  scripture, or the verse itself.

CRITICAL: Do not stretch to find a story or fact. It is completely normal and
expected for many days to have NEITHER. Only flag them when the material clearly,
unmistakably supports a whole video on it. A weak or forced option is worse than
no option — default to false.

--- DAY PLAN ---
{dc.plan_markdown}

--- VERSE COMMENTARY ---
{dc.synthesis_text or "(no per-verse commentary synthesis available for these verses)"}
"""


def _heuristic(dc: DayContent) -> dict:
    """Conservative fallback when Gemini is unavailable.

    Requires strong, specific signals — better to hide a borderline option than
    to offer a forced one.
    """
    text = (dc.plan_markdown + "\n" + dc.synthesis_text).lower()
    # Story: needs an explicit narrative source, not just a simile.
    story_markers = ["sūtra", "sutra", "parable", "jātaka", "jataka", "tells the story",
                     "the story of", "a story", "once, ", "there was a"]
    # Extra info: needs an explicit scholastic/etymological/citation signal.
    info_markers = ["distinction between", "etymolog", "literally means",
                    "the term ", "scholastic", "commentators note", "cross-reference"]
    has_story = any(m in text for m in story_markers)
    has_info = any(m in text for m in info_markers)
    return {
        "story": has_story,
        "story_teaser": "A story from today's verses." if has_story else "",
        "extra_info": has_info,
        "extra_info_teaser": "A surprising detail from the texts." if has_info else "",
        "concept_teaser": "Explain the idea behind today's verses.",
        "practice_teaser": "Invite viewers to today's practice.",
        "creative_teaser": "An everyday take on today's lesson — for everyone.",
    }


# Analysis is deterministic per day and the source repo is static between pulls,
# so cache results to avoid a fresh Gemini call on every day-detail request.
_analysis_cache: dict[int, dict] = {}


def clear_cache() -> None:
    """Drop cached analyses (call after the source repo is updated)."""
    _analysis_cache.clear()


def analyze(dc: DayContent) -> dict:
    """Return the raw analysis dict (booleans + teasers), cached per day."""
    cached = _analysis_cache.get(dc.day)
    if cached is not None:
        return cached

    if not gemini.is_configured():
        # Heuristic is deterministic; safe to cache.
        result = _heuristic(dc)
        _analysis_cache[dc.day] = result
        return result

    try:
        result = gemini.generate_json(_analysis_prompt(dc), schema=_ANALYSIS_SCHEMA)
    except Exception:
        # Never let analysis failure break the day endpoint — and don't cache a
        # transient failure, so the next request can retry the LLM.
        return _heuristic(dc)

    _analysis_cache[dc.day] = result
    return result


def available_ideas(dc: DayContent) -> list[dict]:
    """Return the ordered list of available ideas: {key, label, teaser}."""
    analysis = analyze(dc)
    teasers = {
        "concept": analysis.get("concept_teaser") or IDEAS["concept"]["blurb"],
        "practice": analysis.get("practice_teaser") or IDEAS["practice"]["blurb"],
        "creative": analysis.get("creative_teaser") or IDEAS["creative"]["blurb"],
        "testimony": IDEAS["testimony"]["blurb"],
        "story": analysis.get("story_teaser") or IDEAS["story"]["blurb"],
        "extra_info": analysis.get("extra_info_teaser") or IDEAS["extra_info"]["blurb"],
    }
    result = []
    for key, meta in IDEAS.items():
        present = meta["always"] or bool(analysis.get(key))
        if present:
            result.append({"key": key, "label": meta["label"], "teaser": teasers.get(key) or meta["blurb"]})
    return result
