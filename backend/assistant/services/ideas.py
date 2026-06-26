"""Catalog of the fixed video-idea types and the prompt-template loader."""

from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# key -> (label, Hindi label, prompt filename, always_available, blurb, Hindi blurb)
IDEAS: dict[str, dict] = {
    "concept": {"label": "Concept", "label_hi": "मुख्य विचार", "file": "concept.md", "always": True,
                "blurb": "Explain the idea behind today's verses.",
                "blurb_hi": "आज के श्लोक के पीछे का विचार समझाएँ।"},
    "practice": {"label": "Challenge / Practice", "label_hi": "अभ्यास / चुनौती", "file": "practice.md", "always": True,
                 "blurb": "Invite viewers to do today's practice.",
                 "blurb_hi": "दर्शकों को आज का अभ्यास करने के लिए बुलाएँ।"},
    "creative": {"label": "Creative", "label_hi": "क्रिएटिव", "file": "creative.md", "always": True,
                 "self_contained": True,
                 "blurb": "A fresh, universal video about the lesson behind it — for everyone, no scripture.",
                 "blurb_hi": "सीख पर एक नई, सबके लिए वीडियो — बिना किसी धर्मग्रंथ के।"},
    "testimony": {"label": "Testimony", "label_hi": "आपका अनुभव", "file": "testimony.md", "always": True,
                  "blurb": "Share your own experience (you provide the notes).",
                  "blurb_hi": "अपना खुद का अनुभव साझा करें (नोट्स आप देंगे)।"},
    "story": {"label": "Story", "label_hi": "कहानी", "file": "story.md", "always": False,
              "blurb": "Tell a story or parable from the source.",
              "blurb_hi": "स्रोत से कोई कहानी या दृष्टांत सुनाएँ।"},
    "extra_info": {"label": "Extra info / fun fact", "label_hi": "रोचक जानकारी", "file": "extra_info.md", "always": False,
                   "blurb": "Share a surprising detail from the texts.",
                   "blurb_hi": "ग्रंथों से कोई चौंकाने वाली बात बताएँ।"},
}


def idea_label(key: str, language: str = "english") -> str:
    """Return an idea's display label in the chosen language (falls back to English)."""
    meta = IDEAS[key]
    if (language or "").lower() == "hindi":
        return meta.get("label_hi") or meta["label"]
    return meta["label"]


def idea_blurb(key: str, language: str = "english") -> str:
    """Return an idea's fallback teaser blurb in the chosen language."""
    meta = IDEAS[key]
    if (language or "").lower() == "hindi":
        return meta.get("blurb_hi") or meta["blurb"]
    return meta["blurb"]

# Ideas whose presence depends on the day's content.
CONDITIONAL_IDEAS = [k for k, v in IDEAS.items() if not v["always"]]
ALWAYS_IDEAS = [k for k, v in IDEAS.items() if v["always"]]


def load_prompt(name: str) -> str:
    """Read a prompt template file (e.g. 'concept.md', '_shared.md').

    Not cached, so edits to the prompt "skills" take effect on the next request
    without a server restart.
    """
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(tokens: dict[str, str], idea_file: str, shared: str | None = "_shared.md") -> str:
    """Assemble the (optional) shared context + idea-specific instructions, filling {{TOKENS}}.

    Token substitution uses plain string replacement (not str.format) so that
    braces in the injected source content are never interpreted. Pass shared=None
    for self-contained idea prompts (e.g. Creative) that must not inherit the
    source-faithful shared rules.
    """
    parts = []
    if shared:
        parts.append(load_prompt(shared))
    parts.append(load_prompt(idea_file))
    template = "\n\n".join(parts)
    for key, value in tokens.items():
        template = template.replace("{{" + key + "}}", value)
    return template
