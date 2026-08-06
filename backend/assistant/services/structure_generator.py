"""Generate a shot-by-shot video structure (storyboard) for a day + idea + duration.

Unlike the script generator (which returns spoken prose), this returns a
structured storyboard: a core theme, a concept hook, and timed beats — each with
on-screen visuals and a voiceover line.
"""

from __future__ import annotations

import json

from . import gemini, language as lang_service, length as length_service
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
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "visuals": {"type": "array", "items": {"type": "string"}},
                                "voiceover": {"type": "string"},
                            },
                            "required": ["visuals", "voiceover"],
                        },
                        "minItems": 1,
                    },
                },
                "required": ["label", "timeRange", "options"],
            },
        },
    },
    "required": ["coreTheme", "concept", "sections"],
}


def _length_budget(duration_seconds: int, *, self_contained: bool = False) -> str:
    """Concrete word budget so voiceover volume scales with the duration.

    The storyboard always keeps the three fixed beats (Opening / Middle / End);
    longer durations are absorbed by giving each beat MORE voiceover — the Middle
    carrying most of it — rather than by adding beats. Without this the model
    produces the same three short beats at every length.

    Spells out a per-beat word RANGE (not just a single target) and asks the
    model to literally count words and rewrite before returning, since a bare
    "aim for ~N words" target is easy for the model to drift from — the
    self-check turns it into something the model actually verifies rather than
    estimates.
    """
    target = length_service.target_words(duration_seconds)
    low, high = length_service.word_range(duration_seconds)
    opening, middle, end = length_service.section_words(duration_seconds)
    op_s, mid_s, end_s = length_service.section_seconds(duration_seconds)
    (op_lo, op_hi), (mid_lo, mid_hi), (end_lo, end_hi) = length_service.section_word_range(duration_seconds)

    if self_contained:
        return (
            f"This is a {duration_seconds}-second video in the three beats — Opening "
            f"(~{op_s}s, {op_lo}–{op_hi} words), Middle (~{mid_s}s, {mid_lo}–{mid_hi} "
            f"words), End (~{end_s}s, {end_lo}–{end_hi} words). Keep every voiceover a "
            "crisp one-liner. For a longer video, the Middle can hold two or three "
            "short lines and the visuals fill the rest of the seconds — never stuff "
            "a single line with extra words. Hold each beat's option voiceovers to a "
            "similar, punchy length so the total holds whichever the creator picks.\n"
            "**Before you finalize, literally count the words in every voiceover "
            "line and rewrite any that fall outside its beat's word range above.** "
            "The creator times the shoot to these seconds exactly — a line that runs "
            "short or long throws off the whole take, so hitting the count matters "
            "as much as what the line says."
        )

    return (
        f"At a natural speaking pace a {duration_seconds}-second video is about "
        f"{target} spoken words. Keep the three fixed beats and fit the whole "
        f"{target} words ({low}–{high}) INTO them — do not add beats. This is a HARD "
        f"requirement, not a rough guide: Opening {op_lo}–{op_hi} words, Middle "
        f"{mid_lo}–{mid_hi} words (it carries most of it), End {end_lo}–{end_hi} "
        "words. The creator picks ONE option per beat, so every option within a beat "
        "must land in that SAME beat's range — not just one of the three. A longer "
        "video means fuller lines in each beat — especially the Middle — not extra "
        "beats; a shorter one stays tight.\n"
        "**Before you finalize your answer, literally count the words in every "
        "voiceover option you wrote (all beats, all versions) and rewrite any that "
        "fall outside its beat's word range above — do not skip this check.** The "
        "creator times their shoot to the seconds they picked; a voiceover that reads "
        "noticeably faster or slower than that breaks the take, so hitting the word "
        "count matters as much as what the line says."
    )


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
    language: str = "english",
    focus: str = "",
    focus_label: str = "",
) -> dict:
    if idea_key not in IDEAS:
        raise ValueError(f"Unknown idea: {idea_key!r}")

    idea = IDEAS[idea_key]
    tokens = {
        "DAY": str(dc.day),
        "DATE": dc.date,
        "VERSES_LABEL": dc.verses_label,
        "DURATION_SECONDS": str(duration_seconds),
        "LENGTH_BUDGET": _length_budget(
            duration_seconds, self_contained=bool(idea.get("self_contained"))
        ),
        "IDEA_LABEL": idea["label"],
        "IDEA_FOCUS": idea["blurb"],
        "VERSE_TEXT": dc.verse_block or "(no verse text found)",
        "DAY_PLAN": dc.plan_markdown,
        "VERSE_SYNTHESIS": dc.synthesis_text or "(no per-verse commentary available)",
        "TEACHING_POINTS": dc.teaching_points_text or "(no distilled teaching points available)",
        "CREATOR_NOTES": creator_notes.strip() or "(none provided)",
    }
    if idea.get("self_contained"):
        template_name = "structure_creative.md"
    elif idea_key == "testimony":
        # Testimony is built around the creator's own experience (grounded by the
        # day's teaching points), not the day's general theme — its own template.
        template_name = "structure_testimony.md"
    else:
        template_name = "structure.md"
    prompt = load_prompt(template_name)
    for key, value in tokens.items():
        prompt = prompt.replace("{{" + key + "}}", value)
    if focus.strip():
        label = focus_label.strip()
        heading = f"## Primary focus — build the video around THIS: {label}" if label else \
            "## Primary focus — build the video around THIS"
        commentary_note = (
            "\nThis is ONE classical commentator's specific reading — not a summary "
            "of everything today's commentaries say. Build every beat around THEIR "
            "interpretation; don't blend in other commentators or drift to a generic "
            "take on the verse. **Name them by name only ONCE across this version's "
            "three beats** (the Opening or early Middle), and fold in the text/book "
            "they're drawn from there if it adds credibility — same as you'd introduce "
            "any named teacher on camera. In the OTHER two beats of this same version, "
            "do NOT say their name or title again — refer to them with a pronoun "
            "('he,' 'his teaching') or drop the reference entirely and just carry the "
            "idea forward. A real creator introduces their source once, not in every "
            "beat — three separate re-introductions of the same teacher in one video "
            "reads as a scripting mistake, not a style choice.\n"
        ) if idea_key == "commentary" else ""
        concept_note = (
            "\nThis is ONE distilled teaching point — already extracted and clear, not "
            "one commentator's personal voice (the explanation below may cite several "
            "commentators agreeing on it). Build every beat around making THIS exact "
            "lesson unmistakable: a viewer should be able to repeat it back in their "
            "own words by the End beat. Don't broaden to the day's general theme or "
            "blend in other teaching points, and don't turn it into a name-drop of the "
            "commentators cited below — the lesson is the star, not who said it.\n"
        ) if idea_key == "concept" else ""
        prompt += (
            f"\n\n{heading}\n"
            f"{commentary_note}{concept_note}"
            "The creator picked this specific piece of source material for the video. "
            "This IS the video — build the entire storyboard around it and keep it the "
            "subject of every beat, from the opening hook to the close. The rest of the "
            "day's context above exists ONLY to keep you accurate (correct terms, who a "
            "teacher is, faithful meaning) — do NOT pull ideas, images, stories, or "
            "angles from it, and do NOT drift onto the day's general theme or other "
            "verses. If a beat isn't drawn from the material below, it does not belong "
            "in this video:\n\n"
            f'"""\n{focus.strip()[:2500]}\n"""\n'
        )
    if feedback.strip() and previous:
        prompt += _revision_block(previous, feedback)
    prompt += lang_service.json_directive(language)

    data = gemini.generate_json(prompt, schema=_SCHEMA)

    # Scrub any stray markdown so the storyboard renders as clean text.
    data["coreTheme"] = strip_markdown(data.get("coreTheme", ""))
    data["concept"] = strip_markdown(data.get("concept", ""))
    for s in data.get("sections", []):
        for opt in s.get("options", []):
            opt["voiceover"] = strip_markdown(opt.get("voiceover", ""))
            opt["visuals"] = [strip_markdown(v) for v in opt.get("visuals", []) if v and v.strip()]
    return data
