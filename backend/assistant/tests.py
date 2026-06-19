from django.test import SimpleTestCase

from assistant.services.content_loader import expand_verses
from assistant.services.script_generator import target_words


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
