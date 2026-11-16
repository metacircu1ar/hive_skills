#!/usr/bin/env python3
"""Tests for terms.py: export parsing, aggregation, flags and decision validation."""

import csv
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TERMS = Path(__file__).resolve().parent / "terms.py"
sys.path.insert(0, str(TERMS.parent))

import terms  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, str(TERMS), *map(str, args)], capture_output=True, text=True)


class TermsTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.export = self.dir / "export.csv"
        rows = [
            ["Search Terms Report", "", "", "", "", "", ""],
            ["Search Term", "Campaign Name", "Ad Group Name", "Impressions", "Taps", "Installs", "Spend"],
            ["gym workout planner", "Discovery", "Search Match", "1,200", "40", "6", "$12.60"],
            ["gym workout planner", "Discovery", "Search Match", "300", "10", "1", "$3.40"],
            ["planet fitness", "Discovery", "Search Match", "900", "20", "0", "$9.00"],
            ["acmefit", "Brand", "Exact", "50", "10", "4", "$2.00"],
            ["Total", "", "", "2450", "80", "11", "$27.00"],
        ]
        with open(self.export, "w", newline="") as handle:
            csv.writer(handle).writerows(rows)
        self.summary = self.dir / "terms.json"
        result = run("summarize", "--export", self.export, "--out", self.summary, "--target-cpa", "1", "--min-spend", "5")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.data = json.loads(self.summary.read_text())

    def decide(self, decisions):
        path = self.dir / "decisions.json"
        path.write_text(json.dumps({"decisions": decisions}))
        return run("write", "--terms", self.summary, "--decisions", path, "--out", self.dir / "out", "--protect", "acmefit,acme fit")

    def test_summarize_skips_title_and_total_rows_and_sums_days(self):
        by_term = {row["term"]: row for row in self.data["rows"]}
        self.assertEqual(self.data["term_count"], 3)
        planner = by_term["gym workout planner"]
        self.assertEqual((planner["taps"], planner["installs"], planner["spend"]), (50, 7, 16.0))
        self.assertEqual(planner["cpa"], 2.29)
        self.assertIn("expensive", planner["flags"])
        self.assertIn("spend_without_installs", by_term["planet fitness"]["flags"])
        self.assertEqual(self.data["totals"]["spend"], 27.0)

    def test_missing_columns_are_reported_with_the_headers_found(self):
        bad = self.dir / "bad.csv"
        bad.write_text("Keyword,Clicks\nfoo,1\n")
        result = run("summarize", "--export", bad, "--out", self.dir / "x.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("headers found: Keyword, Clicks", result.stderr)

    def test_write_rejects_negating_a_protected_term(self):
        result = self.decide([{"term": "acmefit", "campaign": "Brand", "ad_group": "Exact", "bucket": "core",
                               "action": "negative_exact", "bid": "hold", "reason": "test"}])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected", result.stderr)

    def test_write_produces_csvs_and_report(self):
        result = self.decide([
            {"term": "planet fitness", "campaign": "Discovery", "ad_group": "Search Match", "bucket": "adjacent",
             "action": "negative_exact", "bid": "hold", "reason": "A gym chain, not this kind of app"},
            {"term": "gym workout planner", "campaign": "Discovery", "ad_group": "Search Match", "bucket": "core",
             "action": "promote_exact", "bid": "hold", "reason": "Exactly what the app does"},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        out = self.dir / "out"
        with open(out / "negatives.csv", newline="") as handle:
            negatives = list(csv.reader(handle))
        self.assertEqual(negatives[1][:2], ["planet fitness", "Exact"])
        report = (out / "report.md").read_text()
        self.assertIn("Spend on them in this period: 9.0", report)
        self.assertIn("Undecided (1)", report)


def write_rows(path, rows, delimiter=","):
    with open(path, "w", newline="") as handle:
        csv.writer(handle, delimiter=delimiter).writerows(rows)


class ExportFormatTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def summarize(self, rows, *extra, delimiter=","):
        export, out = self.dir / "export.csv", self.dir / "terms.json"
        write_rows(export, rows, delimiter)
        result = run("summarize", "--export", export, "--out", out, *extra)
        return result, (json.loads(out.read_text()) if result.returncode == 0 else None)

    def test_unpadded_title_and_metadata_lines_are_skipped(self):
        result, data = self.summarize([
            ["Search Terms Report"],
            ["Date range: 2026-11-01 to 2026-11-07"],
            [],
            ["Search Term", "Taps", "Installs", "Spend"],
            ["workout planner", "4", "1", "3.20"],
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["rows"][0]["spend"], 3.2)

    def test_missing_installs_column_is_rejected(self):
        result, _ = self.summarize([["Search Term", "Taps", "Spend"], ["workout planner", "4", "3.20"]])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing installs", result.stderr)

    def test_missing_impressions_stay_unknown(self):
        result, data = self.summarize([["Search Term", "Taps", "Installs", "Spend"], ["workout planner", "4", "1", "3.20"]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(data["rows"][0]["impressions"])
        self.assertIsNone(data["rows"][0]["ttr"])

    def test_decimal_comma_is_rejected_unless_declared(self):
        rows = [["Search Term", "Taps", "Installs", "Spend"], ["workout planner", "4", "1", "12,50"]]
        result, _ = self.summarize(rows)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--decimal-comma", result.stderr)
        self.assertIn("line 2", result.stderr)
        result, data = self.summarize(rows, "--decimal-comma", delimiter=";")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["rows"][0]["spend"], 12.5)

    def test_thousands_separators_and_currency_symbols(self):
        cases = {"$1,234.50": 1234.5, "1234.5": 1234.5, "USD 7": 7.0, "7 EUR": 7.0, "-$5.00": -5.0,
                 "": None, "--": None, "n/a": None}
        for text, expected in cases.items():
            self.assertEqual(terms.number(text, False, "x"), expected, text)
        self.assertEqual(terms.number("€1.234,50", True, "x"), 1234.5)
        for bad in ("12,50", "1,23,456", "abc", "1.2.3", "1e3", "12abc34", "<5", ">1,000", "$$5", "5 USDX"):
            with self.assertRaises(ValueError, msg=bad):
                terms.number(bad, False, "x")


    def test_truncated_row_is_rejected_and_output_untouched(self):
        out = self.dir / "terms.json"
        out.write_text("previous")
        export = self.dir / "export.csv"
        write_rows(export, [["Search Term", "Spend", "Taps", "Installs"], ["foo", "25", "10"]])
        result = run("summarize", "--export", export, "--out", out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("line 2: 3 fields, but the header has 4", result.stderr)
        self.assertEqual(out.read_text(), "previous")

    def test_empty_required_metric_is_rejected_but_missing_impressions_are_unknown(self):
        result, _ = self.summarize([["Search Term", "Spend", "Taps", "Installs"], ["foo", "25", "10", "n/a"]])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no value", result.stderr)
        result, data = self.summarize([["Search Term", "Impressions", "Spend", "Taps", "Installs"],
                                       ["foo", "", "25", "10", "0"], ["foo", "40", "5", "2", "1"]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(data["rows"][0]["impressions"])
        self.assertEqual(data["rows"][0]["installs"], 1)


    def test_counts_must_be_whole_numbers_of_at_least_zero(self):
        header = ["Search Term", "Impressions", "Spend", "Taps", "Installs"]
        for bad_row in (["foo", "40", "10", "4", "0.5"], ["foo", "40", "10", "-1", "1"], ["foo", "2.5", "10", "4", "1"]):
            result, _ = self.summarize([header, bad_row])
            self.assertNotEqual(result.returncode, 0, bad_row)
            self.assertIn("whole number", result.stderr)
        result, data = self.summarize([header, ["foo", "40.0", "10", "4", "0"], ["bar", "1,000", "3", "2.0", "2.0"]])
        self.assertEqual(result.returncode, 0, result.stderr)
        by_term = {row["term"]: row for row in data["rows"]}
        self.assertEqual((by_term["foo"]["installs"], by_term["bar"]["installs"], by_term["bar"]["impressions"]), (0, 2, 1000))
        self.assertIn("spend_without_installs", by_term["foo"]["flags"])

    def test_unterminated_quote_is_rejected_and_quoted_newlines_still_work(self):
        out, export = self.dir / "terms.json", self.dir / "export.csv"
        out.write_text("previous")
        export.write_text('Search Term,Spend,Taps,Installs\n"foo,10,4,1\nbar,2,1,0\n')
        result = run("summarize", "--export", export, "--out", out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed CSV", result.stderr)
        self.assertEqual(out.read_text(), "previous")
        export.write_text('Search Term,Spend,Taps,Installs\n"two\nlines",10,4,1\n')
        result = run("summarize", "--export", export, "--out", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(out.read_text())["rows"][0]["term"], "two\nlines")


class ProtectedTermsTest(unittest.TestCase):
    protected = ["acme fitness", "acmefit"]

    def blocked(self, term, action):
        return terms.blocked_protected(term, action, self.protected)

    def test_broad_negative_made_of_protected_words_is_refused(self):
        self.assertEqual(self.blocked("fitness", "negative_broad"), "acme fitness")
        self.assertEqual(self.blocked("fitness acme", "negative_broad"), "acme fitness")

    def test_negative_that_is_a_protected_search_is_refused(self):
        self.assertEqual(self.blocked("acmefit", "negative_exact"), "acmefit")
        self.assertEqual(self.blocked("fitness acme", "negative_exact"), "acme fitness")
        self.assertEqual(self.blocked("acmefit login", "negative_broad"), "acmefit")

    def test_unrelated_and_exact_subset_negatives_are_allowed(self):
        self.assertIsNone(self.blocked("yoga mat", "negative_broad"))
        self.assertIsNone(self.blocked("fitness", "negative_exact"))  # blocks only the search "fitness"


class DecisionIntegrityTest(unittest.TestCase):
    setUp = TermsTest.setUp
    decide = TermsTest.decide

    def test_metric_fields_in_a_decision_are_rejected(self):
        result = self.decide([{"term": "planet fitness", "campaign": "Discovery", "ad_group": "Search Match",
                               "bucket": "adjacent", "action": "negative_exact", "bid": "hold",
                               "reason": "test", "spend": 999, "installs": 50}])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected fields ['installs', 'spend']", result.stderr)


class AtomicWriteTest(unittest.TestCase):
    def test_failed_write_keeps_the_previous_file(self):
        path = Path(tempfile.mkdtemp()) / "report.md"
        path.write_text("previous")
        with mock.patch.object(terms.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                terms.atomic_write(path, "new")
        self.assertEqual(path.read_text(), "previous")
        self.assertEqual([p.name for p in path.parent.iterdir()], ["report.md"])


class PartialPublicationTest(unittest.TestCase):
    setUp = TermsTest.setUp

    def test_failed_later_file_leaves_earlier_files_from_the_new_run(self):
        out = self.dir / "out"
        out.mkdir()
        for name in ("negatives.csv", "report.md"):
            (out / name).write_text("previous")
        decisions = self.dir / "decisions.json"
        decisions.write_text(json.dumps({"decisions": [
            {"term": "planet fitness", "campaign": "Discovery", "ad_group": "Search Match", "bucket": "adjacent",
             "action": "negative_exact", "bid": "hold", "reason": "A gym chain"}]}))
        real = terms.atomic_write

        def fail_on_report(path, text):
            if Path(path).name == "report.md":
                raise OSError("disk full")
            real(path, text)
        argv = ["terms.py", "write", "--terms", str(self.summary), "--decisions", str(decisions), "--out", str(out)]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(terms, "atomic_write", fail_on_report):
            with self.assertRaises(OSError):
                terms.main()
        self.assertIn("planet fitness", (out / "negatives.csv").read_text())  # new run
        self.assertEqual((out / "report.md").read_text(), "previous")       # old run, as documented


class PermissionTest(unittest.TestCase):
    def test_replacement_publishes_new_content_everywhere(self):
        path = Path(tempfile.mkdtemp()) / "report.txt"
        path.write_text("old")
        terms.atomic_write(path, "new")
        terms.atomic_write(path.with_name("fresh.txt"), "fresh")
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
            terms.atomic_write(private, "new")
            terms.atomic_write(fresh, "new")
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
        self.assertEqual(private.read_text(), "new")
        self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o644)


if __name__ == "__main__":
    unittest.main()
