"""WeBuddhist plan share integration.

Two per-day extras shown after the verse breakdown:

  1. The "today's challenge" shareable image. The public plan API
     (`/plans/<plan-id>/days/<day>`) returns a `shareable_image_url` — a
     *presigned* S3 URL that expires after ~1 hour. Neither that API nor the S3
     bucket sends CORS headers, so the browser can't fetch either directly; we
     proxy both here (fetch the metadata, then stream the image bytes).
  2. The plan share link (`/open/plan/<plan-id>/day/<day>?lang=EN|HI`), built
     purely from config — no network call needed.

The plan id differs by language (see settings.WEBUDDHIST_PLAN_IDS).
Outbound calls reuse the IPv4-pinned session (see `ipv4`) for the same reason
GitHub fetches do — some networks blackhole IPv6 and stall otherwise.
"""

from __future__ import annotations

import logging

import requests as _requests
from django.conf import settings

from . import ipv4

logger = logging.getLogger(__name__)

_http = ipv4.requests_session()

# Language key -> the `?lang=` code the share site expects.
_LANG_CODE = {"english": "EN", "hindi": "HI"}


class PlanShareError(Exception):
    """The requested plan/day/image doesn't exist or isn't configured."""


class PlanShareUnavailable(PlanShareError):
    """The plan API or S3 is transiently unreachable/erroring (safe to retry)."""


def plan_id(language: str) -> str:
    ids = getattr(settings, "WEBUDDHIST_PLAN_IDS", {}) or {}
    pid = ids.get(language) or ids.get("english")
    if not pid:
        raise PlanShareError("No WeBuddhist plan id is configured.")
    return pid


def share_url(day: int, language: str) -> str:
    """Build the public per-day plan link. No network call."""
    base = getattr(settings, "WEBUDDHIST_SHARE_BASE", "https://webuddhist.com").rstrip("/")
    code = _LANG_CODE.get(language, "EN")
    return f"{base}/open/plan/{plan_id(language)}/day/{day}?lang={code}"


def _day_meta(day: int, language: str) -> dict:
    """Fetch the plan-day metadata JSON from the public WeBuddhist API."""
    base = getattr(settings, "WEBUDDHIST_API_BASE", "https://api.webuddhist.com").rstrip("/")
    url = f"{base}/plans/{plan_id(language)}/days/{day}"
    try:
        r = _http.get(url, timeout=15)
    except _requests.RequestException as exc:
        raise PlanShareUnavailable(f"Network error fetching plan day {day}: {exc}") from exc
    if r.status_code == 404:
        raise PlanShareError(f"Plan day {day} not found.")
    try:
        r.raise_for_status()
    except _requests.HTTPError as exc:
        raise PlanShareUnavailable(f"Plan API returned {r.status_code} for day {day}.") from exc
    try:
        return r.json()
    except ValueError as exc:
        raise PlanShareUnavailable("Plan API returned invalid JSON.") from exc


def shareable_image_url(day: int, language: str) -> str | None:
    """Return the presigned S3 image URL for a day, or None if there isn't one."""
    return _day_meta(day, language).get("shareable_image_url") or None


def fetch_image(url: str) -> tuple[bytes, str]:
    """Download the shareable image bytes (and content type) from S3."""
    try:
        r = _http.get(url, timeout=20)
        r.raise_for_status()
    except _requests.RequestException as exc:
        raise PlanShareUnavailable(f"Could not download the share image: {exc}") from exc
    return r.content, r.headers.get("Content-Type", "image/webp")
