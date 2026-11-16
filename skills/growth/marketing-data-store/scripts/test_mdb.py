#!/usr/bin/env python3
"""Tests for mdb.py: provenance, deduplication, schema drift and read-only queries."""

import contextlib
import csv
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MDB = Path(__file__).resolve().parent / "mdb.py"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(MDB), *map(str, args)], capture_output=True, text=True, env=env)


class MarketingDbTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.db = self.dir / "m.sqlite"

    def write_csv(self, name, rows):
        path = self.dir / name
        with open(path, "w", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return path

    def count(self, sql):
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            return connection.execute(sql).fetchone()[0]

    def test_import_dedupes_adds_columns_and_queries_read_only(self):
        first = self.write_csv("a.csv", [["Date", "Campaign", "Spend"], ["2026-11-01", "Discovery", "4.5"]])
        second = self.write_csv("b.csv", [["Date", "Campaign", "Spend", "Installs"], ["2026-11-02", "Discovery", "5", "2"]])
        for path in (first, first, second):
            result = run("--db", self.db, "import", "--source", "apple_ads", "--kind", "campaigns", "--file", path)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.count("SELECT COUNT(*) FROM _imports"), 2)
        self.assertEqual(self.count("SELECT COUNT(*) FROM apple_ads_campaigns"), 2)
        query = run("--db", self.db, "query", "SELECT SUM(CAST(spend AS REAL)) AS total FROM apple_ads_campaigns", "--format", "json")
        self.assertEqual(json.loads(query.stdout), [{"total": 9.5}])
        self.assertNotEqual(run("--db", self.db, "query", "DELETE FROM apple_ads_campaigns").returncode, 0)
        sneaky = run("--db", self.db, "query", "WITH x AS (SELECT 1) DELETE FROM apple_ads_campaigns")
        self.assertNotEqual(sneaky.returncode, 0)
        self.assertEqual(self.count("SELECT COUNT(*) FROM apple_ads_campaigns"), 2)

    def test_database_comes_from_flag_or_environment(self):
        env = {k: v for k, v in os.environ.items() if k != "MARKETING_DB"}
        missing = run("schema", env=env)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("MARKETING_DB", missing.stderr)
        path = self.write_csv("c.csv", [["day", "spend"], ["2026-11-01", "1"]])
        env["MARKETING_DB"] = str(self.db)
        result = run("import", "--source", "stripe", "--kind", "charges", "--file", path, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("stripe_charges", run("schema", env=env).stdout)

    def test_read_only_holds_for_paths_with_uri_characters(self):
        names = ["marketing.sqlite#backup", "100%.sqlite"]
        if os.name != "nt":
            names.append("what?.sqlite")  # Windows doesn't allow '?' in file names
        for name in names:
            db = self.dir / name
            path = self.write_csv(f"{len(name)}.csv", [["day", "spend"], ["2026-11-01", "1"]])
            imported = run("--db", db, "import", "--source", "ads", "--kind", "daily", "--file", path)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            ok = run("--db", db, "query", "SELECT COUNT(*) AS n FROM ads_daily", "--format", "json")
            self.assertEqual(json.loads(ok.stdout), [{"n": 1}], name)
            write = run("--db", db, "query", "WITH x AS (SELECT 1) DELETE FROM ads_daily")
            self.assertNotEqual(write.returncode, 0, name)
            with contextlib.closing(sqlite3.connect(db)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM ads_daily").fetchone()[0], 1, name)
        self.assertFalse((self.dir / "marketing.sqlite").exists())

    def test_repeated_headers_never_collide_with_real_ones(self):
        path = self.write_csv("dup.csv", [["Amount", "Amount", "Amount_2"], ["1", "2", "3"]])
        result = run("--db", self.db, "import", "--source", "stripe", "--kind", "charges", "--file", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        with contextlib.closing(sqlite3.connect(self.db)) as connection:
            columns = [r[1] for r in connection.execute('PRAGMA table_info("stripe_charges")')]
            self.assertEqual(columns, ["_import_id", "amount", "amount_2", "amount_2_2"])
            self.assertEqual(connection.execute("SELECT amount, amount_2, amount_2_2 FROM stripe_charges").fetchone(), ("1", "2", "3"))

    def test_oversized_row_fails_without_recording_an_import(self):
        rows = [["day", "spend"]] + [["2026-11-01", "1"]] * 400 + [["2026-11-02", "2", "surplus"]]
        path = self.write_csv("wide.csv", rows)
        result = run("--db", self.db, "import", "--source", "ads", "--kind", "daily", "--file", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("line 402", result.stderr)
        self.assertFalse(self.db.exists())


    def test_short_malformed_semicolon_and_tab_exports_are_rejected(self):
        for delimiter, name in ((";", "semi.csv"), ("\t", "tab.tsv")):
            path = self.dir / name
            path.write_text(delimiter.join(["day", "spend"]) + "\n" + delimiter.join(["2026-11-01", "1"]) + "\n"
                            + delimiter.join(["2026-11-02", "2", "surplus"]) + "\n")
            result = run("--db", self.db, "import", "--source", "ads", "--kind", "daily", "--file", path)
            self.assertNotEqual(result.returncode, 0, name)
            self.assertIn("line 3 has 3", result.stderr)
        short = self.dir / "short.csv"
        short.write_text("day,spend,clicks\n2026-11-01,1\n")
        self.assertIn("line 2 has 2", run("--db", self.db, "import", "--source", "ads", "--kind", "daily", "--file", short).stderr)
        self.assertFalse(self.db.exists())

    def test_ambiguous_header_delimiter_is_rejected(self):
        path = self.dir / "both.csv"
        path.write_text("a,b;c\n1,2;3\n")
        result = run("--db", self.db, "import", "--source", "ads", "--kind", "daily", "--file", path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("can't tell", result.stderr)

    def test_header_keeps_its_column_across_imports(self):
        first = self.write_csv("first.csv", [["Amount", "Amount_2"], ["10", "fee-a"]])
        second = self.write_csv("second.csv", [["Amount", "Amount", "Amount_2"], ["20", "dup", "fee-b"]])
        for path in (first, second):
            result = run("--db", self.db, "import", "--source", "stripe", "--kind", "charges", "--file", path)
            self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(run("--db", self.db, "query", "SELECT amount, amount_2, amount_3 FROM stripe_charges ORDER BY _import_id",
                              "--format", "json").stdout)
        self.assertEqual(rows, [{"amount": "10", "amount_2": "fee-a", "amount_3": None},
                                {"amount": "20", "amount_2": "fee-b", "amount_3": "dup"}])


    def import_text(self, name, text, source="ads", kind="daily"):
        path = self.dir / name
        path.write_text(text)
        return run("--db", self.db, "import", "--source", source, "--kind", kind, "--file", path)

    def test_unterminated_quote_is_rejected_without_touching_the_database(self):
        result = self.import_text("bad.csv", 'day,spend\n2026-11-01,"1\n2026-11-02,2\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed CSV", result.stderr)
        self.assertFalse(self.db.exists())
        result = self.import_text("note.csv", 'day,note\n2026-11-01,"line one\nline two"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(run("--db", self.db, "query", "SELECT day, note FROM ads_daily", "--format", "json").stdout)
        self.assertEqual(rows, [{"day": "2026-11-01", "note": "line one\nline two"}])

    def test_multiline_quoted_headers_pick_the_right_delimiter(self):
        for delimiter, kind in ((",", "comma"), (";", "semi"), ("\t", "tab")):
            text = f'"Spend\nUSD"{delimiter}Date\n10{delimiter}2026-11-01\n'
            result = self.import_text(f"{kind}.csv", text, kind=kind)
            self.assertEqual(result.returncode, 0, (kind, result.stderr))
            rows = json.loads(run("--db", self.db, "query", f"SELECT spend_usd, date FROM ads_{kind}", "--format", "json").stdout)
            self.assertEqual(rows, [{"spend_usd": "10", "date": "2026-11-01"}], kind)

    def test_source_and_kind_pairs_cannot_share_a_table(self):
        first = self.import_text("a.csv", "day,spend\n2026-11-01,1\n", source="meta_ads", kind="daily")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.import_text("b.csv", "day,spend\n2026-11-02,2\n", source="meta", kind="ads_daily")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("already holds --source meta_ads --kind daily", second.stderr)
        rows = json.loads(run("--db", self.db, "query", "SELECT COUNT(*) AS n FROM meta_ads_daily", "--format", "json").stdout)
        self.assertEqual(rows, [{"n": 1}])


if __name__ == "__main__":
    unittest.main()
