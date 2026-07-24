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

**Explanation:** Sharing wisdom strengthens your own faith.

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

<!-- sub:metaphors -->
#### Metaphors and Examples

- **A well-filled vase** (བུམ་པ་) → Sugata as "gone completely." Nothing left unattained.
- **A person beautiful to behold** → Sugata as "gone beautifully."

Sources: [[1-SOURCES/Commentaries/KKP.md#^1-1]]

<!-- sub:synthesis -->
#### Verse Synthesis (overview)

This stanza is both homage and pledge.

Sources: [[1-SOURCES/x.md#^1-1]]

<!-- sub:teaching-points -->
#### Main Teaching Points

- Begin with humility, not ego.

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

    def test_practice_resource(self):
        self.assertIsNotNone(self.parsed.practice)
        self.assertEqual(self.parsed.practice.label, "Today's Practice")
        self.assertIn("Share a quote", self.parsed.practice.text)

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

    def test_structured_resources(self):
        first, second = self.parsed.verse_rails
        # Story item: label from the heading (after the dash), body without heading.
        self.assertEqual(len(first.story_items), 1)
        self.assertEqual(first.story_items[0].label,
                         "The Arrogance of the Bodhisattva Daughter")
        self.assertIn("proud daughter", first.story_items[0].text)
        self.assertNotIn("#####", first.story_items[0].text)
        # Commentary: labelled by commentator display name (after the dash).
        self.assertEqual(len(first.commentaries), 1)
        self.assertEqual(first.commentaries[0].label, "Khenpo Kunzang Pelden")
        self.assertIn("three meanings", first.commentaries[0].text)
        # Metaphors: one Resource per bullet, label = leading bold term.
        self.assertEqual([m.label for m in first.metaphors],
                         ["A well-filled vase", "A person beautiful to behold"])
        # Verse with none of these stays empty.
        self.assertEqual(second.story_items, [])
        self.assertEqual(second.commentaries, [])
        self.assertEqual(second.metaphors, [])

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

    def test_teaching_points_subsection(self):
        first, second = self.parsed.verse_rails
        self.assertIn("sub:teaching-points", first.sections)
        self.assertIn("Begin with humility", first.sections["sub:teaching-points"])
        # Verse 1-2 omits the subsection.
        self.assertNotIn("sub:teaching-points", second.sections)


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
        # teaching points: present for 1-1, empty for 1-2 (aligned to verses).
        self.assertEqual(len(dc.teaching_points), 2)
        self.assertIn("Begin with humility", dc.teaching_points[0])
        self.assertEqual(dc.teaching_points[1], "")
        # teaching_points_text joins present ones under a verse header.
        self.assertIn("### Verse 1-1", dc.teaching_points_text)
        self.assertIn("Begin with humility", dc.teaching_points_text)
        # Per-verse selectable resources, mapped to idea categories.
        self.assertEqual(len(dc.verse_resources["1-1"]["story"]), 1)
        self.assertEqual(len(dc.verse_resources["1-1"]["concept"]), 1)
        self.assertEqual(len(dc.verse_resources["1-1"]["extra_info"]), 2)
        self.assertEqual(dc.verse_resources["1-1"]["concept"][0]["label"],
                         "Khenpo Kunzang Pelden")
        # Challenge ← "Today's Practice" (day-level, repeated on every verse), split
        # into the action (text, no "Practice:" prefix) and its explanation.
        practice = dc.verse_resources["1-1"]["practice"][0]
        self.assertEqual(practice["label"], "Today's Practice")
        self.assertEqual(practice["text"], "Share a quote with someone.")
        self.assertNotIn("Practice:", practice["text"])
        self.assertIn("Sharing wisdom", practice["explanation"])
        # Verse 1-2 has no per-verse rails, but still carries the day's practice.
        self.assertEqual(dc.verse_resources["1-2"]["story"], [])
        self.assertEqual(dc.verse_resources["1-2"]["concept"], [])
        self.assertEqual(dc.verse_resources["1-2"]["extra_info"], [])
        self.assertEqual(len(dc.verse_resources["1-2"]["practice"]), 1)

    def test_missing_package_raises(self):
        with mock.patch.object(content_loader, "_list_github_dir",
                               return_value=["Chapter-1 D1-D14"]), \
             mock.patch.object(content_loader, "_fetch_raw",
                               side_effect=self._fake_fetch(None)):
            with self.assertRaises(ContentError):
                get_day_content(1)
