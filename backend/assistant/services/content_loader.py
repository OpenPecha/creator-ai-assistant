"""
Load day-plan content from the bodhisattvacharyavatara-rails GitHub repo.

On first use, ONE call to the GitHub Git Trees API fetches the full repo file
list and caches it. All subsequent file reads use raw.githubusercontent.com,
which has no meaningful rate limit. No local clone is required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache

import requests as _requests

from django.conf import settings
from django.utils import timezone

# Relative paths inside the rails repo.
_PLAN_ROOT = "3-TRANSFORMATIONS/Plans/the-bodhisattva-challenge/en"
_SCHEDULE = f"{_PLAN_ROOT}/assets/schedule.md"
_DAYS_DIR = f"{_PLAN_ROOT}/Days"
_VERSES_DIR = "3-TRANSFORMATIONS/Translations/en-ai/Verses"

_DASHES = "–—-"
_RANGE_RE = re.compile(rf"(\d+)\.(\d+)\s*[{_DASHES}]\s*(?:(\d+)\.)?(\d+)")
_SINGLE_RE = re.compile(r"(\d+)\.(\d+)")
_TIBETAN_RE = re.compile(r"[ༀ-࿿]")


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
    token = getattr(settings, "GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_raw(path: str) -> str:
    """Fetch a file from the repo via raw.githubusercontent.com.

    raw.githubusercontent.com is not subject to the GitHub API rate limit,
    so this is safe to call per-file without worrying about quotas.
    """
    repo, branch = _github_config()
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        r = _requests.get(url, timeout=15)
    except _requests.RequestException as exc:
        raise ContentError(f"Network error fetching {path}: {exc}") from exc
    if r.status_code == 404:
        raise ContentError(f"File not found in repo: {path}")
    r.raise_for_status()
    return r.text


@lru_cache(maxsize=1)
def _get_repo_file_index() -> frozenset[str]:
    """Fetch the full repo file tree in ONE GitHub API call and cache it.

    Uses the Git Trees API with `recursive=1` so we get every path in the repo
    at once. Subsequent lookups are local dict lookups — zero extra API calls.
    """
    repo, branch = _github_config()
    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
    try:
        r = _requests.get(url, timeout=30, headers=_auth_headers())
    except _requests.RequestException as exc:
        raise ContentError(f"Network error fetching repo tree: {exc}") from exc
    r.raise_for_status()
    data = r.json()
    if "tree" not in data:
        raise ContentError(f"Unexpected GitHub tree response: {data.get('message', data)}")
    return frozenset(item["path"] for item in data["tree"] if item.get("type") == "blob")


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

@lru_cache(maxsize=1)
def get_schedule() -> dict[int, dict]:
    """Parse the schedule markdown table into {day: {verses_label, date, verses}}."""
    text = _fetch_raw(_SCHEDULE)
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
        raise ContentError("No schedule rows parsed from schedule.md")
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

def _find_day_path(day: int) -> tuple[str, bool]:
    """Return (repo-relative path, is_variant) for the day-plan file.

    Uses the cached file index (built from one Git Trees API call) so this
    function itself makes zero network requests.
    """
    index = _get_repo_file_index()

    # All day-plan files live somewhere under _DAYS_DIR.
    prefix = f"{_DAYS_DIR}/"
    day_files = [p for p in index if p.startswith(prefix) and p.endswith(".md")]

    # Exact match: any Chapter-*/N.md
    filename = f"{day}.md"
    exact = [p for p in day_files if p.rsplit("/", 1)[-1] == filename]
    if exact:
        return sorted(exact)[0], False

    # Variant match: N-*.md or day_N_*.md
    variants = [
        p for p in day_files
        if p.rsplit("/", 1)[-1].startswith(f"{day}-")
        or p.rsplit("/", 1)[-1].startswith(f"day_{day}_")
    ]
    if variants:
        return sorted(variants)[0], True

    raise ContentError(f"No day-plan file found for Day {day} in the GitHub repo.")


# ── Public API ────────────────────────────────────────────────────────────────

def _load_verse_synthesis(verse_id: str) -> VerseSynthesis:
    path = f"{_VERSES_DIR}/{verse_id}.md"
    try:
        text = _fetch_raw(path)
        return VerseSynthesis(verse_id=verse_id, text=text, available=True)
    except ContentError:
        return VerseSynthesis(verse_id=verse_id, text="", available=False)


def load_day_content(day: int) -> DayContent:
    """Gather everything needed to generate a script for `day`."""
    schedule = get_schedule()
    if day not in schedule:
        raise ContentError(f"Day {day} is not in the schedule (valid range 1–{max(schedule)}).")

    entry = schedule[day]
    plan_path, is_variant = _find_day_path(day)
    plan_markdown = _fetch_raw(plan_path)
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


@lru_cache(maxsize=128)
def get_day_content(day: int) -> DayContent:
    return load_day_content(day)


def clear_cache() -> None:
    """Drop all caches (e.g. after a repo push webhook)."""
    get_schedule.cache_clear()
    get_day_content.cache_clear()
    _get_repo_file_index.cache_clear()
