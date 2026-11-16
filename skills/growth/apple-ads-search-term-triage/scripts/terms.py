#!/usr/bin/env python3
"""Mechanical half of Apple Ads search-term triage.

  summarize  read a search-terms export (CSV) into one normalized JSON file, with totals
             and mechanical flags (spend without installs, expensive, too little data)
  write      turn the agent's per-term decisions into recommendation CSVs and a report

The judgment in between (what each searcher wants) belongs to the agent. This script
only counts, checks and formats, so the same export always gives the same numbers.

Numbers use a decimal point with optional comma thousands separators (1,234.56).
Exports that write decimal commas (1.234,56) need --decimal-comma; anything the script
can't read exactly is rejected with its row and column, never guessed.

The output CSVs are recommendations for a person to apply in Apple Ads. They are not in
Apple's bulk-upload format, which needs campaign and ad group IDs and numeric bids.
"""
import argparse
import contextlib
import csv
import io
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

# Lower-cased export headers this script accepts for each field, in order of preference.
HEADERS = {
    "term": ["search term", "search terms", "search term text", "searchterm", "search_term"],
    "campaign": ["campaign name", "campaign"],
    "ad_group": ["ad group name", "ad group", "adgroup", "ad_group"],
    "keyword": ["keyword", "keyword text", "matched keyword"],
    "match_source": ["match source", "search term source", "source"],
    "impressions": ["impressions"],
    "taps": ["taps"],
    "installs": ["installs", "total installs", "installs (tap-through)", "tap-through installs", "conversions"],
    "spend": ["spend", "local spend", "spend (usd)", "total spend"],
}
# Triage needs these; without them the flags and recommendations would rest on invented zeroes.
REQUIRED = ("term", "spend", "taps", "installs")
COUNTS = ("taps", "installs", "impressions")
METRICS = ("taps", "installs", "spend")
OPTIONAL_METRICS = ("impressions",)
DELIMITERS = (",", ";", "\t")
EMPTY_VALUES = {"", "-", "--", "—", "n/a", "na"}
CURRENCY = r"(?:[$€£¥₽₹]|[A-Z]{3})"

BUCKETS = {"core", "adjacent", "competitor", "irrelevant", "unclear"}
ACTIONS = {"keep", "negative_exact", "negative_broad", "promote_exact"}
BIDS = {"raise", "lower", "hold"}
DECISION_FIELDS = {"term", "campaign", "ad_group", "bucket", "action", "bid", "reason"}


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


def map_headers(fieldnames, strict=True):
    """Map export headers to fields. With strict=False, return None instead of exiting."""
    lowered = {name.strip().lower(): name for name in fieldnames if name}
    mapping = {}
    for field, candidates in HEADERS.items():
        for candidate in candidates:
            if candidate in lowered:
                mapping[field] = lowered[candidate]
                break
    # Apple renames metric columns from time to time; fall back to the first header that
    # names the metric and isn't a rate or a cost per unit.
    for field, stem in (("installs", "install"), ("spend", "spend")):
        if field not in mapping:
            for low, original in lowered.items():
                if stem in low and not any(word in low for word in ("rate", "cpa", "cpi", "avg", "per ")):
                    mapping[field] = original
                    break
    missing = [field for field in REQUIRED if field not in mapping]
    if missing and not strict:
        return None
    if missing:
        raise SystemExit(
            f"export is missing {', '.join(missing)}; headers found: {', '.join(fieldnames)}. "
            "Export the Search Terms report from Apple Ads as CSV, with taps and installs."
        )
    return mapping


def number(text, decimal_comma, where):
    """Read one export number exactly; None for an empty or 'unavailable' cell.

    Only a currency symbol or a three-letter currency code around the number is removed.
    Everything else must be a complete number in the chosen convention, so "1e3",
    "12abc34" and "<5" are rejected rather than read as 13, 1234 or 5.
    """
    raw = (text or "").strip()
    if raw.lower() in EMPTY_VALUES:
        return None
    match = re.fullmatch(
        rf"([-+]?)\s*(?:{CURRENCY}\s*)?([-+]?)([\d.,]+)(?:\s*{CURRENCY})?", raw)
    thousands, decimal = (".", ",") if decimal_comma else (",", ".")
    grammar = rf"(?:\d{{1,3}}(?:{re.escape(thousands)}\d{{3}})+|\d+)(?:{re.escape(decimal)}\d+)?"
    if not match or (match.group(1) and match.group(2)) or not re.fullmatch(grammar, match.group(3)):
        hint = ""
        if match and not decimal_comma and re.fullmatch(r"\d+,\d{1,2}", match.group(3)):
            hint = " (it looks like a decimal comma: pass --decimal-comma)"
        raise ValueError(f"{where}: can't read {raw!r} as a number{hint}")
    sign = "-" if "-" in (match.group(1) + match.group(2)) else ""
    return float(sign + match.group(3).replace(thousands, "").replace(decimal, "."))


def find_header(lines):
    """Return (line index, delimiter) of the header row, skipping report preambles."""
    for index, line in enumerate(lines[:50]):
        for delimiter in DELIMITERS:
            cells = next(csv.reader([line], delimiter=delimiter), [])
            if len(cells) > 1 and map_headers(cells, strict=False):
                return index, delimiter
    first = next((line for line in lines if line.strip()), "")
    cells = max((next(csv.reader([first], delimiter=d), []) for d in DELIMITERS), key=len)
    map_headers(cells)  # exits, naming what's missing and the headers it saw
    raise SystemExit("no header row found")


def read_export(path, decimal_comma=False):
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    start, delimiter = find_header(lines)
    reader = csv.reader(io.StringIO("".join(lines[start:]), newline=""), delimiter=delimiter, strict=True)
    header = next(reader)
    mapping = map_headers(header)
    rows, errors = [], []
    records = []
    try:
        for cells in reader:
            records.append((start + reader.line_num, cells))
    except csv.Error as error:
        raise SystemExit(f"export rejected, nothing written: malformed CSV near line {start + reader.line_num}: {error}")
    for line, cells in records:
        where = f"line {line}"
        if not any(cell.strip() for cell in cells):
            continue
        if len(cells) != len(header):
            errors.append(f"{where}: {len(cells)} fields, but the header has {len(header)}")
            continue
        raw = dict(zip(header, cells))
        term = (raw.get(mapping["term"]) or "").strip()
        if not term or term.lower() in ("total", "totals", "grand total"):
            continue
        row = {"term": term}
        for field in ("campaign", "ad_group", "keyword", "match_source"):
            row[field] = (raw.get(mapping[field]) or "").strip() if field in mapping else ""
        for field in (*METRICS, *OPTIONAL_METRICS):
            if field not in mapping:
                row[field] = None
                continue
            try:
                row[field] = number(raw.get(mapping[field]), decimal_comma, f"{where}, column {mapping[field]!r}")
            except ValueError as error:
                errors.append(str(error))
                continue
            if row[field] is None and field in METRICS:
                errors.append(f"{where}, column {mapping[field]!r}: no value; triage needs an explicit number, 0 included")
            elif row[field] is not None and field in COUNTS and (row[field] < 0 or row[field] != int(row[field])):
                errors.append(f"{where}, column {mapping[field]!r}: {raw.get(mapping[field])!r} isn't a whole number of at least 0")
        rows.append(row)
    if errors:
        more = f"\n  ... and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise SystemExit("export rejected, nothing written:\n  " + "\n  ".join(errors[:20]) + more)
    return rows, mapping


def aggregate(rows):
    """Sum per-day rows into one row per search term, campaign and ad group."""
    merged = {}
    for row in rows:
        key = (row["term"].lower(), row["campaign"], row["ad_group"])
        if key not in merged:
            merged[key] = {**row}
            continue
        for field in METRICS:
            merged[key][field] += row[field]
        for field in OPTIONAL_METRICS:
            # One day without the value makes the total unknown, not smaller.
            if merged[key][field] is None or row[field] is None:
                merged[key][field] = None
            else:
                merged[key][field] += row[field]
    return list(merged.values())


def add_metrics(row, min_spend, target_cpa, min_taps):
    taps, installs, spend, impressions = row["taps"], row["installs"], row["spend"], row["impressions"]
    row["cpt"] = round(spend / taps, 2) if taps else None
    row["cpa"] = round(spend / installs, 2) if installs else None
    row["ttr"] = round(taps / impressions, 4) if impressions else None
    row["conversion_rate"] = round(installs / taps, 4) if taps else None
    flags = []
    if spend >= min_spend and installs == 0:
        flags.append("spend_without_installs")
    if target_cpa and installs and spend / installs > 2 * target_cpa:
        flags.append("expensive")
    if taps < min_taps:
        flags.append("low_data")
    row["flags"] = flags
    row["taps"], row["installs"], row["spend"] = int(taps), int(installs), round(spend, 2)
    if impressions is not None:
        row["impressions"] = int(impressions)
    return row


def summarize(args):
    rows, mapping = read_export(args.export, args.decimal_comma)
    if not rows:
        raise SystemExit(f"no search-term rows in {args.export}")
    rows = [add_metrics(row, args.min_spend, args.target_cpa, args.min_taps) for row in aggregate(rows)]
    rows.sort(key=lambda row: row["spend"], reverse=True)
    totals = {field: round(sum(row[field] for row in rows), 2) for field in METRICS}
    known = [row["impressions"] for row in rows]
    totals["impressions"] = sum(known) if "impressions" in mapping and None not in known else None
    totals["cpa"] = round(totals["spend"] / totals["installs"], 2) if totals["installs"] else None
    output = {
        "source_file": str(Path(args.export).resolve()),
        "columns_used": mapping,
        "settings": {"min_spend": args.min_spend, "target_cpa": args.target_cpa, "min_taps": args.min_taps,
                     "decimal_comma": args.decimal_comma},
        "term_count": len(rows),
        "totals": totals,
        "flag_counts": {flag: sum(flag in row["flags"] for row in rows)
                        for flag in ("spend_without_installs", "expensive", "low_data")},
        "rows": rows,
    }
    atomic_write(args.out, json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}: {len(rows)} terms, spend {totals['spend']}, installs {int(totals['installs'])}", file=sys.stderr)


def words(text):
    return set(re.findall(r"\w+", text.lower()))


def blocked_protected(term, action, protected):
    """Return the protected phrase a negative keyword would block, if any.

    Any negative that is itself a protected search (all the phrase's words, any order) is
    refused. A broad negative also blocks every search containing all of its words, so it
    is refused when its words are a subset of a protected phrase: a broad "fitness" blocks
    "acme fitness".
    """
    term_words = words(term)
    for phrase in protected:
        phrase_words = words(phrase)
        if not phrase_words:
            continue
        if phrase_words <= term_words:
            return phrase
        if action == "negative_broad" and term_words and term_words <= phrase_words:
            return phrase
    return None


def load_decisions(path, terms, protected):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    decisions = data["decisions"] if isinstance(data, dict) else data
    known = {(row["term"].lower(), row["campaign"], row["ad_group"]): row for row in terms["rows"]}
    errors, merged, seen = [], [], set()
    for index, decision in enumerate(decisions):
        where = f"decision {index + 1} ({decision.get('term', '?')!r})"
        extra = sorted(set(decision) - DECISION_FIELDS)
        if extra:
            errors.append(f"{where}: unexpected fields {extra}; metrics come only from the summary")
        key = ((decision.get("term") or "").lower(), decision.get("campaign", ""), decision.get("ad_group", ""))
        if key not in known:
            errors.append(f"{where}: no such term/campaign/ad group in the summary")
            continue
        if key in seen:
            errors.append(f"{where}: decided twice")
        seen.add(key)
        for field, allowed in (("bucket", BUCKETS), ("action", ACTIONS), ("bid", BIDS)):
            if decision.get(field) not in allowed:
                errors.append(f"{where}: {field} must be one of {sorted(allowed)}")
        if not (decision.get("reason") or "").strip():
            errors.append(f"{where}: reason is required")
        action = decision.get("action") or ""
        if action.startswith("negative"):
            phrase = blocked_protected(known[key]["term"], action, protected)
            if phrase:
                errors.append(f"{where}: this negative would block the protected search {phrase!r}")
        # Only the judgment comes from the decision; every measured value stays as summarized.
        merged.append({**known[key], **{field: decision.get(field) for field in ("bucket", "action", "bid", "reason")}})
    undecided = [row["term"] for k, row in known.items() if k not in seen]
    if errors:
        raise SystemExit("decisions rejected:\n  " + "\n  ".join(errors))
    return merged, undecided


def csv_text(header, rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def write(args):
    terms = json.loads(Path(args.terms).read_text(encoding="utf-8"))
    protected = [p.strip().lower() for p in args.protect.split(",") if p.strip()]
    decisions, undecided = load_decisions(args.decisions, terms, protected)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    negatives = [d for d in decisions if d["action"].startswith("negative")]
    promotions = [d for d in decisions if d["action"] == "promote_exact"]
    bids = [d for d in decisions if d["bid"] != "hold"]
    match_type = {"negative_exact": "Exact", "negative_broad": "Broad"}
    saved = round(sum(d["spend"] for d in negatives), 2)
    by_bucket = {}
    for d in decisions:
        bucket = by_bucket.setdefault(d["bucket"], {"terms": 0, "spend": 0.0, "installs": 0})
        bucket["terms"] += 1
        bucket["spend"] = round(bucket["spend"] + d["spend"], 2)
        bucket["installs"] += d["installs"]
    lines = [
        "# Search-term triage",
        "",
        f"Source: `{terms['source_file']}` · {terms['term_count']} terms · spend {terms['totals']['spend']} · installs {int(terms['totals']['installs'])}",
        "",
        "**Nothing has been changed in Apple Ads.** These are recommendations to review, then apply "
        "by hand in Apple Ads. They aren't in Apple's bulk-upload format, which needs campaign and ad "
        "group IDs and numeric bids.",
        "",
        "| Bucket | Terms | Spend | Installs |",
        "|---|---|---|---|",
        *[f"| {name} | {b['terms']} | {b['spend']} | {b['installs']} |" for name, b in sorted(by_bucket.items())],
        "",
        f"- **Negatives:** {len(negatives)} terms (`negatives.csv`). Spend on them in this period: {saved}.",
        f"- **Promote to exact keywords:** {len(promotions)} terms (`promote_exact.csv`).",
        f"- **Bid recommendations:** {len(bids)} (`bid_changes.csv`): a direction to apply with a bid you choose.",
    ]
    if undecided:
        lines += ["", f"**Undecided ({len(undecided)}):** " + ", ".join(undecided[:30]) + (" …" if len(undecided) > 30 else "")]

    # Build every file first, then replace each one whole.
    files = {
        "negatives.csv": csv_text(["Keyword", "Match Type", "Campaign", "Ad Group", "Spend", "Installs", "Reason"],
                                  [[d["term"], match_type[d["action"]], d["campaign"], d["ad_group"], d["spend"], d["installs"], d["reason"]] for d in negatives]),
        "promote_exact.csv": csv_text(["Keyword", "Match Type", "Campaign", "Ad Group", "Installs", "CPA", "Reason"],
                                      [[d["term"], "Exact", d["campaign"], d["ad_group"], d["installs"], d["cpa"], d["reason"]] for d in promotions]),
        "bid_changes.csv": csv_text(["Keyword", "Campaign", "Ad Group", "Recommendation", "CPA", "Reason"],
                                    [[d["term"], d["campaign"], d["ad_group"], d["bid"], d["cpa"], d["reason"]] for d in bids]),
        "report.md": "\n".join(lines) + "\n",
    }
    for name, text in files.items():
        atomic_write(out / name, text)
    print(f"wrote {out}/: {len(negatives)} negatives, {len(promotions)} promotions, {len(bids)} bid recommendations", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    s = commands.add_parser("summarize", help="normalize an export and add metrics and flags")
    s.add_argument("--export", required=True, help="Apple Ads search-terms report, CSV, with taps and installs")
    s.add_argument("--out", required=True, help="JSON file to write")
    s.add_argument("--min-spend", type=float, default=5.0, help="flag terms that spent at least this with no installs")
    s.add_argument("--target-cpa", type=float, default=0.0, help="flag terms with CPA above twice this; 0 to skip")
    s.add_argument("--min-taps", type=int, default=5, help="below this many taps a term is marked low_data")
    s.add_argument("--decimal-comma", action="store_true", help="numbers are written 1.234,56 instead of 1,234.56")

    w = commands.add_parser("write", help="turn decisions into recommendation CSVs and a report")
    w.add_argument("--terms", required=True, help="JSON from summarize")
    w.add_argument("--decisions", required=True, help="the agent's decisions JSON")
    w.add_argument("--out", required=True, help="directory for the output files")
    w.add_argument("--protect", default="", help="comma-separated searches that negatives may never block, e.g. your brand")

    args = parser.parse_args()
    summarize(args) if args.command == "summarize" else write(args)


if __name__ == "__main__":
    main()
