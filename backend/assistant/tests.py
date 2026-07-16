from unittest import mock

from django.test import SimpleTestCase

from assistant.services import content_loader, day_package
from assistant.services.content_loader import ContentError, expand_verses, get_day_content
from assistant.services.script_generator import target_words


# A compact but structurally complete Day-Package, exercising: frontmatter status,
# all three sections, a verse with a story and one without, Sources: lines, Obsidian
# [[…]] links, a *(Source: …)* note, and a **Rail source:** metadata line.
_PACKAGE_MD = """---
day: 1
chapter: 1
verses: "1-1 to 1-2"
status: draft
---

# Day 1 — Test title

**Date:** Jul 6, 2026

---

<!-- sec:challenge -->
## 1. Today's Challenge

<!-- challenge:opening -->
### Opening

Open quietly.

<!-- challenge:practice -->
### Today's Practice

**Practice:** Share a quote with someone.

*(Source: `Days/Chapter-1/1.md`)*

---

<!-- sec:verses -->
## 2. Today's Verses

Intro paragraph. Source: BCA-Full-Plain-English.md.

**Verse 1-1**

> I bow to the buddhas
> and to their heirs.

**Verse 1-2**

> Nothing here is new.

---

<!-- sec:rails -->
## 3. Verse Rails

Intro to the rails.

<!-- verse:1-1 -->
### Verse 1-1

> **Rail source:** `1-1-summary.md` &nbsp;|&nbsp; **Rail status:** `draft`

<!-- sub:root-verse -->
#### Root Verse

> I bow to the buddhas.

Sources: [[1-SOURCES/Text/x.md#^1-1]]

<!-- sub:commentary -->
#### Commentary Explanations

<!-- cm:kunpal -->
##### kunpal — Khenpo Kunzang Pelden

Sugata has three meanings.

Sources: [[1-SOURCES/Commentaries/KKP.md#^1-1]]

<!-- sub:stories -->
#### Stories and Illustrations

<!-- story:BCAC13 -->
##### BCAC13 — The Arrogance of the Bodhisattva Daughter

Long ago a proud daughter would not bow to the arhats, then relented.

Sources: [[1-SOURCES/Commentaries/KTB.md#^1-1]]

<!-- sub:synthesis -->
#### Verse Synthesis (overview)

This stanza is both homage and pledge.

Sources: [[1-SOURCES/x.md#^1-1]]

---

<!-- verse:1-2 -->
### Verse 1-2

> **Rail source:** `1-2-summary.md` &nbsp;|&nbsp; **Rail status:** `draft`

<!-- sub:root-verse -->
#### Root Verse

> Nothing here is new.

<!-- sub:synthesis -->
#### Verse Synthesis (overview)

Humbling pride.

Sources: [[1-SOURCES/y.md#^1-2]]

---
"""

_SCHEDULE_MD = """| Day | Verses | Date |
|---|---|---|
| 1 | 1.1–1.2 | Jul 6, 2026 |
"""


class ExpandVersesTests(SimpleTestCase):
    def test_simple_range(self):
        self.assertEqual(expand_verses("1.12–1.14"), ["1-12", "1-13", "1-14"])

    def test_prologue_prefix_ignored(self):
        self.assertEqual(expand_verses("Prologue, 1.1–1.3"), ["1-1", "1-2", "1-3"])

    def test_two_verse_range(self):
        self.assertEqual(expand_verses("1.4–1.5"), ["1-4", "1-5"])

    def test_chapter_two(self):
        self.assertEqual(expand_verses("2.1–2.3"), ["2-1", "2-2", "2-3"])

    def test_ascii_hyphen_range(self):
        self.assertEqual(expand_verses("6.1-6.2"), ["6-1", "6-2"])

    def test_single_verse(self):
        self.assertEqual(expand_verses("3.7"), ["3-7"])

    def test_no_duplicates(self):
        # A single verse that also appears in a range should not duplicate.
        self.assertEqual(expand_verses("1.1, 1.1–1.2"), ["1-1", "1-2"])


class TargetWordsTests(SimpleTestCase):
    def test_scaling(self):
        self.assertEqual(target_words(60), 150)
        self.assertEqual(target_words(30), 75)

    def test_floor(self):
        self.assertGreaterEqual(target_words(1), 20)


class DayPackageParseTests(SimpleTestCase):
    def setUp(self):
        self.parsed = day_package.parse(_PACKAGE_MD)

    def test_status_from_frontmatter(self):
        self.assertEqual(self.parsed.status, "draft")

    def test_challenge_section(self):
        self.assertIn("Share a quote with someone", self.parsed.challenge_md)
        # The H1 title/date block above sec:challenge is excluded.
        self.assertNotIn("Test title", self.parsed.challenge_md)
        # The *(Source: …)* note is stripped.
        self.assertNotIn("(Source:", self.parsed.challenge_md)

    def test_verses_from_section_two(self):
        self.assertEqual(
            self.parsed.verses,
            [
                ("1-1", "I bow to the buddhas\nand to their heirs."),
                ("1-2", "Nothing here is new."),
            ],
        )

    def test_rails_and_stories(self):
        self.assertEqual(len(self.parsed.verse_rails), 2)
        first, second = self.parsed.verse_rails
        self.assertEqual(len(first.stories), 1)
        self.assertIn("Bodhisattva Daughter", first.stories[0])
        self.assertEqual(second.stories, [])
        # Aggregate helper flattens across verses.
        self.assertEqual(len(self.parsed.stories), 1)

    def test_rails_cleaned(self):
        for vr in self.parsed.verse_rails:
            self.assertNotIn("[[", vr.rails_md)
            self.assertNotIn("Sources:", vr.rails_md)
            self.assertNotIn("<!--", vr.rails_md)
            self.assertNotIn("**Rail source:**", vr.rails_md)
        # Commentary content survives the cleaning.
        self.assertIn("Sugata has three meanings", self.parsed.verse_rails[0].rails_md)

    def test_optional_subsection_absent(self):
        # Verse 1-2 has no stories/commentary/metaphors subsections.
        self.assertNotIn("sub:stories", self.parsed.verse_rails[1].sections)


class GetDayContentTests(SimpleTestCase):
    def _fake_fetch(self, package_md):
        pkg_path = f"{content_loader._PACKAGES_DIR}/Chapter-1 D1-D14/1-en.md"

        def fetch(path):
            if path == content_loader._SCHEDULE:
                return _SCHEDULE_MD
            if path == pkg_path:
                return package_md
            return None

        return fetch

    def test_populates_day_content_from_package(self):
        with mock.patch.object(content_loader, "_list_github_dir",
                               return_value=["Chapter-1 D1-D14"]), \
             mock.patch.object(content_loader, "_fetch_raw",
                               side_effect=self._fake_fetch(_PACKAGE_MD)):
            dc = get_day_content(1)

        self.assertEqual(dc.verses, ["1-1", "1-2"])
        self.assertEqual(dc.verses_label, "1.1–1.2")
        self.assertEqual(dc.date, "Jul 6, 2026")
        # plan_markdown = the challenge track (Section 1).
        self.assertIn("Share a quote with someone", dc.plan_markdown)
        # verse_block = Section 2 plain-English verses, ordered by schedule ids.
        self.assertIn("I bow to the buddhas", dc.verse_block)
        self.assertIn("Nothing here is new", dc.verse_block)
        # synthesis_text = full rails (commentary + story present).
        self.assertIn("Sugata has three meanings", dc.synthesis_text)
        self.assertIn("Bodhisattva Daughter", dc.synthesis_text)
        # stories surfaced for idea analysis.
        self.assertEqual(len(dc.stories), 1)

    def test_missing_package_raises(self):
        with mock.patch.object(content_loader, "_list_github_dir",
                               return_value=["Chapter-1 D1-D14"]), \
             mock.patch.object(content_loader, "_fetch_raw",
                               side_effect=self._fake_fetch(None)):
            with self.assertRaises(ContentError):
                get_day_content(1)
