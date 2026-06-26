"""Output-language support for the Creator AI Assistant.

A single global language (chosen by the user) drives every generated response:
verse summaries, idea teasers, scripts and structures. Rather than maintaining a
full translated copy of every prompt, we append a strong language directive to
the (English) prompt instructing the model to produce its output in the chosen
language. The directive mirrors the warm, conversational "Chai rule" Hindi tone
used in verse_summary_hindi.md so Hindi output never reads like a stiff textbook
translation.
"""

from __future__ import annotations

# Supported output languages: key -> human-readable name.
LANGUAGES = {
    "english": "English",
    "hindi": "Hindi",
}

DEFAULT_LANGUAGE = "english"


def normalize(language: str | None) -> str:
    """Coerce arbitrary input to a supported language key (defaults to English)."""
    lang = (language or "").strip().lower()
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


# Shared description of the Hindi voice we want, reused by both directives.
_HINDI_TONE = (
    "Write the way everyday Hindustani people actually speak — warm, natural and "
    "human, like talking to a friend over chai. NOT textbook Hindi, NOT a stiff "
    "word-for-word translation, NOT heavy Sanskritized Hindi. It is perfectly fine "
    "to keep common English words (everyday loanwords) where Hindi speakers "
    "naturally use them. Avoid lofty Buddhist jargon; say things in plain terms."
)

_HINDI_PROSE_DIRECTIVE = f"""

## OUTPUT LANGUAGE: HINDI (हिन्दी) — THIS OVERRIDES THE LANGUAGE OF EVERYTHING ABOVE
The instructions above are written in English, but your ENTIRE response MUST be
written in Hindi using Devanagari script. Follow every instruction above, but
produce the final text in Hindi.
- {_HINDI_TONE}
- Do not include any English sentences in the output. Do not add a translation or
  the English version — Hindi only.
"""

_HINDI_JSON_DIRECTIVE = f"""

## OUTPUT LANGUAGE: HINDI (हिन्दी) FOR ALL TEXT VALUES
Keep the JSON structure and every field/key name EXACTLY as specified above (in
English). But every human-readable text VALUE must be written in Hindi using
Devanagari script.
- {_HINDI_TONE}
- Only the readable text values are translated; booleans, numbers, time ranges
  and the JSON keys stay exactly as specified.
"""


def prose_directive(language: str) -> str:
    """Directive to append to a plain-text (prose) generation prompt."""
    return _HINDI_PROSE_DIRECTIVE if normalize(language) == "hindi" else ""


def json_directive(language: str) -> str:
    """Directive to append to a JSON-output generation prompt (keys stay English)."""
    return _HINDI_JSON_DIRECTIVE if normalize(language) == "hindi" else ""
