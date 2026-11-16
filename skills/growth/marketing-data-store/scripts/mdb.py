#!/usr/bin/env python3
"""A small local marketing data store in one SQLite file.

  import  load a CSV export into a table named <source>_<kind>, recording where it came from
  query   run a read-only SQL query and print the result
  schema  list tables, columns, row counts and the latest import of each

Every import is recorded in the _imports table with the file's SHA-256, so loading the
same export twice is skipped. New columns in a later export are added to the table.
Queries open the database read-only, so they can't change anything.

The database is --db FILE, or the MARKETING_DB environment variable.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
DELIMITERS = (",", ";", "\t")


def snake(header, index):
    name = re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")
    if not name:
        name = f"column_{index + 1}"
    if name[0].isdigit():
        name = f"c_{name}"
    return name


def connect(db, read_only=False):
    if read_only:
        if not db.exists():
            raise SystemExit(f"no database at {db}; import something first")
        # as_uri() percent-encodes '#', '?' and '%', so a file name can't end the path early
        # and push mode=ro into a fragment that SQLite ignores.
        connection = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        return connection
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db)
    connection.execute("""CREATE TABLE IF NOT EXISTS _imports (
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, kind TEXT NOT NULL, table_name TEXT NOT NULL,
        file_name TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE, rows INTEGER NOT NULL,
        imported_at TEXT NOT NULL, note TEXT)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS _columns (
        table_name TEXT NOT NULL, header TEXT NOT NULL, occurrence INTEGER NOT NULL,
        column_name TEXT NOT NULL, PRIMARY KEY (table_name, header, occurrence),
        UNIQUE (table_name, column_name))""")
    return connection


def first_record(text, delimiter):
    """The header record as split by this delimiter, quoted newlines included; None if it can't be."""
    try:
        return next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True), None)
    except csv.Error:
        return None


def detect_delimiter(text):
    """Choose the delimiter from the complete header record, so a data row can't sway it."""
    counts = {d: len(first_record(text, d) or []) for d in DELIMITERS}
    best = max(counts.values())
    if best <= 1:
        return ","  # one column: every delimiter reads it the same way
    winners = [d for d, n in counts.items() if n == best]
    if len(winners) > 1:
        names = " and ".join(repr(d) for d in winners)
        raise SystemExit(f"can't tell whether the header is separated by {names}; nothing was imported")
    return winners[0]


def read_csv(path):
    """Return (headers, rows), or exit before anything is written if a row is malformed."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        text = handle.read()
    if not text.strip():
        raise SystemExit(f"{path} has no header row")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=detect_delimiter(text), strict=True)
    records = []
    try:
        headers = next(reader)
        for row in reader:
            records.append((reader.line_num, row))
    except csv.Error as error:
        raise SystemExit(f"{path}: malformed CSV near line {reader.line_num}: {error}; nothing was imported")
    rows, bad = [], []
    for line, row in records:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) > len(headers) and not any(cell.strip() for cell in row[len(headers):]):
            row = row[:len(headers)]  # only trailing empty cells
        if len(row) != len(headers):
            bad.append(f"line {line} has {len(row)}")
            continue
        rows.append(row)
    if bad:
        listed = ", ".join(bad[:20]) + (" ..." if len(bad) > 20 else "")
        raise SystemExit(f"{path}: the header has {len(headers)} fields, but {listed}; nothing was imported")
    return headers, rows


def plan_columns(connection, table, headers):
    """Map each header to a column, reusing the table's earlier mapping.

    A header keeps its column across imports, so "Amount_2" stays in the same column even
    when a later export adds a second "Amount". Repeats of one header are told apart by
    their order (first, second ...). New headers get a name nothing else uses.
    """
    known = {(header, occurrence): column for header, occurrence, column in connection.execute(
        "SELECT header, occurrence, column_name FROM _columns WHERE table_name = ?", (table,))}
    used = set(known.values()) | {r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')}
    seen, columns, new = Counter(), [], []
    for index, header in enumerate(headers):
        seen[header] += 1
        key = (header, seen[header])
        if key in known:
            columns.append(known[key])
            continue
        base = snake(header, index)
        if base.startswith("_"):
            base = f"c{base}"
        name, suffix = base, 2
        while name in used:
            name, suffix = f"{base}_{suffix}", suffix + 1
        used.add(name)
        columns.append(name)
        new.append((table, header, key[1], name))
    return columns, new


def import_csv(args):
    for label, value in (("source", args.source), ("kind", args.kind)):
        if not NAME.match(value):
            raise SystemExit(f"--{label} must be lower-case letters, digits and underscores, starting with a letter")
    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    table = f"{args.source}_{args.kind}"
    headers, rows = read_csv(path)
    connection = connect(Path(args.db))
    with connection:
        existing = connection.execute("SELECT table_name, imported_at FROM _imports WHERE sha256 = ?", (digest,)).fetchone()
        if existing:
            print(f"skipped: this exact file was already imported into {existing[0]} at {existing[1]}", file=sys.stderr)
            return
        # meta_ads + daily and meta + ads_daily both make meta_ads_daily: one table, one dataset.
        owner = connection.execute(
            "SELECT source, kind FROM _imports WHERE table_name = ? AND (source != ? OR kind != ?) LIMIT 1",
            (table, args.source, args.kind)).fetchone()
        if owner:
            raise SystemExit(f"table {table} already holds --source {owner[0]} --kind {owner[1]}; "
                             f"pick a source and kind that don't join into the same name. Nothing was imported.")
        columns, new = plan_columns(connection, table, headers)
        connection.executemany("INSERT INTO _columns (table_name, header, occurrence, column_name) VALUES (?,?,?,?)", new)
        current = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
        if not current:
            definition = ", ".join(f'"{c}" TEXT' for c in columns)
            connection.execute(f'CREATE TABLE "{table}" (_import_id INTEGER NOT NULL, {definition})')
        else:
            for column in columns:
                if column not in current:
                    connection.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" TEXT')
        cursor = connection.execute(
            "INSERT INTO _imports (source, kind, table_name, file_name, sha256, rows, imported_at, note) VALUES (?,?,?,?,?,?,?,?)",
            (args.source, args.kind, table, path.name, digest, len(rows),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), args.note))
        import_id = cursor.lastrowid
        placeholders = ", ".join("?" for _ in range(len(columns) + 1))
        column_list = ", ".join(f'"{c}"' for c in ["_import_id", *columns])
        connection.executemany(f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})',
                               ([import_id, *row] for row in rows))
    print(f"imported {len(rows)} rows from {path.name} into {table} (import {import_id})", file=sys.stderr)


def query(args):
    sql = args.sql.strip().rstrip(";")
    if not re.match(r"^(select|with|pragma\s+table_info)\b", sql, re.IGNORECASE):
        raise SystemExit("only SELECT or WITH queries are allowed")
    connection = connect(Path(args.db), read_only=True)
    try:
        cursor = connection.execute(sql)
    except sqlite3.Error as error:
        raise SystemExit(f"query failed: {error}")
    headers = [d[0] for d in cursor.description or []]
    rows = cursor.fetchmany(args.limit + 1)
    truncated = len(rows) > args.limit
    rows = rows[:args.limit]
    if args.format == "json":
        print(json.dumps([dict(zip(headers, row)) for row in rows], indent=2, ensure_ascii=False))
    elif args.format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(headers)
        writer.writerows(rows)
    else:
        print("| " + " | ".join(headers) + " |")
        print("|" + "---|" * len(headers))
        for row in rows:
            print("| " + " | ".join("" if v is None else str(v) for v in row) + " |")
    if truncated:
        print(f"(stopped at {args.limit} rows; raise --limit or aggregate in SQL)", file=sys.stderr)


def schema(args):
    connection = connect(Path(args.db), read_only=True)
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT IN ('_imports', '_columns') ORDER BY name")]
    if not tables:
        print("no tables yet")
        return
    for table in tables:
        count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        last = connection.execute(
            "SELECT file_name, imported_at FROM _imports WHERE table_name = ? ORDER BY id DESC LIMIT 1", (table,)).fetchone()
        columns = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")') if r[1] != "_import_id"]
        print(f"{table}: {count} rows; last import {last[0]} at {last[1]}" if last else f"{table}: {count} rows")
        print("  " + ", ".join(columns))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=os.environ.get("MARKETING_DB"), help="SQLite file (default: $MARKETING_DB)")
    commands = parser.add_subparsers(dest="command", required=True)

    i = commands.add_parser("import", help="load a CSV export")
    i.add_argument("--source", required=True, help="where it came from, e.g. stripe, revenuecat, apple_ads, meta, posthog, creative")
    i.add_argument("--kind", required=True, help="what it is, e.g. transactions, campaigns, search_terms, events, manifest")
    i.add_argument("--file", required=True)
    i.add_argument("--note", help="date range, filters or anything else worth remembering")

    q = commands.add_parser("query", help="run a read-only SQL query")
    q.add_argument("sql")
    q.add_argument("--format", choices=["table", "csv", "json"], default="table")
    q.add_argument("--limit", type=int, default=200)

    commands.add_parser("schema", help="list tables and columns")

    args = parser.parse_args()
    if not args.db:
        parser.error("no database: pass --db FILE or set MARKETING_DB")
    {"import": import_csv, "query": query, "schema": schema}[args.command](args)


if __name__ == "__main__":
    main()
