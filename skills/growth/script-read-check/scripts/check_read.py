#!/usr/bin/env python3
"""Check that a narrated audio or video file says exactly what its script says.

Transcribes the media word by word with a local Whisper model, aligns the heard words
against the script, and reports every difference with its timestamps.

Exit codes: 0 when the read matches, 1 when there are differences, 2 on errors.

Backends, tried in this order unless --backend is given:
  mlx      mlx-whisper (Apple Silicon)          pip install mlx-whisper
  faster   faster-whisper (CPU or CUDA)         pip install faster-whisper
  openai   openai-whisper                        pip install openai-whisper
"""
import argparse
import contextlib
import difflib
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from decimal import Decimal
from pathlib import Path

# Large turbo models by default: small ones mishear brand names in a correct read.
DEFAULT_MODELS = {
    "mlx": "mlx-community/whisper-large-v3-turbo",
    "faster": "large-v3-turbo",
    "openai": "turbo",
}
LEADING = "\"“”‘’«»([{"
TRAILING = ".,;:!?\"“”‘’«»)]}"
NUMBER_TOKEN = re.compile(r"([-+]?)[$€£¥₽₹]?([-+]?)(\d+(?:[.,]\d+)*)")
NUMBER_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
    "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
}


def normalize_number(text, decimal_comma=False):
    """Write a number by value under one stated convention, or return None.

    By default ',' separates thousands (only in groups of three) and '.' is the decimal
    point, so "1,000" equals "1000" while "0.125" and "125" differ. With decimal_comma the
    roles swap ("1.000" and "0,125"). Anything else isn't a number in that convention and
    is compared exactly as written.
    """
    thousands, decimal = (".", ",") if decimal_comma else (",", ".")
    grouped = rf"\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+"
    if not re.fullmatch(rf"(?:{grouped}|\d+)(?:{re.escape(decimal)}\d+)?", text):
        return None
    value = Decimal(text.replace(thousands, "").replace(decimal, "."))
    return format(value.normalize(), "f")


def strip_latin_accents(word):
    """Remove accents from Latin letters only (café → cafe); й and и stay different."""
    decomposed = unicodedata.normalize("NFD", word)
    kept = []
    for char in decomposed:
        if unicodedata.combining(char) and kept and kept[-1].isascii():
            continue
        kept.append(char)
    return unicodedata.normalize("NFC", "".join(kept))


def meaningful(char):
    """Letters and digits of any script, and combining marks such as Indic vowel signs."""
    return char.isalnum() or unicodedata.category(char).startswith("M")


def split_words(text):
    """Split on spaces, slashes and dashes, except where they carry a number's meaning.

    "well-known" and "and/or" give two words each. "-10", "−1.5" and "$-5" stay signed
    numbers, and a slash or dash between digits stays inside one token, so fractions,
    ranges and dates ("1/2", "3–5", "3 – 5", "3 - 5", "2026-11-17") compare as written.
    """
    text = re.sub(r"(?<=\d)\s*([/–—])\s*(?=\d)", r"\1", text)
    # "3 - 5" is a range; "5 -3" (no space after the hyphen) stays a negative number.
    text = re.sub(r"(?<=\d)\s+-\s+(?=\d)", "-", text)
    words = []
    for chunk in text.split():
        if re.search(r"\d[/–—-]\d", chunk) or re.match(r"[^\w]*[-+−]\W*\d", chunk):
            words.append(chunk)
        else:
            words.extend(part for part in re.split(r"[/–—-]+", chunk) if part)
    return words


def normalize(word, decimal_comma=False):
    """Compare words by meaning-bearing characters only.

    Case, Latin accents, apostrophes and surrounding punctuation don't count. Letters and
    marks of every other script do ("कला" and "कल" differ). Numbers compare by value under
    the chosen convention, keeping their sign ("-10" and "10" differ), and 0–10 equal their
    English words. A number with any other symbol (".5", "50%", "1.5kg", "1/2", "3–5") is
    compared as written.
    """
    word = strip_latin_accents(word).casefold().replace("'", "").replace("\u2019", "")
    if any(char.isdigit() for char in word):
        # Only these decorations around a number are ignored: surrounding quotes, brackets
        # and sentence punctuation, one sign and one currency symbol. Anything else (".5",
        # "50%", "1.5kg", "-10°c") is compared as written, so its meaning still counts.
        core = word.replace("−", "-").lstrip(LEADING).rstrip(TRAILING)
        number = NUMBER_TOKEN.fullmatch(core)
        if not number or (number.group(1) and number.group(2)):
            return core
        value = normalize_number(number.group(3), decimal_comma)
        if value is None:
            value = number.group(3)  # not a number in this convention: compare as written
        if value != "0" and "-" in number.group(1) + number.group(2):
            return f"-{value}"
        return NUMBER_WORDS.get(value, value)
    word = "".join(char for char in word if meaningful(char))
    return NUMBER_WORDS.get(word, word)


def tokenize(text, decimal_comma=False):
    return [token for token in (normalize(raw, decimal_comma) for raw in split_words(text)) if token]


def fail(message):
    """Operational errors exit 2, so they can't be mistaken for read differences (1)."""
    print(message, file=sys.stderr)
    sys.exit(2)


def atomic_write(path, text):
    """Replace path with text in one step.

    Atomic per file: a reader sees the old file or the new one, never a partial write.
    An existing file keeps its permissions; a new one gets 0666 minus the umask, like an
    ordinary write. Uses os.chmod rather than os.fchmod, which Windows lacks before 3.13.
    """
    path = Path(path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(dir=path.resolve().parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def pick_backend(requested):
    modules = {"mlx": "mlx_whisper", "faster": "faster_whisper", "openai": "whisper"}
    order = [requested] if requested else ["mlx", "faster", "openai"]
    for name in order:
        if importlib.util.find_spec(modules[name]):
            return name
    hint = "; ".join(line.strip() for line in __doc__.splitlines() if "pip install" in line)
    fail(f"no Whisper backend installed ({hint})")


def transcribe(media, backend, model, language, decimal_comma=False):
    """Return heard words as dicts with text, start and end (seconds).

    Never pass the script or its names as an initial prompt: in testing, a prompt naming
    "Calendly" made the model hear "Calendly" where the voice said "Kalanla", which hides
    exactly the mistakes this check exists to find.
    """
    if backend == "mlx":
        import mlx_whisper
        result = mlx_whisper.transcribe(str(media), path_or_hf_repo=model, language=language,
                                        word_timestamps=True, condition_on_previous_text=False)
        segments = [[{"text": w["word"], "start": w["start"], "end": w["end"]} for w in s.get("words", [])]
                    for s in result["segments"]]
    elif backend == "faster":
        from faster_whisper import WhisperModel
        found, _ = WhisperModel(model).transcribe(str(media), language=language, word_timestamps=True)
        segments = [[{"text": w.word, "start": w.start, "end": w.end} for w in (s.words or [])] for s in found]
    else:
        import whisper
        result = whisper.load_model(model).transcribe(str(media), language=language, word_timestamps=True)
        segments = [[{"text": w["word"], "start": w["start"], "end": w["end"]} for w in s.get("words", [])]
                    for s in result["segments"]]
    return heard_words(segments, decimal_comma)


def merge_number_records(records):
    """Rejoin a number Whisper split across word records, such as " 1" + ".99".

    A record that doesn't start with a space continues the previous one. It is joined when
    either side of the join is a digit, so "1.99", "3–5", "50%" and "$5" come back whole,
    spanning both records' timestamps. A lone separator record between two numbers joins
    them too. Word pieces without digits are left alone.
    """
    merged = []
    for record in records:
        text = record["text"]
        previous = merged[-1]["text"] if merged else ""
        continues = merged and text and not text[0].isspace()
        if continues and (previous.rstrip()[-1:].isdigit() or re.match(r"[^\w\s]*\d", text)):
            merged[-1] = {"text": previous + text, "start": merged[-1]["start"], "end": record["end"]}
        else:
            merged.append(dict(record))
    # A separator written as its own record between two numbers (" 3", " -", " 5") joins
    # them, so the transcript keeps the range exactly as split_words keeps it in the script.
    joined = []
    for record in merged:
        if (len(joined) >= 2 and joined[-1]["text"].strip() in ("-", "–", "—", "/")
                and joined[-2]["text"].rstrip()[-1:].isdigit() and record["text"].lstrip()[:1].isdigit()):
            separator = joined.pop()
            first = joined.pop()
            record = {"text": f"{first['text']} {separator['text'].strip()} {record['text'].strip()}",
                      "start": first["start"], "end": record["end"]}
        joined.append(record)
    return joined


def heard_words(segments, decimal_comma=False):
    """Turn backend word records, grouped by segment, into tokens tokenized like the script."""
    heard = []
    for records in segments:
        for word in merge_number_records(records):
            for token in tokenize(word["text"], decimal_comma):
                heard.append({"token": token, "text": word["text"].strip(),
                              "start": round(word["start"], 2), "end": round(word["end"], 2)})
    return heard


def align(script_text, heard, decimal_comma=False):
    """Compare script words with heard words and return the differences."""
    script_raw = [raw for raw in split_words(script_text) if normalize(raw, decimal_comma)]
    script_tokens = [normalize(raw, decimal_comma) for raw in script_raw]
    heard_tokens = [word["token"] for word in heard]
    matcher = difflib.SequenceMatcher(None, script_tokens, heard_tokens, autojunk=False)
    issues, matched = [], 0
    for tag, s1, s2, h1, h2 in matcher.get_opcodes():
        if tag == "equal":
            matched += s2 - s1
            continue
        # "PayPal" heard as "Pay pal" (or the reverse) is the same read.
        if tag == "replace" and "".join(script_tokens[s1:s2]) == "".join(heard_tokens[h1:h2]):
            matched += s2 - s1
            continue
        if h1 < h2:
            start, end = heard[h1]["start"], heard[h2 - 1]["end"]
        else:
            # Nothing was heard for these script words: point at the gap between neighbours.
            start = heard[h1 - 1]["end"] if h1 > 0 else 0.0
            end = heard[h1]["start"] if h1 < len(heard) else start
        issues.append({
            "kind": {"replace": "misread", "delete": "missing", "insert": "extra"}[tag],
            "script": " ".join(script_raw[s1:s2]),
            "heard": " ".join(word["text"] for word in heard[h1:h2]),
            "start": round(start, 2),
            "end": round(end, 2),
            "context": " ".join(script_raw[max(0, s1 - 4):s1]) + " [...] " + " ".join(script_raw[s2:s2 + 4]),
        })
    accuracy = round(matched / len(script_tokens), 4) if script_tokens else 0.0
    return issues, accuracy, len(script_tokens)


def timestamp(seconds):
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes):02d}:{secs:05.2f}"


def markdown(report):
    lines = [
        f"# Read check: {Path(report['media']).name}",
        "",
        f"Script words: {report['script_words']} · matched: {report['accuracy']:.1%} · issues: {len(report['issues'])} "
        f"· backend: {report['backend']} ({report['model']})",
        "",
    ]
    if not report["issues"]:
        lines.append("The read matches the script.")
    else:
        lines += ["| # | When | Kind | Script says | Heard | Context |", "|---|---|---|---|---|---|"]
        for number, issue in enumerate(report["issues"], 1):
            lines.append(f"| {number} | {timestamp(issue['start'])}–{timestamp(issue['end'])} | {issue['kind']} | "
                         f"{issue['script'] or '—'} | {issue['heard'] or '—'} | {issue['context']} |")
        lines += ["", "Listen to each one before changing anything: the model can mishear a correct read."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--media", required=True, help="audio or video file (anything ffmpeg can read)")
    parser.add_argument("--script", required=True, help="text file with the exact words that should be spoken")
    parser.add_argument("--backend", choices=sorted(DEFAULT_MODELS), help="default: first one installed")
    parser.add_argument("--model", help="model name or path (default depends on the backend)")
    parser.add_argument("--language", default="en")
    parser.add_argument("--decimal-comma", action="store_true",
                        help="numbers are written 1.000,50 (comma decimals) instead of 1,000.50")
    parser.add_argument("--out", help="directory for read_check.json and read_check.md (default: print markdown)")
    args = parser.parse_args()

    media, script = Path(args.media), Path(args.script)
    for path in (media, script):
        if not path.is_file():
            fail(f"not a file: {path}")
    try:
        script_text = script.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"can't read the script {script}: {error}")
    if not tokenize(script_text, args.decimal_comma):
        fail("the script is empty")

    backend = pick_backend(args.backend)
    model = args.model or DEFAULT_MODELS[backend]
    try:
        heard = transcribe(media, backend, model, args.language, args.decimal_comma)
    except Exception as error:  # a backend can fail in many ways; all of them are errors, not differences
        fail(f"transcription failed ({backend}, {model}): {error}")
    issues, accuracy, script_words = align(script_text, heard, args.decimal_comma)
    report = {
        "media": str(media.resolve()),
        "script": str(script.resolve()),
        "backend": backend,
        "model": model,
        "script_words": script_words,
        "heard_words": len(heard),
        "accuracy": accuracy,
        "issues": issues,
        "heard": heard,
    }
    if args.out:
        out = Path(args.out)
        try:
            out.mkdir(parents=True, exist_ok=True)
            atomic_write(out / "read_check.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            atomic_write(out / "read_check.md", markdown(report))
        except OSError as error:
            fail(f"can't write the report to {out}: {error}")
        print(f"wrote {out}/read_check.md and read_check.json: {len(issues)} issues, {accuracy:.1%} matched", file=sys.stderr)
    else:
        print(markdown(report))
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
