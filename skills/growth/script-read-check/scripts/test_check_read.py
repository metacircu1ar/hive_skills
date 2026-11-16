#!/usr/bin/env python3
"""Offline tests for check_read.py's alignment; transcription itself needs a Whisper backend."""

import io
import os
import stat
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_read  # noqa: E402
from check_read import align, heard_words, normalize  # noqa: E402


def heard(words):
    return [{"token": normalize(w), "text": w, "start": i * 0.5, "end": i * 0.5 + 0.4} for i, w in enumerate(words)]


class AlignTest(unittest.TestCase):
    def test_exact_read_has_no_issues(self):
        issues, accuracy, count = align("Book it on Calendly, it's 3 clicks.",
                                        heard(["book", "it", "on", "Calendly,", "its", "three", "clicks"]))
        self.assertEqual(issues, [])
        self.assertEqual((accuracy, count), (1.0, 7))

    def test_compound_split_in_two_counts_as_a_match(self):
        issues, accuracy, _ = align("Pay with PayPal today", heard(["pay", "with", "Pay", "pal", "today"]))
        self.assertEqual(issues, [])
        self.assertEqual(accuracy, 1.0)

    def test_misread_and_extra_words_are_reported_with_times(self):
        issues, _, _ = align("Book it on Calendly today please", heard(["book", "it", "on", "Kalanla", "please", "now"]))
        kinds = [(i["kind"], i["script"], i["heard"]) for i in issues]
        self.assertIn(("misread", "Calendly today", "Kalanla"), kinds)
        self.assertIn(("extra", "", "now"), kinds)
        misread = next(i for i in issues if i["kind"] == "misread")
        self.assertEqual((misread["start"], misread["end"]), (1.5, 1.9))


class NormalizationTest(unittest.TestCase):
    def test_different_prices_are_reported(self):
        issues, _, _ = align("It costs $1.99 a month", heard(["it", "costs", "199", "a", "month"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("$1.99", "199")])

    def test_different_non_latin_words_are_reported(self):
        issues, _, _ = align("привет мой друг", heard(["привет", "мои", "друг"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("мой", "мои")])
        issues, _, _ = align("我们 今天 见", heard(["我们", "明天", "见"]))
        self.assertEqual(len(issues), 1)

    def test_three_digit_decimals_are_not_thousands(self):
        issues, _, _ = align("wait 0.125 seconds", heard(["wait", "125", "seconds"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("0.125", "125")])
        issues, _, _ = align("wait 0,125 seconds", [{"token": normalize(w, True), "text": w, "start": 0, "end": 0}
                                                     for w in ["wait", "0.125", "seconds"]], decimal_comma=True)
        self.assertEqual(len(issues), 1)  # 0,125 is a decimal; "0.125" isn't a number in that convention

    def test_indic_vowel_marks_are_kept(self):
        issues, _, _ = align("यह कला है", heard(["यह", "कल", "है"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("कला", "कल")])

    def test_signs_are_kept_and_hyphenated_words_still_split(self):
        issues, _, _ = align("temperature -10 degrees", heard(["temperature", "10", "degrees"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("-10", "10")])
        issues, _, _ = align("a change of -1.5 points", heard(["a", "change", "of", "1.5", "points"]))
        self.assertEqual(len(issues), 1)
        for script_text, words in (("temperature -10 degrees", ["temperature", "-10", "degrees"]),
                                   ("a well-known app", ["a", "well", "known", "app"]),
                                   ("costs $-5 now", ["costs", "-5", "now"])):
            issues, _, _ = align(script_text, heard(words))
            self.assertEqual(issues, [], script_text)

    def test_numbers_joined_to_units_keep_their_punctuation(self):
        issues, _, _ = align("weighs 1.5kg today", heard(["weighs", "15kg", "today"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("1.5kg", "15kg")])
        issues, _, _ = align("it was -10°C outside", heard(["it", "was", "10°C", "outside"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("-10°C", "10°C")])
        for script_text, words in (("weighs 1.5kg.", ["weighs", "1.5kg"]),
                                   ("it was (-10°C)", ["it", "was", "-10°C"]),
                                   ("a 3x speedup", ["a", "3x", "speedup"])):
            issues, _, _ = align(script_text, heard(words))
            self.assertEqual(issues, [], script_text)

    def test_unlisted_symbols_around_numbers_still_count(self):
        issues, _, _ = align("wait .5 seconds", heard(["wait", "5", "seconds"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [(".5", "5")])
        issues, _, _ = align("save 50% today", heard(["save", "50", "today"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("50%", "50")])
        for script_text, words in (('it costs "$5".', ["it", "costs", "5"]),
                                   ("it costs -$5", ["it", "costs", "-5"]),
                                   ("save 50% today", ["save", "50%", "today"]),
                                   ("wait .5 seconds", ["wait", ".5", "seconds"]),
                                   ('"1,000" people', ["1000", "people"])):
            issues, _, _ = align(script_text, heard(words))
            self.assertEqual(issues, [], script_text)

    def test_fractions_ranges_and_dates_keep_their_separators(self):
        for script_text, words, expected in (
                ("add 1/2 cup", ["add", "1", "2", "cup"], ("1/2", "1 2")),
                ("add 1/2 cup", ["add", "1/3", "cup"], ("1/2", "1/3")),
                ("ages 3–5 only", ["ages", "3", "5", "only"], ("3–5", "3 5")),
                ("ages 3 – 5 only", ["ages", "3", "5", "only"], ("3–5", "3 5"))):
            issues, _, _ = align(script_text, heard(words))
            self.assertEqual([(i["script"], i["heard"]) for i in issues], [expected], script_text)
        for script_text, words in (("add 1/2 cup", ["add", "1/2", "cup"]),
                                   ("ages 3–5 only", ["ages", "3–5", "only"]),
                                   ("open 24/7 on 2026-11-17", ["open", "24/7", "on", "2026-11-17"]),
                                   ("a well-known and/or app", ["a", "well", "known", "and", "or", "app"])):
            issues, _, _ = align(script_text, heard(words))
            self.assertEqual(issues, [], script_text)

    def test_spaced_ascii_ranges_keep_their_hyphen_and_negatives_stay_separate(self):
        issues, _, _ = align("ages 3 - 5 only", heard(["ages", "3", "5", "only"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("3-5", "3 5")])
        issues, _, _ = align("ages 3 - 5 only", heard(["ages", "3-5", "only"]))
        self.assertEqual(issues, [])
        issues, _, _ = align("from 5 -3 points", heard(["from", "5", "3", "points"]))
        self.assertEqual([(i["script"], i["heard"]) for i in issues], [("-3", "3")])
        issues, _, _ = align("from 5 -3 points", heard(["from", "5", "-3", "points"]))
        self.assertEqual(issues, [])

    def test_decimal_comma_convention(self):
        self.assertEqual(normalize("1.000", True), normalize("1000", True))
        self.assertEqual(normalize("0,125", True), normalize("0.125"))
        self.assertNotEqual(normalize("0,125", True), normalize("125", True))

    def test_intended_equivalences_still_match(self):
        pairs = [("1,000", "1000"), ("Café", "cafe"), ("it's", "its"), ("$5.", "5"), ("1.50", "1.5"), ("three", "3")]
        for script_word, heard_word in pairs:
            issues, _, _ = align(f"pay {script_word} now", heard(["pay", heard_word, "now"]))
            self.assertEqual(issues, [], (script_word, heard_word))


def records(*words):
    """Whisper-style word records: a leading space starts a new word; none continues one."""
    return [{"text": text, "start": i * 0.25, "end": i * 0.25 + 0.2} for i, text in enumerate(words)]


class TranscriptAdapterTest(unittest.TestCase):
    def check(self, script_text, *segments):
        return align(script_text, heard_words([records(*segment) for segment in segments]))

    def test_numbers_split_across_records_are_rebuilt(self):
        issues, _, _ = self.check("Book it for 1.99 today", [" Book", " it", " for", " 1", ".99", " today"])
        self.assertEqual(issues, [])
        for script_text, words in (("ages 3–5 only", [" ages", " 3", "–5", " only"]),
                                   ("save 50% now", [" save", " 50", "%", " now"]),
                                   ("only $5 now", [" only", " $", "5", " now"]),
                                   ("ages 3 - 5 only", [" ages", " 3", " -", " 5", " only"])):
            issues, _, _ = self.check(script_text, words)
            self.assertEqual(issues, [], script_text)

    def test_wrong_split_number_is_reported_over_both_records(self):
        issues, _, _ = self.check("Book it for 1.99 today", [" Book", " it", " for", " 1", ".89", " today"])
        self.assertEqual([(i["script"], i["heard"], i["start"], i["end"]) for i in issues],
                         [("1.99", "1.89", 0.75, 1.2)])

    def test_records_never_merge_across_segments(self):
        merged = heard_words([records(" ages", " 3"), records("5", " only")])
        self.assertEqual([word["token"] for word in merged], ["ages", "three", "five", "only"])


class ExitCodeTest(unittest.TestCase):
    def setUp(self):
        directory = Path(tempfile.mkdtemp())
        self.media, self.script = directory / "a.wav", directory / "a.txt"
        self.media.write_bytes(b"not really audio")
        self.script.write_text("book it today")

    def run_main(self, transcribe=None, backend_installed=True, out=None):
        argv = ["check_read.py", "--media", str(self.media), "--script", str(self.script)]
        if out:
            argv += ["--out", str(out)]
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sys, "argv", argv))
            stack.enter_context(mock.patch.object(check_read.importlib.util, "find_spec",
                                                  return_value=object() if backend_installed else None))
            if transcribe:
                stack.enter_context(mock.patch.object(check_read, "transcribe", transcribe))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            stop = stack.enter_context(self.assertRaises(SystemExit))
            check_read.main()
        return stop.exception.code

    def test_match_differences_missing_backend_and_failure_have_distinct_codes(self):
        self.assertEqual(self.run_main(lambda *a: heard(["book", "it", "today"])), 0)
        self.assertEqual(self.run_main(lambda *a: heard(["book", "it", "tomorrow"])), 1)
        self.assertEqual(self.run_main(backend_installed=False), 2)

        def broken(*args):
            raise RuntimeError("model download failed")
        self.assertEqual(self.run_main(broken), 2)

    def test_unreadable_script_and_failed_report_exit_2(self):
        self.script.write_bytes(b"\xff\xfe not utf-8")
        self.assertEqual(self.run_main(lambda *a: heard(["book"])), 2)
        self.script.write_text("book it today")
        blocker = self.media.parent / "blocker"
        blocker.write_text("a file where the report directory should be")
        self.assertEqual(self.run_main(lambda *a: heard(["book", "it", "today"]), out=blocker / "reports"), 2)


class PermissionTest(unittest.TestCase):
    def test_replacement_publishes_new_content_everywhere(self):
        path = Path(tempfile.mkdtemp()) / "report.txt"
        path.write_text("old")
        check_read.atomic_write(path, "new")
        check_read.atomic_write(path.with_name("fresh.txt"), "fresh")
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
            check_read.atomic_write(private, "new")
            check_read.atomic_write(fresh, "new")
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o600)
        self.assertEqual(private.read_text(), "new")
        self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o644)


if __name__ == "__main__":
    unittest.main()
