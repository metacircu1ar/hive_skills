---
name: script-read-check
description: >-
  Check that a narrated audio or video file says exactly what its script says. A
  local Whisper model transcribes it word by word; the words are aligned with the
  script, and every misread, missing or extra word is reported with its timestamps.
  Use before publishing any AI-voiced ad, avatar video, demo or voice-over, and to
  locate the exact span to re-record or patch.
---

# Script read check

AI voices and avatar models mispronounce names, skip words and invent filler. A human
listening once misses half of it. This skill transcribes the media word by word and
lines it up with the script, so every difference comes with a timestamp you can jump
to.

## Invocation

```text
/script-read-check --media FILE --script FILE [--backend mlx|faster|openai] [--model NAME]
                   [--decimal-comma] [--out DIR]
```

- **`--media`:** audio or video, anything ffmpeg reads.
- **`--script`:** a text file with exactly what should be said.
- **`--backend`:** which Whisper to use. Default: the first one installed, in the order
  mlx (Apple Silicon), faster-whisper, openai-whisper.
- **`--model`:** default `mlx-community/whisper-large-v3-turbo` on mlx (about 1.6 GB,
  downloaded on first use), `large-v3-turbo` on faster-whisper and `turbo` on
  openai-whisper. A small model such as `mlx-community/whisper-base-mlx` is faster but
  mishears brand names in a correct read (in testing it heard a two-word brand name as
  "Jim Flow"), so use it only for drafts.
- **`--out`:** directory for `read_check.md` and `read_check.json`. Without it the report
  is printed.

## Boundaries

- **Local only.** Media never leaves the machine.
- **Report, don't fix on your own.** The output is a list of places to listen to. Patch or
  re-record only what the person approves.
- **Any model can mishear a correct read.** Treat every issue as "listen here", not as
  proof of a mistake.
- **Never give the model the script or a list of names as a prompt.** In testing, a
  prompt naming "Calendly" made the model hear "Calendly" where the voice said "Kalanla":
  the prompt hides exactly the mistakes this check exists to find.

## 1. Run the check

```text
python3 "<skill-dir>/scripts/check_read.py" --media ad_v1.mp4 --script ad_v1_script.txt --out checks/ad_v1
```

Exit code 0 means the read matches, 1 means there are differences, and 2 means the check
couldn't run: a missing or unreadable file, an empty script, no Whisper backend, a failed
transcription, or a report that couldn't be written. Each report file is replaced in one
step and keeps its permissions; if writing fails between the two files, they can be from
different runs. If no backend is installed, install
one: `pip install mlx-whisper` on Apple Silicon, otherwise `pip install faster-whisper`.

What counts as the same word:

- Case, surrounding punctuation, apostrophes and accents on Latin letters ("Café" and
  "cafe") don't count. Letters and marks of every other script do, so "мой" and "мои"
  differ, and so do "कला" and "कल".
- Numbers compare by value under one convention: by default "," separates thousands (only
  in groups of three) and "." is the decimal point. So "1,000" and "1000" match, and so do
  "1.50" and "1.5", while "0.125" and "125" differ. Pass `--decimal-comma` for scripts
  written "1.000,50". A number that doesn't fit the convention is compared exactly as
  written. Signs count: "-10" and "10" differ, while hyphenated words ("well-known")
  still split into words. Around a number, only surrounding quotes, brackets, sentence
  punctuation, one sign and one currency symbol are ignored ("$5" and "5" match). Any other
  symbol makes the token compare exactly as written, so ".5" and "5", "50%" and "50", and
  "1.5kg" and "15kg" all differ. A slash or dash between digits stays in the token, so
  fractions, ranges and dates ("1/2", "3–5", "3 - 5", "2026-11-17") must be read the same
  way; "5 -3", with no space after the hyphen, is a negative number. Whisper sometimes
  splits one written number across word records (" 1" and ".99"); the check joins them
  back before comparing, with the timestamps of both.
  Numbers 0 to 10 equal their English words.
- A compound split in two ("Pay pal" for "PayPal") matches.

Each issue is one of:

- **misread:** a different word was heard ("Kalanla" for "Calendly");
- **missing:** script words that weren't heard;
- **extra:** words heard that aren't in the script.

## 2. Confirm and fix

For each issue, listen to that span. If the read really is wrong:

1. **Prefer regenerating the line** with the same voice and settings, then check again.
2. **Patch only with approval:** replace the span with a corrected take using ffmpeg,
   keeping the cut on word boundaries from `read_check.json`, then re-run the check on
   the patched file.

## Tests

The alignment logic has offline tests; transcription itself needs a backend.

```text
python3 -m unittest discover -s "<skill-dir>/scripts" -p 'test_*.py'
```

## Report

Give the match percentage, the issues as a table (time, kind, script, heard), which ones
you confirmed by listening, and what you changed. Stop at "ready to publish" only when a
check with the default large model reports no confirmed issues.
