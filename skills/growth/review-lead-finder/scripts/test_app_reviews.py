#!/usr/bin/env python3
"""Offline tests for app_reviews.py: feed parsing, pain flags and pattern files."""

import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app_reviews  # noqa: E402
from app_reviews import flag_reviews, load_pattern, parse_feed  # noqa: E402

PERFORMANCE = Path(__file__).resolve().parent.parent / "presets" / "performance.txt"


def entry(rating, text, date, title="t"):
    return {"im:rating": {"label": str(rating)}, "updated": {"label": f"{date}T10:00:00-07:00"},
            "im:version": {"label": "1.0"}, "title": {"label": title}, "content": {"label": text},
            "id": {"label": "1"}}


class ParseFeedTest(unittest.TestCase):
    def test_handles_list_single_entry_and_app_info_entry(self):
        today = datetime.now(timezone.utc).date().isoformat()
        listed = parse_feed({"feed": {"entry": [{"im:name": {"label": "App"}}, entry(2, "so slow", today)]}})
        self.assertEqual([r["rating"] for r in listed], [2])
        self.assertEqual(len(parse_feed({"feed": {"entry": entry(5, "great", today)}})), 1)
        self.assertEqual(parse_feed({"feed": {}}), [])


class FlagReviewsTest(unittest.TestCase):
    def test_flags_pain_within_date_and_rating_limits(self):
        today = datetime.now(timezone.utc).date()
        old = (today - timedelta(days=400)).isoformat()
        reviews = [parse_feed({"feed": {"entry": e}})[0] for e in (
            entry(1, "It freezes and keeps crashing", today.isoformat()),
            entry(5, "Fast, never laggy", today.isoformat()),   # rating above the cap
            entry(2, "So laggy", old),                            # too old
            entry(3, "Nice design", today.isoformat()),           # no pain words
        )]
        pattern = load_pattern(None, PERFORMANCE)
        flagged = flag_reviews(reviews, pattern, 365, 4)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["matched"], ["freezes", "keeps crashing"])
        self.assertEqual(len(flag_reviews(reviews, pattern, 0, 0)), 3)


class LoadPatternTest(unittest.TestCase):
    def test_file_ignores_comments_and_blank_lines(self):
        path = Path(tempfile.mkdtemp()) / "pain.txt"
        path.write_text("# billing pain\n\n\\bcharged twice\\b\nrefund\n")
        self.assertEqual(load_pattern(None, path), "(?:\\bcharged twice\\b)|(?:refund)")

    def test_inline_pattern_is_used_as_is(self):
        self.assertEqual(load_pattern("x|y", None), "x|y")


class AtomicWriteTest(unittest.TestCase):
    def test_failed_write_keeps_the_previous_file(self):
        path = Path(tempfile.mkdtemp()) / "reviews.json"
        path.write_text("previous")
        with mock.patch.object(app_reviews.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                app_reviews.atomic_write(path, "new")
        self.assertEqual(path.read_text(), "previous")
        self.assertEqual([p.name for p in path.parent.iterdir()], ["reviews.json"])


class PermissionTest(unittest.TestCase):
    def test_replacement_publishes_new_content_everywhere(self):
        path = Path(tempfile.mkdtemp()) / "report.txt"
        path.write_text("old")
        app_reviews.atomic_write(path, "new")
        app_reviews.atomic_write(path.with_name("fresh.txt"), "fresh")
        self.assertEqual(path.read_text(), "new")
        self.assertEqual(path.with_name("fresh.txt").read_text(), "fresh")

    @unittest.skipIf(os.name == "nt", "Windows chmod only sets the read-only flag, not POSIX modes")
    def test_replacement_keeps_existing_permissions_and_new_files_follow_umask(self):
        directory = Path(tempfile.mkdtemp())
        private, fresh = directory / "private.txt", directory / "fresh.txt"
        private.write_text("old")
        os.chmod(private, 0o600)
        previous = os.umask(0o022)
        try:
            app_reviews.atomic_write(private, "new")
            app_reviews.atomic_write(fresh, "new")
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
        self.assertEqual(private.read_text(), "new")
        self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o644)


if __name__ == "__main__":
    unittest.main()
