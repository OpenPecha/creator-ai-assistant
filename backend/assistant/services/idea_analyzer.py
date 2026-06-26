"""Decide which video ideas a given day's content can support.

Concept / Practice / Testimony are always offered. Story and Extra info are
conditional: a single Gemini call inspects the day's content and flags whether a
genuine story or fun fact is present, with a one-line teaser per available idea.

If Gemini is not configured, falls back to a lightweight keyword heuristic so the
app remains usable offline.
"""

from __future__ import annotations

from . import gemini, language as lang_service
from .content_loader import DayContent
from .ideas import IDEAS, idea_blurb, idea_label

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

Teaser craft (this matters — the teaser is the ONLY thing shown on each idea card):
- Each teaser plainly says what THIS day's video would be about — a calm, clear
  description, NOT a hook, a question, or a sales pitch. No hype, no bold claims,
  no clickbait, no drama.
- Simple and instantly clear. Small, everyday words a 12-year-old gets at a glance.
  Avoid heavy or abstract words ("sins," "compassion," "merit," "virtue," "analogy")
  — say it in plain terms.
- Short — about 5 to 9 words. Calm and clear, in the style of:
  "The one good habit that never runs out." / "A simple way to deal with regret
  today." / "Why small good acts are worth it."
- Base it on the source; don't fabricate.

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


# Analysis is deterministic per (day, language) and the source repo is static
# between pulls, so cache results to avoid a fresh Gemini call on every
# day-detail request. The teasers are language-specific, so the language is part
# of the cache key.
_analysis_cache: dict[tuple[int, str], dict] = {}


def clear_cache() -> None:
    """Drop cached analyses (call after the source repo is updated)."""
    _analysis_cache.clear()


def analyze(dc: DayContent, language: str = "english") -> dict:
    """Return the raw analysis dict (booleans + teasers), cached per (day, language)."""
    language = lang_service.normalize(language)
    key = (dc.day, language)
    cached = _analysis_cache.get(key)
    if cached is not None:
        return cached

    if not gemini.is_configured():
        # Heuristic is deterministic; safe to cache. (English-only teasers; the
        # heuristic is a rare offline fallback so we don't translate it.)
        result = _heuristic(dc)
        _analysis_cache[key] = result
        return result

    prompt = _analysis_prompt(dc) + lang_service.json_directive(language)
    try:
        result = gemini.generate_json(prompt, schema=_ANALYSIS_SCHEMA)
    except Exception:
        # Never let analysis failure break the day endpoint — and don't cache a
        # transient failure, so the next request can retry the LLM.
        return _heuristic(dc)

    _analysis_cache[key] = result
    return result


def available_ideas(dc: DayContent, language: str = "english") -> list[dict]:
    """Return the ordered list of available ideas: {key, label, teaser}."""
    language = lang_service.normalize(language)
    analysis = analyze(dc, language)
    teasers = {
        "concept": analysis.get("concept_teaser") or idea_blurb("concept", language),
        "practice": analysis.get("practice_teaser") or idea_blurb("practice", language),
        "creative": analysis.get("creative_teaser") or idea_blurb("creative", language),
        "testimony": idea_blurb("testimony", language),
        "story": analysis.get("story_teaser") or idea_blurb("story", language),
        "extra_info": analysis.get("extra_info_teaser") or idea_blurb("extra_info", language),
    }
    result = []
    for key, meta in IDEAS.items():
        present = meta["always"] or bool(analysis.get(key))
        if present:
            result.append({
                "key": key,
                "label": idea_label(key, language),
                "teaser": teasers.get(key) or idea_blurb(key, language),
            })
    return result
