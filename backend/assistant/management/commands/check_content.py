"""Smoke-test the content loader against the local rails repo.

Usage: python manage.py check_content [--day N]
"""

from django.core.management.base import BaseCommand

from assistant.services import content_loader as cl


class Command(BaseCommand):
    help = "Verify schedule parsing and day-content loading from the rails repo."

    def add_arguments(self, parser):
        parser.add_argument("--day", type=int, default=None, help="Inspect a single day in detail.")

    def handle(self, *args, **opts):
        # 1. Pure parser checks (no repo needed).
        cases = {
            "1.12–1.14": ["1-12", "1-13", "1-14"],
            "Prologue, 1.1–1.3": ["1-1", "1-2", "1-3"],
            "1.4–1.5": ["1-4", "1-5"],
            "2.1–2.3": ["2-1", "2-2", "2-3"],
        }
        self.stdout.write(self.style.MIGRATE_HEADING("expand_verses():"))
        ok = True
        for label, expected in cases.items():
            got = cl.expand_verses(label)
            mark = "✓" if got == expected else "✗"
            if got != expected:
                ok = False
            self.stdout.write(f"  {mark} {label!r:24} -> {got}")
        if not ok:
            self.stderr.write(self.style.ERROR("expand_verses mismatch!"))
            return

        # 2. Schedule + day loading (needs RAILS_REPO_PATH).
        schedule = cl.get_schedule()
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nschedule: {len(schedule)} days parsed"))
        for d in (1, 5, 15):
            if d in schedule:
                self.stdout.write(f"  Day {d}: {schedule[d]['verses_label']!r} -> {schedule[d]['verses']}  ({schedule[d]['date']})")

        days_to_check = [opts["day"]] if opts["day"] else [1, 5, 15]
        for d in days_to_check:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\nload_day_content({d}):"))
            dc = cl.get_day_content(d)
            self.stdout.write(f"  verses     : {dc.verses}")
            self.stdout.write(f"  date       : {dc.date}")
            self.stdout.write(f"  plan_file  : {dc.plan_file}  (variant={dc.is_variant})")
            self.stdout.write(f"  plan chars : {len(dc.plan_markdown)}")
            avail = [vs.verse_id for vs in dc.verse_syntheses if vs.available]
            missing = [vs.verse_id for vs in dc.verse_syntheses if not vs.available]
            self.stdout.write(f"  synthesis  : {len(avail)} available {avail}, {len(missing)} missing {missing}")

        self.stdout.write(self.style.SUCCESS("\nContent loader OK."))
