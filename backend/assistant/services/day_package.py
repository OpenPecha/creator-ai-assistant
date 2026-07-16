"""Parse a Day-Package (`{day}-en.md`) into structured content.

A Day-Package is the source-of-truth English file for one day of the plan. It has
three anchored sections:

    <!-- sec:challenge -->  the practice-plan track (notification / opening /
                            "from the tradition" / today's practice)
    <!-- sec:verses -->     today's verses in plain English (**Verse X-Y** + a
                            blockquote of the translation)
    <!-- sec:rails -->      per-verse "rails": one <!-- verse:X-Y --> block each,
                            holding <!-- sub:* --> subsections — root verse,
                            interlinear gloss, commentaries (<!-- cm:* -->), stories
                            (<!-- story:* -->), metaphors, scriptural quotations,
                            teaching points, key terms, and a synthesis overview.

The HTML-comment anchors — not the heading text — are the contract, so this parser
keeps working if a heading is reworded. Optional subsections simply don't appear for
verses that lack them. This module is pure (no network); `content_loader` fetches the
markdown and calls `parse()`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# `<!-- sec:verses -->`, `<!-- verse:1-1 -->`, `<!-- sub:stories -->`, `<!-- cm:kunpal -->`
_ANCHOR_RE = re.compile(r"<!--\s*([\w:-]+)\s*-->")
_FRONTMATTER_RE = re.compile(r"\A﻿?---\n.*?\n---\n", re.DOTALL)
_VERSE_MARKER_RE = re.compile(r"^\*\*Verse\s+([\w.-]+)\*\*\s*$", re.MULTILINE)
# Obsidian links: `[[path#^1-1]]`, `![[embed]]`, and any wrapping `( … )`.
_LINK_RE = re.compile(r"\(?\s*!?\[\[[^\]]*\]\]\s*\)?")
_SOURCE_NOTE_RE = re.compile(r"^\*?\(Source:.*\)\*?$")


@dataclass
class VerseRail:
    verse_id: str
    rails_md: str  # full cleaned rails for this verse (all subsections)
    stories: list[str] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)  # sub-anchor -> cleaned text


@dataclass
class ParsedPackage:
    status: str
    challenge_md: str
    verses: list[tuple[str, str]]  # (verse_id, plain-English text) from Section 2
    verse_rails: list[VerseRail]

    @property
    def stories(self) -> list[str]:
        """All stories across every verse, in document order."""
        out: list[str] = []
        for vr in self.verse_rails:
            out.extend(vr.stories)
        return out


# ── Cleaning ──────────────────────────────────────────────────────────────────

def _strip_frontmatter(md: str) -> tuple[str, str]:
    """Return (status, body). `status` comes from the frontmatter if present."""
    status = ""
    m = _FRONTMATTER_RE.match(md)
    if m:
        sm = re.search(r"(?m)^status:\s*(.+?)\s*$", m.group(0))
        if sm:
            status = sm.group(1).strip().strip('"').strip("'")
        md = md[m.end():]
    return status, md


def _clean(text: str) -> str:
    """Strip anchors, citation lines, and Obsidian link syntax for prompt use."""
    text = _ANCHOR_RE.sub("", text)
    text = _LINK_RE.sub("", text)
    kept: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("Sources:"):
            continue
        if s.startswith("**Rail source:**") or "**Rail source:**" in s:
            continue
        if _SOURCE_NOTE_RE.match(s):
            continue
        kept.append(line)
    text = "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Segmentation ────────────────────────────────────────────────────────────────

def _segments(body: str) -> list[tuple[str, str]]:
    """Split `body` into ordered (anchor_name, text_until_next_anchor) pairs.

    Text before the first anchor is returned under the "" key. The anchor markers
    themselves are dropped; heading lines that follow them are kept in the text.
    """
    matches = list(_ANCHOR_RE.finditer(body))
    if not matches:
        return [("", body)]
    segs: list[tuple[str, str]] = []
    if matches[0].start() > 0:
        segs.append(("", body[: matches[0].start()]))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        segs.append((m.group(1), body[start:end]))
    return segs


# ── Section parsers ─────────────────────────────────────────────────────────────

def _parse_verses(raw: str) -> list[tuple[str, str]]:
    """Extract (verse_id, text) from the Section 2 body's `**Verse X-Y**` blocks."""
    raw = _ANCHOR_RE.sub("", raw)
    verses: list[tuple[str, str]] = []
    matches = list(_VERSE_MARKER_RE.finditer(raw))
    for i, m in enumerate(matches):
        vid = m.group(1).replace(".", "-")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        lines = []
        for line in raw[start:end].splitlines():
            s = line.strip()
            if s.startswith(">"):
                t = s.lstrip(">").strip()
                if t:
                    lines.append(t)
        text = "\n".join(lines).strip()
        if text:
            verses.append((vid, text))
    return verses


def _parse_rails(rails_segs: list[tuple[str, str]]) -> list[VerseRail]:
    """Group Section 3 segments into one VerseRail per `<!-- verse:X-Y -->` block."""
    rails: list[VerseRail] = []
    cur: dict | None = None
    cur_sub: str | None = None

    def finish(state: dict) -> VerseRail:
        sections = {k: _clean("\n".join(v)) for k, v in state["sections"].items()}
        return VerseRail(
            verse_id=state["id"],
            rails_md=_clean("\n".join(state["raw"])),
            stories=state["stories"],
            sections=sections,
        )

    for name, text in rails_segs:
        if name == "sec:rails":
            continue
        if name.startswith("verse:"):
            if cur is not None:
                rails.append(finish(cur))
            cur = {"id": name.split(":", 1)[1].replace(".", "-"),
                   "raw": [], "stories": [], "sections": {}}
            cur_sub = None
            continue
        if cur is None:
            continue
        cur["raw"].append(text)
        if name.startswith("sub:"):
            cur_sub = name
            cur["sections"].setdefault(cur_sub, []).append(text)
        elif name.startswith("story:"):
            cur["stories"].append(_clean(text))
            if cur_sub:
                cur["sections"].setdefault(cur_sub, []).append(text)
        elif cur_sub:  # cm:* and any other nested anchors
            cur["sections"].setdefault(cur_sub, []).append(text)

    if cur is not None:
        rails.append(finish(cur))
    return rails


# ── Public API ──────────────────────────────────────────────────────────────────

def parse(markdown: str) -> ParsedPackage:
    """Parse a Day-Package markdown string into a structured ParsedPackage."""
    status, body = _strip_frontmatter(markdown)
    segs = _segments(body)

    challenge_parts: list[str] = []
    verses_raw = ""
    rails_segs: list[tuple[str, str]] = []
    section: str | None = None

    for name, text in segs:
        if name.startswith("sec:"):
            section = name
            if name == "sec:challenge":
                challenge_parts.append(text)
            elif name == "sec:verses":
                verses_raw = text
            elif name == "sec:rails":
                rails_segs.append((name, text))
            continue
        if section == "sec:challenge":
            challenge_parts.append(text)
        elif section == "sec:verses":
            verses_raw += "\n" + text
        elif section == "sec:rails":
            rails_segs.append((name, text))

    return ParsedPackage(
        status=status,
        challenge_md=_clean("\n".join(challenge_parts)),
        verses=_parse_verses(verses_raw),
        verse_rails=_parse_rails(rails_segs),
    )
