"""Publish a generated video idea to the team's GitHub review vault.

The review vault is a separate repo (an Obsidian vault) the team browses,
annotates, and comments on directly — distinct from the read-only source
content repo `content_loader` pulls from. A save is keyed by
(day, idea, focus, duration, language): saving the same piece again (e.g.
after a chat-refine) updates that same file in place, so git's own commit
history becomes the version trail instead of the vault filling up with
near-duplicate files.
"""

from __future__ import annotations

import base64
import re
from datetime import date

from django.conf import settings

from . import ipv4
from .ideas import idea_label

_http = ipv4.requests_session()


class ReviewNotConfigured(Exception):
    """Raised when GITHUB_REVIEW_TOKEN/GITHUB_REVIEW_REPO aren't set."""


class ReviewPublishError(Exception):
    """Raised when the GitHub write itself fails."""


def is_configured() -> bool:
    return bool(settings.GITHUB_REVIEW_TOKEN and settings.GITHUB_REVIEW_REPO)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s or "untitled"


def _yaml_str(value: str) -> str:
    """Double-quoted YAML scalar with internal quotes escaped."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _path_for(day: int, idea_key: str, focus_label: str, duration_seconds: int, language: str) -> str:
    ident = _slug(focus_label) if focus_label else "general"
    lang_code = "hi" if language == "hindi" else "en"
    return f"Day-{day:03d}/{idea_key}-{ident}-{duration_seconds}s-{lang_code}.md"


def _structure_to_markdown(structure: dict) -> str:
    """Render all matched versions of a storyboard, clearly labeled.

    Saves every version (not just whichever the creator had on screen) since
    a reviewer benefits from seeing the alternatives that were generated.
    """
    lines = [
        f"**Core theme:** {structure.get('coreTheme', '')}",
        "",
        f'**Concept:** "{structure.get("concept", "")}"',
        "",
    ]
    sections = structure.get("sections") or []
    version_count = max((len(s.get("options") or []) for s in sections), default=1) or 1
    for v in range(version_count):
        lines.append(f"## Version {v + 1}")
        for sec in sections:
            opts = sec.get("options") or []
            opt = opts[min(v, len(opts) - 1)] if opts else {}
            lines.append(f"### {sec.get('label', '')} ({sec.get('timeRange', '')})")
            lines.append("**On screen**")
            for visual in (opt.get("visuals") or []):
                lines.append(f"- {visual}")
            lines.append("")
            lines.append("**Voiceover**")
            lines.append(opt.get("voiceover", ""))
            lines.append("")
    return "\n".join(lines)


def _build_markdown(
    *, day: int, verses_label: str, idea_key: str, focus_label: str,
    duration_seconds: int, language: str, output_type: str, content,
) -> tuple[str, str]:
    label = idea_label(idea_key, language)
    title_bits = [f"Day {day}", label]
    if focus_label:
        title_bits.append(focus_label)
    title = " — ".join(title_bits)

    body = _structure_to_markdown(content) if output_type == "structure" else (content or "").strip()

    fm = [
        "---",
        f"day: {day}",
        f"verses: {_yaml_str(verses_label)}",
        f"idea: {idea_key}",
        f"ideaLabel: {_yaml_str(label)}",
    ]
    if focus_label:
        fm.append(f"focus: {_yaml_str(focus_label)}")
    fm += [
        f"outputType: {output_type}",
        f"durationSeconds: {duration_seconds}",
        f"language: {language}",
        f"generatedAt: {date.today().isoformat()}",
        "status: needs-review",
        "---",
    ]

    markdown = "\n".join(fm) + f"\n\n# {title}\n\n{body}\n\n## Feedback\n"
    return markdown, title


def publish(
    *, day: int, verses_label: str, idea_key: str, focus_label: str,
    duration_seconds: int, language: str, output_type: str, content,
) -> dict:
    """Create or update the review file for this piece. Returns {url, path}."""
    if not is_configured():
        raise ReviewNotConfigured(
            "GITHUB_REVIEW_TOKEN and GITHUB_REVIEW_REPO must both be set to save for review."
        )

    markdown, title = _build_markdown(
        day=day, verses_label=verses_label, idea_key=idea_key, focus_label=focus_label,
        duration_seconds=duration_seconds, language=language, output_type=output_type,
        content=content,
    )
    path = _path_for(day, idea_key, focus_label, duration_seconds, language)
    repo = settings.GITHUB_REVIEW_REPO
    branch = settings.GITHUB_REVIEW_BRANCH
    base = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_REVIEW_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Look up the existing file's blob sha (if any) so we update it in place
    # rather than creating a sibling — GitHub requires the current sha to
    # overwrite an existing path.
    get_resp = _http.get(base, headers=headers, params={"ref": branch}, timeout=15)
    sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

    payload = {
        "message": f"{'Update' if sha else 'Save'} {title} (review)",
        "content": base64.b64encode(markdown.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_resp = _http.put(base, headers=headers, json=payload, timeout=20)
    if put_resp.status_code not in (200, 201):
        raise ReviewPublishError(
            f"GitHub write failed ({put_resp.status_code}): {put_resp.text[:300]}"
        )

    html_url = (put_resp.json().get("content") or {}).get("html_url", "")
    return {"url": html_url, "path": path}
