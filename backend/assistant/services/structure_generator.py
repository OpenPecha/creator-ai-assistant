"""Generate a shot-by-shot video structure (storyboard) for a day + idea + duration.

Unlike the script generator (which returns spoken prose), this returns a
structured storyboard: a core theme, a concept hook, and timed beats — each with
on-screen visuals and a voiceover line.
"""

from __future__ import annotations

import json

from . import gemini
from .content_loader import DayContent
from .ideas import IDEAS, load_prompt
from .script_generator import strip_markdown

_SCHEMA = {
    "type": "object",
    "properties": {
        "coreTheme": {"type": "string"},
        "concept": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "timeRange": {"type": "string"},
                    "visuals": {"type": "array", "items": {"type": "string"}},
                    "voiceover": {"type": "string"},
                },
                "required": ["label", "timeRange", "visuals", "voiceover"],
            },
        },
    },
    "required": ["coreTheme", "concept", "sections"],
}


def _revision_block(previous: dict, feedback: str) -> str:
    prev = json.dumps(previous, ensure_ascii=False)[:6000]
    return (
        "\n\n## Revision request\n"
        "You previously produced this structure (as JSON):\n"
        f"{prev}\n\n"
        f"The creator wants it improved: {feedback.strip()}\n\n"
        "Revise it with that change, keeping what already works. Return the full "
        "revised structure as JSON."
    )


def generate(
    dc: DayContent,
    idea_key: str,
    duration_seconds: int,
    creator_notes: str = "",
    *,
    feedback: str = "",
    previous: dict | None = None,
) -> dict:
    if idea_key not in IDEAS:
        raise ValueError(f"Unknown idea: {idea_key!r}")

    idea = IDEAS[idea_key]
    tokens = {
        "DAY": str(dc.day),
        "DATE": dc.date,
        "VERSES_LABEL": dc.verses_label,
        "DURATION_SECONDS": str(duration_seconds),
        "IDEA_LABEL": idea["label"],
        "IDEA_FOCUS": idea["blurb"],
        "VERSE_TEXT": dc.verse_block or "(no verse text found)",
        "DAY_PLAN": dc.plan_markdown,
        "VERSE_SYNTHESIS": dc.synthesis_text or "(no per-verse commentary available)",
        "CREATOR_NOTES": creator_notes.strip() or "(none provided)",
    }
    template_name = "structure_creative.md" if idea.get("self_contained") else "structure.md"
    prompt = load_prompt(template_name)
    for key, value in tokens.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    if feedback.strip() and previous:
        prompt += _revision_block(previous, feedback)

    data = gemini.generate_json(prompt, schema=_SCHEMA)

    # Scrub any stray markdown so the storyboard renders as clean text.
    data["coreTheme"] = strip_markdown(data.get("coreTheme", ""))
    data["concept"] = strip_markdown(data.get("concept", ""))
    for s in data.get("sections", []):
        s["voiceover"] = strip_markdown(s.get("voiceover", ""))
        s["visuals"] = [strip_markdown(v) for v in s.get("visuals", []) if v and v.strip()]
    return data
