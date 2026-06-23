"""
Load day-plan content from a local clone of the bodhisattvacharyavatara-rails repo.

A "Day N" of the 365-day Bodhisattva Challenge maps to:
  - a verse list + date, from the English schedule table
  - a day-plan markdown file (6-section format)
  - per-verse commentary synthesis files (rich prose: stories, fun facts, concepts)

This module is pure file IO + parsing — no network, no LLM. Results are cached
in-memory per day since the source repo is static between manual `git pull`s.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import timezone

# Relative paths inside the rails repo.
_PLAN_ROOT = "3-TRANSFORMATIONS/Plans/the-bodhisattva-challenge/en"
_SCHEDULE = f"{_PLAN_ROOT}/assets/schedule.md"
_DAYS_DIR = f"{_PLAN_ROOT}/Days"
_VERSES_DIR = "3-TRANSFORMATIONS/Translations/en-ai/Verses"

# en-dash / em-dash / hyphen used in "1.12–1.14" ranges.
_DASHES = "–—-"
_RANGE_RE = re.compile(rf"(\d+)\.(\d+)\s*[{_DASHES}]\s*(?:(\d+)\.)?(\d+)")
_SINGLE_RE = re.compile(r"(\d+)\.(\d+)")

# Any Tibetan-script character (used to drop the Tibetan lines from the verse block).
_TIBETAN_RE = re.compile(r"[ༀ-࿿]")


class ContentError(Exception):
    """Raised when source content cannot be located or parsed."""


@dataclass
class VerseSynthesis:
    verse_id: str          # e.g. "1-12"
    text: str              # full markdown of the synthesis file
    available: bool        # whether a synthesis file exists


@dataclass
class DayContent:
    day: int
    verses: list[str]               # verse ids, e.g. ["1-12", "1-13", "1-14"]
    verses_label: str               # raw schedule label, e.g. "1.12–1.14"
    date: str
    plan_markdown: str              # the day-plan file contents
    plan_file: str                  # repo-relative path used
    verse_syntheses: list[VerseSynthesis] = field(default_factory=list)
    verses_text: list[str] = field(default_factory=list)  # English translation, one entry per verse
    is_variant: bool = False        # True if no exact N.md and a variant was used

    @property
    def synthesis_text(self) -> str:
        """Concatenated synthesis prose for the LLM, with verse headers."""
        parts = []
        for vs in self.verse_syntheses:
            if vs.available:
                parts.append(f"### Verse {vs.verse_id}\n\n{vs.text}")
        return "\n\n---\n\n".join(parts)

    @property
    def verse_block(self) -> str:
        """The English verse text, verses separated by a blank line."""
        return "\n\n".join(self.verses_text)


def extract_today_verses(plan_markdown: str) -> list[str]:
    """Pull the English verse translation from the '## Today's Verses' section.

    Each day plan has a "## Today's Verses" section with blockquotes that pair the
    Tibetan root text with its English translation. We keep only the English lines,
    grouped one entry per verse.
    """
    verses: list[str] = []
    current: list[str] = []
    in_section = False

    for line in plan_markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break  # reached the next section
            low = stripped.lower()
            in_section = "today" in low and "verse" in low
            continue
        if not in_section:
            continue
        if stripped == "":
            # blank line = boundary between verses
            if current:
                verses.append("\n".join(current))
                current = []
            continue
        if stripped.startswith(">"):
            text = stripped.lstrip(">").strip()
            if not text or _TIBETAN_RE.search(text):
                continue  # skip the intra-verse separator and Tibetan lines
            current.append(text)

    if current:
        verses.append("\n".join(current))
    return verses


def _repo_path() -> Path:
    raw = settings.RAILS_REPO_PATH
    if not raw:
        raise ContentError(
            "RAILS_REPO_PATH is not set. Point it at your local clone of the "
            "bodhisattvacharyavatara-rails repo (see backend/.env.example)."
        )
    path = Path(raw)
    if not path.exists():
        raise ContentError(f"RAILS_REPO_PATH does not exist: {path}")
    return path


def expand_verses(label: str) -> list[str]:
    """Expand a schedule verse label into verse ids.

    Examples:
      "1.12–1.14"        -> ["1-12", "1-13", "1-14"]
      "Prologue, 1.1–1.3" -> ["1-1", "1-2", "1-3"]
      "2.1–2.3"          -> ["2-1", "2-2", "2-3"]
      "1.4–1.5"          -> ["1-4", "1-5"]

    Ranges are assumed to stay within one chapter (true for this schedule).
    Non-verse tokens like "Prologue" are ignored.
    """
    ids: list[str] = []
    seen: set[str] = set()

    # Handle ranges first, then any standalone single verses not in a range.
    consumed_spans: list[tuple[int, int]] = []
    for m in _RANGE_RE.finditer(label):
        chapter = int(m.group(1))
        start = int(m.group(2))
        end = int(m.group(4))
        for v in range(start, end + 1):
            vid = f"{chapter}-{v}"
            if vid not in seen:
                seen.add(vid)
                ids.append(vid)
        consumed_spans.append(m.span())

    for m in _SINGLE_RE.finditer(label):
        # Skip if this single match falls inside a range we already expanded.
        if any(s <= m.start() < e for s, e in consumed_spans):
            continue
        vid = f"{int(m.group(1))}-{int(m.group(2))}"
        if vid not in seen:
            seen.add(vid)
            ids.append(vid)

    return ids


@lru_cache(maxsize=1)
def get_schedule() -> dict[int, dict]:
    """Parse the schedule markdown table into {day: {verses_label, date, verses}}."""
    schedule_file = _repo_path() / _SCHEDULE
    if not schedule_file.exists():
        raise ContentError(f"Schedule file not found: {schedule_file}")

    schedule: dict[int, dict] = {}
    for line in schedule_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        day_cell = cells[0]
        if not day_cell.isdigit():
            continue  # header row or separator
        day = int(day_cell)
        verses_label = cells[1]
        date = cells[2]
        schedule[day] = {
            "verses_label": verses_label,
            "date": date,
            "verses": expand_verses(verses_label),
        }
    if not schedule:
        raise ContentError(f"No schedule rows parsed from {schedule_file}")
    return schedule


def _parse_anchor_date(date_str: str) -> date | None:
    """Parse Day 1's full date (e.g. 'May 31, 2026') into a date object.

    Later schedule rows omit the year (e.g. 'Jun 1'), but Day 1 carries the
    year, so it serves as the anchor for the whole 365-day arc.
    """
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def released_progress() -> dict:
    """How many days of the plan are live as of the server's local date.

    The schedule runs one verse-day per calendar day starting from Day 1's
    anchor date, so released = (today - anchor) + 1, clamped to [0, total].
    """
    schedule = get_schedule()
    total = max(schedule)
    anchor = _parse_anchor_date(schedule[1]["date"]) if 1 in schedule else None
    today = timezone.localdate()

    if anchor is None:
        # Anchor unparseable — report the full plan rather than guessing.
        return {"released": total, "total": total, "started": True, "today": today.isoformat()}

    released = (today - anchor).days + 1
    released = max(0, min(released, total))
    return {
        "released": released,
        "total": total,
        "started": released > 0,
        "today": today.isoformat(),
        "startDate": anchor.isoformat(),
    }


def find_day_file(day: int) -> tuple[Path, bool]:
    """Locate the day-plan file for `day` under any Chapter-* folder.

    Returns (path, is_variant). Prefers an exact `N.md`; otherwise falls back to
    the first variant (`N-*.md` / `day_N_*.md`) and flags it.
    """
    days_dir = _repo_path() / _DAYS_DIR
    if not days_dir.exists():
        raise ContentError(f"Days directory not found: {days_dir}")

    # Exact match: <N>.md in any chapter folder.
    exact = sorted(days_dir.glob(f"Chapter-*/{day}.md"))
    if exact:
        return exact[0], False

    # Variant fallback: N-option-*.md, N-new.md, N-Final.md, day_N_option_*.md
    variants = sorted(
        list(days_dir.glob(f"Chapter-*/{day}-*.md"))
        + list(days_dir.glob(f"Chapter-*/day_{day}_*.md"))
    )
    if variants:
        return variants[0], True

    raise ContentError(
        f"No day-plan file found for Day {day} under {days_dir} "
        f"(looked for {day}.md and variants)."
    )


def _load_verse_synthesis(verse_id: str) -> VerseSynthesis:
    path = _repo_path() / _VERSES_DIR / f"{verse_id}.md"
    if path.exists():
        return VerseSynthesis(verse_id=verse_id, text=path.read_text(encoding="utf-8"), available=True)
    return VerseSynthesis(verse_id=verse_id, text="", available=False)


def load_day_content(day: int) -> DayContent:
    """Gather everything needed to generate a script for `day`."""
    schedule = get_schedule()
    if day not in schedule:
        raise ContentError(f"Day {day} is not in the schedule (valid range 1–{max(schedule)}).")

    entry = schedule[day]
    plan_path, is_variant = find_day_file(day)
    repo = _repo_path()

    syntheses = [_load_verse_synthesis(vid) for vid in entry["verses"]]
    plan_markdown = plan_path.read_text(encoding="utf-8")

    return DayContent(
        day=day,
        verses=entry["verses"],
        verses_label=entry["verses_label"],
        date=entry["date"],
        plan_markdown=plan_markdown,
        plan_file=str(plan_path.relative_to(repo)),
        verse_syntheses=syntheses,
        verses_text=extract_today_verses(plan_markdown),
        is_variant=is_variant,
    )


# Cache assembled DayContent objects (cheap to rebuild, but avoids re-reading files).
@lru_cache(maxsize=128)
def get_day_content(day: int) -> DayContent:
    return load_day_content(day)


def clear_cache() -> None:
    """Drop caches after the source repo is updated."""
    get_schedule.cache_clear()
    get_day_content.cache_clear()
