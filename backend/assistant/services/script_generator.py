"""Generate a spoken video script for a given day + idea + duration."""

from __future__ import annotations

from . import gemini
from .content_loader import DayContent
from .ideas import IDEAS, build_prompt

# ~150 spoken words per minute => 2.5 words per second.
WORDS_PER_SECOND = 2.5


def target_words(duration_seconds: int) -> int:
    return max(20, round(duration_seconds * WORDS_PER_SECOND))


def generate(dc: DayContent, idea_key: str, duration_seconds: int, creator_notes: str = "") -> str:
    if idea_key not in IDEAS:
        raise ValueError(f"Unknown idea: {idea_key!r}")

    tokens = {
        "DAY": str(dc.day),
        "DATE": dc.date,
        "VERSES_LABEL": dc.verses_label,
        "DURATION_SECONDS": str(duration_seconds),
        "TARGET_WORDS": str(target_words(duration_seconds)),
        "DAY_PLAN": dc.plan_markdown,
        "VERSE_SYNTHESIS": dc.synthesis_text or "(no per-verse commentary synthesis available)",
        "CREATOR_NOTES": creator_notes.strip() or "(the creator did not provide notes)",
    }
    prompt = build_prompt(tokens, IDEAS[idea_key]["file"])
    return gemini.generate_text(prompt)
