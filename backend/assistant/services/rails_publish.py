"""Publish a generated video idea to the rails repo.

Every generated script/structure is pushed to rails as a permanent record of
what the assistant produced — a durable archive the team can browse, track,
and annotate in Obsidian, not just a review queue.

Files land under `3-TRANSFORMATIONS/Creator-assistant-generated-video-idea/
{en,hi}/` — by default in the SAME repo/Obsidian vault `content_loader` reads
source content from, kept under its own folder (a sibling of
`3-TRANSFORMATIONS/Plans/...`, never that path itself) so a push can never
collide with or overwrite an actual day-package path (`content_loader` only
ever lists/reads specific known subpaths, never the repo root, so this folder
is invisible to it either way). Point GITHUB_PUBLISH_REPO at a different repo
instead if the team later wants full separation. Git has no notion of an empty
folder — the `en`/`hi` folders come into existence automatically the first
time something is saved into them, no separate setup step needed. A push is
keyed by (day, idea, focus, duration, language): publishing the same piece
again (e.g. after a chat-refine) updates that same file in place, so git's own
commit history becomes the version trail instead of the folder filling up with
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

# Folder generated ideas are published under — a sibling of 3-TRANSFORMATIONS/Plans/,
# never touches the actual day-package paths content_loader reads from.
_PUBLISH_ROOT = "3-TRANSFORMATIONS/Creator-assistant-generated-video-idea"

# Everything below this heading is human-written and survives re-saves.
_FEEDBACK_HEADING = "## Feedback"


class PublishNotConfigured(Exception):
    """Raised when GITHUB_PUBLISH_TOKEN/GITHUB_PUBLISH_REPO aren't set."""


class PublishError(Exception):
    """Raised when the GitHub write itself fails."""


def is_configured() -> bool:
    return bool(settings.GITHUB_PUBLISH_TOKEN and settings.GITHUB_PUBLISH_REPO)


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
    return f"{_PUBLISH_ROOT}/{lang_code}/Day-{day:03d}/{idea_key}-{ident}-{duration_seconds}s.md"


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
        "status: draft",
        "---",
    ]

    markdown = "\n".join(fm) + f"\n\n# {title}\n\n{body}\n\n{_FEEDBACK_HEADING}\n"
    return markdown, title


def _carry_over_feedback(new_markdown: str, existing_markdown: str) -> str:
    """Preserve whatever reviewers wrote under `## Feedback` in the old file.

    Every save rewrites the whole file, so without this a re-save (and with
    auto-publish, every single regenerate) would silently wipe a reviewer's
    notes. The generated part above the heading is always replaced; everything
    from the heading down is human-owned and carried across verbatim.
    """
    idx = existing_markdown.find(_FEEDBACK_HEADING)
    if idx == -1:
        return new_markdown
    kept = existing_markdown[idx + len(_FEEDBACK_HEADING):].strip()
    if not kept:
        return new_markdown
    return new_markdown.rstrip("\n") + f"\n\n{kept}\n"


def publish(
    *, day: int, verses_label: str, idea_key: str, focus_label: str,
    duration_seconds: int, language: str, output_type: str, content,
) -> dict:
    """Create or update this piece's file in rails. Returns {url, path}."""
    if not is_configured():
        raise PublishNotConfigured(
            "GITHUB_PUBLISH_TOKEN and GITHUB_PUBLISH_REPO must both be set to publish to rails."
        )

    markdown, title = _build_markdown(
        day=day, verses_label=verses_label, idea_key=idea_key, focus_label=focus_label,
        duration_seconds=duration_seconds, language=language, output_type=output_type,
        content=content,
    )
    path = _path_for(day, idea_key, focus_label, duration_seconds, language)
    repo = settings.GITHUB_PUBLISH_REPO
    branch = settings.GITHUB_PUBLISH_BRANCH
    base = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_PUBLISH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Look up the existing file's blob sha (if any) so we update it in place
    # rather than creating a sibling — GitHub requires the current sha to
    # overwrite an existing path. The same response carries the current
    # contents, which is where any reviewer feedback lives.
    get_resp = _http.get(base, headers=headers, params={"ref": branch}, timeout=15)
    sha = None
    if get_resp.status_code == 200:
        existing = get_resp.json()
        sha = existing.get("sha")
        if existing.get("encoding") == "base64" and existing.get("content"):
            try:
                previous = base64.b64decode(existing["content"]).decode("utf-8")
                markdown = _carry_over_feedback(markdown, previous)
            except (ValueError, UnicodeDecodeError):
                # Unreadable previous file — publish the fresh copy rather than
                # failing the save outright.
                pass

    payload = {
        "message": f"{'Update' if sha else 'Add'} {title} (creator assistant)",
        "content": base64.b64encode(markdown.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_resp = _http.put(base, headers=headers, json=payload, timeout=20)
    if put_resp.status_code not in (200, 201):
        raise PublishError(
            f"GitHub write failed ({put_resp.status_code}): {put_resp.text[:300]}"
        )

    html_url = (put_resp.json().get("content") or {}).get("html_url", "")
    return {"url": html_url, "path": path}
