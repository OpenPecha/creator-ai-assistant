"""
Load day-plan content from the bodhisattvacharyavatara-rails GitHub repo.

Every request fetches fresh content directly from raw.githubusercontent.com.
No local clone, no cache, no stale data — new content pushed to GitHub is
available immediately on the next request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import requests as _requests

from django.conf import settings
from django.utils import timezone

# Relative paths inside the rails repo.
_PLAN_ROOT = "3-TRANSFORMATIONS/Plans/the-bodhisattva-challenge/en"
_SCHEDULE = f"{_PLAN_ROOT}/assets/schedule-corrected.md"
_DAYS_DIR = f"{_PLAN_ROOT}/Days"
_VERSES_DIR = "3-TRANSFORMATIONS/Translations/en-ai/Verses"

_DASHES = "–—-"
_RANGE_RE = re.compile(rf"(\d+)\.(\d+)\s*[{_DASHES}]\s*(?:(\d+)\.)?(\d+)")
_SINGLE_RE = re.compile(r"(\d+)\.(\d+)")
_TIBETAN_RE = re.compile(r"[ༀ-࿿]")

# Common variant suffixes to probe if the exact day file isn't found.
_VARIANT_SUFFIXES = ["-A", "-B", "-option-1", "-option-2", "-new", "-Final", "-final"]


class ContentError(Exception):
    """Raised when source content cannot be located or parsed."""


@dataclass
class VerseSynthesis:
    verse_id: str
    text: str
    available: bool


@dataclass
class DayContent:
    day: int
    verses: list[str]
    verses_label: str
    date: str
    plan_markdown: str
    plan_file: str
    verse_syntheses: list[VerseSynthesis] = field(default_factory=list)
    verses_text: list[str] = field(default_factory=list)
    is_variant: bool = False

    @property
    def synthesis_text(self) -> str:
        parts = []
        for vs in self.verse_syntheses:
            if vs.available:
                parts.append(f"### Verse {vs.verse_id}\n\n{vs.text}")
        return "\n\n---\n\n".join(parts)

    @property
    def verse_block(self) -> str:
        return "\n\n".join(self.verses_text)


# ── GitHub helpers ────────────────────────────────────────────────────────────

def _github_config() -> tuple[str, str]:
    repo = getattr(settings, "GITHUB_REPO", "")
    if not repo:
        raise ContentError(
            "GITHUB_REPO is not set. Add GITHUB_REPO=owner/repo-name to backend/.env."
        )
    branch = getattr(settings, "GITHUB_BRANCH", "main")
    return repo, branch


def _auth_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = getattr(settings, "GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _list_github_dir(path: str) -> list[str]:
    """Return directory entry names via the GitHub Contents API."""
    repo, branch = _github_config()
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    try:
        r = _requests.get(url, timeout=15, headers=_auth_headers())
    except _requests.RequestException as exc:
        raise ContentError(f"Network error listing {path}: {exc}") from exc
    if r.status_code == 404:
        return []
    r.raise_for_status()
    data = r.json()
    return [item["name"] for item in data] if isinstance(data, list) else []


def _fetch_raw(path: str) -> str | None:
    """Fetch a file from the repo via raw.githubusercontent.com.

    Returns None on 404 (file doesn't exist) so callers can try fallback paths.
    Raises ContentError on network errors or unexpected HTTP errors.
    """
    repo, branch = _github_config()
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        r = _requests.get(url, timeout=15)
    except _requests.RequestException as exc:
        raise ContentError(f"Network error fetching {path}: {exc}") from exc
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.text


# ── Content parsing ───────────────────────────────────────────────────────────

def extract_today_verses(plan_markdown: str) -> list[str]:
    """Pull English verse translations from the '## Today's Verses' section."""
    verses: list[str] = []
    current: list[str] = []
    in_section = False

    for line in plan_markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            low = stripped.lower()
            in_section = "today" in low and "verse" in low
            continue
        if not in_section:
            continue
        if stripped == "":
            if current:
                verses.append("\n".join(current))
                current = []
            continue
        if stripped.startswith(">"):
            text = stripped.lstrip(">").strip()
            if not text or _TIBETAN_RE.search(text):
                continue
            current.append(text)

    if current:
        verses.append("\n".join(current))
    return verses


def expand_verses(label: str) -> list[str]:
    """Expand a schedule verse label into verse ids.

    "1.12–1.14" -> ["1-12", "1-13", "1-14"]
    """
    ids: list[str] = []
    seen: set[str] = set()
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
        if any(s <= m.start() < e for s, e in consumed_spans):
            continue
        vid = f"{int(m.group(1))}-{int(m.group(2))}"
        if vid not in seen:
            seen.add(vid)
            ids.append(vid)

    return ids


# ── Schedule ──────────────────────────────────────────────────────────────────

def get_schedule() -> dict[int, dict]:
    """Fetch and parse the schedule markdown table from GitHub."""
    text = _fetch_raw(_SCHEDULE)
    if text is None:
        raise ContentError("schedule.md not found in the GitHub repo.")
    schedule: dict[int, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3 or not cells[0].isdigit():
            continue
        day = int(cells[0])
        schedule[day] = {
            "verses_label": cells[1],
            "date": cells[2],
            "verses": expand_verses(cells[1]),
        }
    if not schedule:
        raise ContentError("No schedule rows parsed from schedule.md.")
    return schedule


def _parse_anchor_date(date_str: str) -> date | None:
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def released_progress() -> dict:
    """How many days of the plan are live as of the server's local date."""
    schedule = get_schedule()
    total = max(schedule)
    anchor = _parse_anchor_date(schedule[1]["date"]) if 1 in schedule else None
    today = timezone.localdate()

    if anchor is None:
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


# ── Day file lookup ───────────────────────────────────────────────────────────

def _find_day_path(day: int, verses: list[str]) -> tuple[str, bool]:
    """Find the day-plan file path in the GitHub repo.

    Lists the Days directory once per request to find the correct
    Chapter folder (which may have a suffix like 'Chapter-1 D1-D14'),
    then probes for the exact file or common variant names.
    """
    chapter = int(verses[0].split("-")[0]) if verses else 1

    # Find the chapter directory — name starts with "Chapter-{chapter}".
    all_dirs = _list_github_dir(_DAYS_DIR)
    chapter_dir = next(
        (d for d in all_dirs if d.startswith(f"Chapter-{chapter}")),
        None,
    )
    if chapter_dir is None:
        raise ContentError(f"No Chapter-{chapter} directory found under Days/ in the repo.")

    base = f"{_DAYS_DIR}/{chapter_dir}"

    # Exact match.
    exact = f"{base}/{day}.md"
    if _fetch_raw(exact) is not None:
        return exact, False

    # Variant suffixes.
    for suffix in _VARIANT_SUFFIXES:
        path = f"{base}/{day}{suffix}.md"
        if _fetch_raw(path) is not None:
            return path, True

    raise ContentError(f"No day-plan file found for Day {day} in the GitHub repo.")


# ── Public API ────────────────────────────────────────────────────────────────

def _load_verse_synthesis(verse_id: str) -> VerseSynthesis:
    path = f"{_VERSES_DIR}/{verse_id}.md"
    text = _fetch_raw(path)
    return VerseSynthesis(verse_id=verse_id, text=text or "", available=text is not None)


def get_day_content(day: int) -> DayContent:
    """Fetch everything needed to generate a script for `day` from GitHub."""
    schedule = get_schedule()
    if day not in schedule:
        raise ContentError(f"Day {day} is not in the schedule (valid range 1–{max(schedule)}).")

    entry = schedule[day]
    plan_path, is_variant = _find_day_path(day, entry["verses"])
    plan_markdown = _fetch_raw(plan_path)
    if plan_markdown is None:
        raise ContentError(f"Day plan file disappeared after lookup: {plan_path}")
    syntheses = [_load_verse_synthesis(vid) for vid in entry["verses"]]

    return DayContent(
        day=day,
        verses=entry["verses"],
        verses_label=entry["verses_label"],
        date=entry["date"],
        plan_markdown=plan_markdown,
        plan_file=plan_path,
        verse_syntheses=syntheses,
        verses_text=extract_today_verses(plan_markdown),
        is_variant=is_variant,
    )


def clear_cache() -> None:
    pass  # no-op — no cache to clear
