"""
Load day-plan content from the bodhisattvacharyavatara-rails GitHub repo.

Content is fetched from GitHub (raw.githubusercontent.com + the Contents API)
and served through a short per-process TTL cache, so new content pushed to
GitHub becomes available on the next request after the cache window elapses.
See the "HTTP response cache" section below for the rationale and tuning.
"""

from __future__ import annotations

import re
import threading as _threading
import time as _time
from dataclasses import dataclass, field
from datetime import date, datetime

import requests as _requests

from django.conf import settings
from django.utils import timezone

from . import day_package, ipv4

# GitHub publishes IPv6 records; on networks where the IPv6 route is blackholed
# every fetch stalls for the full timeout before falling back. This session
# pins GitHub connections to IPv4 (see assistant.services.ipv4). We still use
# `_requests` above for its exception classes.
_http = ipv4.requests_session()

# Relative paths inside the rails repo.
_PLAN_ROOT = "3-TRANSFORMATIONS/Plans/the-bodhisattva-challenge/en"
_SCHEDULE = f"{_PLAN_ROOT}/assets/schedule-hhdl-birthday.md"
# Each day's content is a single consolidated "Day-Package" file, `{day}-en.md`,
# living under a chapter subdirectory (e.g. "Chapter-1 D1-D14"). See day_package.py
# for its structure. A day with no package is unavailable (get_day_content raises).
_PACKAGES_DIR = f"{_PLAN_ROOT}/Day-Packages"

_DASHES = "–—-"
_RANGE_RE = re.compile(rf"(\d+)\.(\d+)\s*[{_DASHES}]\s*(?:(\d+)\.)?(\d+)")
_SINGLE_RE = re.compile(r"(\d+)\.(\d+)")


class ContentError(Exception):
    """Raised when source content cannot be located or parsed."""


class ContentUnavailableError(ContentError):
    """Raised when GitHub is transiently unreachable/erroring (safe to retry)."""


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
    stories: list[str] = field(default_factory=list)
    # Per-verse selectable source material, keyed by verse id, then by idea
    # category: {"1-1": {"story": [{label, text}], "concept": [...], "extra_info": [...]}}.
    # story ← package stories, concept ← commentaries, extra_info ← metaphors.
    verse_resources: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
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


# ── HTTP response cache ───────────────────────────────────────────────────────
# GitHub is the source of truth, but fetching every file live on every request
# means 5–14 outbound calls per day-load and quickly exhausts GitHub's API rate
# limits under real traffic. A short per-process TTL cache collapses repeat reads
# (schedule, day files, verse files, directory listings) to ~1 network round-trip
# per file per TTL window. Only successful responses (including 404s) are cached;
# transient errors are never cached, so a retry always re-hits GitHub.
#
# The cache is per-process: with multiple gunicorn workers each keeps its own
# copy, which is fine for shedding load. Use a shared cache (e.g. Redis) if you
# later need cross-worker consistency. Tune or disable via the GITHUB_CACHE_TTL
# setting (seconds; 0 disables caching entirely).
_MISS = object()
_cache_lock = _threading.Lock()
_cache: dict[str, tuple[float, object]] = {}


def _cache_ttl() -> int:
    return int(getattr(settings, "GITHUB_CACHE_TTL", 300))


def _cache_get(key: str):
    """Return the cached value for `key`, or the `_MISS` sentinel if absent/stale.

    Uses a sentinel rather than None because None is a valid cached value (a 404).
    """
    if _cache_ttl() <= 0:
        return _MISS
    now = _time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return _MISS
        expires, value = hit
        if expires <= now:
            _cache.pop(key, None)
            return _MISS
        return value


def _cache_set(key: str, value) -> None:
    ttl = _cache_ttl()
    if ttl <= 0:
        return
    with _cache_lock:
        _cache[key] = (_time.monotonic() + ttl, value)


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
    cache_key = f"dir:{path}"
    cached = _cache_get(cache_key)
    if cached is not _MISS:
        return cached

    repo, branch = _github_config()
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    try:
        r = _http.get(url, timeout=15, headers=_auth_headers())
    except _requests.RequestException as exc:
        # Connection reset / timeout / DNS — transient and safe to retry.
        raise ContentUnavailableError(f"Network error listing {path}: {exc}") from exc
    if r.status_code == 404:
        _cache_set(cache_key, [])
        return []
    try:
        r.raise_for_status()
    except _requests.HTTPError as exc:
        raise ContentUnavailableError(
            f"GitHub returned {r.status_code} listing {path}."
        ) from exc
    data = r.json()
    result = [item["name"] for item in data] if isinstance(data, list) else []
    _cache_set(cache_key, result)
    return result


def _fetch_raw(path: str) -> str | None:
    """Fetch a file from the repo via raw.githubusercontent.com.

    Returns None on 404 (file doesn't exist) so callers can try fallback paths.
    Raises ContentUnavailableError on transient network/HTTP errors (retryable).
    """
    cache_key = f"raw:{path}"
    cached = _cache_get(cache_key)
    if cached is not _MISS:
        return cached

    repo, branch = _github_config()
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    try:
        r = _http.get(url, timeout=15)
    except _requests.RequestException as exc:
        # Connection reset / timeout / DNS — transient and safe to retry.
        raise ContentUnavailableError(f"Network error fetching {path}: {exc}") from exc
    if r.status_code == 404:
        _cache_set(cache_key, None)
        return None
    try:
        r.raise_for_status()
    except _requests.HTTPError as exc:
        raise ContentUnavailableError(
            f"GitHub returned {r.status_code} fetching {path}."
        ) from exc
    _cache_set(cache_key, r.text)
    return r.text


# ── Content parsing ───────────────────────────────────────────────────────────

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
    """Fetch and parse the schedule markdown table from GitHub.

    Resolves the "Verses" and "Date" columns by their header names so the
    parser keeps working if extra columns (e.g. "Studio Verse") are added.
    """
    text = _fetch_raw(_SCHEDULE)
    if text is None:
        raise ContentError(f"Schedule file not found in the GitHub repo: {_SCHEDULE}")

    # Column indices, resolved from the header row when present. Defaults match
    # the historic 3-column layout: Day | Verses | Date.
    verses_idx, date_idx = 1, 2

    schedule: dict[int, dict] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue

        # Header row: map column names to indices.
        lowered = [c.lower() for c in cells]
        if "date" in lowered:
            date_idx = lowered.index("date")
            for label in ("verses", "verse"):
                if label in lowered:
                    verses_idx = lowered.index(label)
                    break
            continue

        if not cells[0].isdigit():
            continue
        if date_idx >= len(cells) or verses_idx >= len(cells):
            continue
        day = int(cells[0])
        schedule[day] = {
            "verses_label": cells[verses_idx],
            "date": cells[date_idx],
            "verses": expand_verses(cells[verses_idx]),
        }
    if not schedule:
        raise ContentError(f"No schedule rows parsed from {_SCHEDULE}.")
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


# ── Day-Package lookup ──────────────────────────────────────────────────────────

def _find_package_path(day: int, verses: list[str]) -> str:
    """Return the GitHub path to a day's Day-Package file (`{day}-en.md`).

    Lists the Day-Packages directory once to find the chapter folder (which may
    carry a suffix like 'Chapter-1 D1-D14'), then returns the `{day}-en.md` path
    inside it. Raises ContentError if the chapter directory is absent; the file's
    own existence is checked by the caller's fetch.
    """
    chapter = int(verses[0].split("-")[0]) if verses else 1

    all_dirs = _list_github_dir(_PACKAGES_DIR)
    chapter_dir = next(
        (d for d in all_dirs if d.startswith(f"Chapter-{chapter}")),
        None,
    )
    if chapter_dir is None:
        raise ContentError(
            f"No Chapter-{chapter} directory found under Day-Packages/ in the repo."
        )

    return f"{_PACKAGES_DIR}/{chapter_dir}/{day}-en.md"


# ── Public API ────────────────────────────────────────────────────────────────

def get_day_content(day: int) -> DayContent:
    """Fetch and parse a day's consolidated Day-Package from GitHub.

    The Day-Package (`{day}-en.md`) is the single source of day content: its
    practice-plan track becomes `plan_markdown`, its Section-2 verses become
    `verses_text`, and each verse's full "rails" become that verse's synthesis
    (so `synthesis_text` carries the complete commentary). A day with no package
    is unavailable — this raises ContentError, which the API surfaces as a 404.
    """
    schedule = get_schedule()
    if day not in schedule:
        raise ContentError(f"Day {day} is not in the schedule (valid range 1–{max(schedule)}).")

    entry = schedule[day]
    plan_path = _find_package_path(day, entry["verses"])
    markdown = _fetch_raw(plan_path)
    if markdown is None:
        raise ContentError(
            f"No Day-Package (`{day}-en.md`) found for Day {day} in the GitHub repo."
        )

    parsed = day_package.parse(markdown)

    # Order verses_text by the schedule's verse ids so views.py's positional
    # pairing of dc.verses ↔ dc.verses_text stays aligned. A verse the package
    # doesn't carry yields "" rather than shifting the rest.
    verse_text = {vid: text for vid, text in parsed.verses}
    rails = {vr.verse_id: vr for vr in parsed.verse_rails}
    verses_text = [verse_text.get(vid, "") for vid in entry["verses"]]
    syntheses = [
        VerseSynthesis(
            verse_id=vid,
            text=(rails[vid].rails_md if vid in rails else ""),
            available=(vid in rails and bool(rails[vid].rails_md)),
        )
        for vid in entry["verses"]
    ]

    # Per-verse selectable resources, mapped to the idea categories they feed:
    # Story ← stories, Concept ← commentaries, Extra-info ← metaphors. Challenge ←
    # the day's "Today's Practice" (day-level, so repeated on each verse).
    def _items(resources) -> list[dict]:
        return [{"label": r.label, "text": r.text} for r in resources]

    practice_items = (
        [{"label": parsed.practice.label, "text": parsed.practice.text}]
        if parsed.practice else []
    )

    verse_resources = {}
    for vid in entry["verses"]:
        vr = rails.get(vid)
        verse_resources[vid] = {
            "story": _items(vr.story_items) if vr else [],
            "concept": _items(vr.commentaries) if vr else [],
            "extra_info": _items(vr.metaphors) if vr else [],
            "practice": list(practice_items),
        }

    return DayContent(
        day=day,
        verses=entry["verses"],
        verses_label=entry["verses_label"],
        date=entry["date"],
        plan_markdown=parsed.challenge_md,
        plan_file=plan_path,
        verse_syntheses=syntheses,
        verses_text=verses_text,
        stories=parsed.stories,
        verse_resources=verse_resources,
        is_variant=False,
    )


def clear_cache() -> None:
    """Drop all cached GitHub responses (e.g. after a content push)."""
    with _cache_lock:
        _cache.clear()
