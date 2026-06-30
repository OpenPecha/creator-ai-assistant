"""Duration → length budgets, shared by the script and structure generators.

Centralizes the words-per-second assumption so both the spoken script and the
storyboard voiceovers scale consistently with the creator's chosen duration,
instead of drifting toward the same "natural" short-form length at every pick.
"""

from __future__ import annotations

# ~150 spoken words per minute => 2.5 words per second.
WORDS_PER_SECOND = 2.5

# How the spoken content is split across the three fixed beats.
# Opening (hook) ~1/5, Middle (develop) ~3/5, End (land it) ~1/5.
_SECTION_SPLIT = (0.2, 0.6, 0.2)


def target_words(duration_seconds: int) -> int:
    """Total spoken-word budget for a video of this length."""
    return max(20, round(duration_seconds * WORDS_PER_SECOND))


def word_range(duration_seconds: int) -> tuple[int, int]:
    """A tight (low, high) word band around the target (~±12%)."""
    target = target_words(duration_seconds)
    low = max(15, round(target * 0.88))
    high = round(target * 1.12)
    return low, high


def section_words(duration_seconds: int) -> tuple[int, int, int]:
    """Word budget for (Opening, Middle, End) — the three fixed beats."""
    target = target_words(duration_seconds)
    op, mid, _end = _SECTION_SPLIT
    opening = max(6, round(target * op))
    middle = max(8, round(target * mid))
    end = max(6, target - opening - middle)
    return opening, middle, end


def section_seconds(duration_seconds: int) -> tuple[int, int, int]:
    """Time budget in seconds for (Opening, Middle, End)."""
    op, mid, _end = _SECTION_SPLIT
    opening = max(2, round(duration_seconds * op))
    middle = max(3, round(duration_seconds * mid))
    end = max(2, duration_seconds - opening - middle)
    return opening, middle, end
