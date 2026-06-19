"""Catalog of the fixed video-idea types and the prompt-template loader."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# key -> (label, prompt filename, always_available)
IDEAS: dict[str, dict] = {
    "concept": {"label": "Concept", "file": "concept.md", "always": True,
                "blurb": "Explain the idea behind today's verses."},
    "practice": {"label": "Challenge / Practice", "file": "practice.md", "always": True,
                 "blurb": "Invite viewers to do today's practice."},
    "testimony": {"label": "Testimony", "file": "testimony.md", "always": True,
                  "blurb": "Share your own experience (you provide the notes)."},
    "story": {"label": "Story", "file": "story.md", "always": False,
              "blurb": "Tell a story or parable from the source."},
    "extra_info": {"label": "Extra info / fun fact", "file": "extra_info.md", "always": False,
                   "blurb": "Share a surprising detail from the texts."},
}

# Ideas whose presence depends on the day's content.
CONDITIONAL_IDEAS = [k for k, v in IDEAS.items() if not v["always"]]
ALWAYS_IDEAS = [k for k, v in IDEAS.items() if v["always"]]


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Read a prompt template file (e.g. 'concept.md', '_shared.md')."""
    path = _PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def build_prompt(tokens: dict[str, str], idea_file: str) -> str:
    """Assemble the shared context + idea-specific instructions, filling {{TOKENS}}.

    Token substitution uses plain string replacement (not str.format) so that
    braces in the injected source content are never interpreted.
    """
    template = load_prompt("_shared.md") + "\n\n" + load_prompt(idea_file)
    for key, value in tokens.items():
        template = template.replace("{{" + key + "}}", value)
    return template
