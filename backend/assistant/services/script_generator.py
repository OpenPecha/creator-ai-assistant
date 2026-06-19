"""Generate a spoken video script for a given day + idea + duration."""

from __future__ import annotations

import re

from . import gemini
from .content_loader import DayContent
from .ideas import IDEAS, build_prompt

# ~150 spoken words per minute => 2.5 words per second.
WORDS_PER_SECOND = 2.5


def target_words(duration_seconds: int) -> int:
    return max(20, round(duration_seconds * WORDS_PER_SECOND))


def strip_markdown(text: str) -> str:
    """Remove markdown formatting so the script is clean spoken plain text.

    The model is told not to use markdown, but occasionally slips in emphasis.
    This is the reliable safety net.
    """
    t = text
    # Bold/italic: **word**, *word*, __word__, _word_ -> word
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", t)
    # Inline code / backticks
    t = t.replace("`", "")
    # Leading heading hashes and list bullets at line starts
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", t)
    t = re.sub(r"(?m)^\s*[-*+]\s+", "", t)
    # Any stray remaining asterisks/underscores used as emphasis
    t = t.replace("*", "")
    return t.strip()


def _revision_block(previous: str, feedback: str) -> str:
    return (
        "\n\n## Revision request\n"
        "You previously wrote this script:\n\n"
        f'"""\n{previous.strip()[:6000]}\n"""\n\n'
        f"The creator wants it improved: {feedback.strip()}\n\n"
        "Rewrite the script with that change. Keep what already works and change "
        "only what's needed. Return ONLY the full revised script."
    )


def generate(
    dc: DayContent,
    idea_key: str,
    duration_seconds: int,
    creator_notes: str = "",
    *,
    feedback: str = "",
    previous: str = "",
) -> str:
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
    idea = IDEAS[idea_key]
    shared = None if idea.get("self_contained") else "_shared.md"
    prompt = build_prompt(tokens, idea["file"], shared=shared)
    if feedback.strip() and previous.strip():
        prompt += _revision_block(previous, feedback)
    return strip_markdown(gemini.generate_text(prompt))
