#!/usr/bin/env python3
"""App Store lookups and review mining for lead research.

Two commands, both read-only against Apple's public endpoints:

  search   find apps by name and print their IDs, sellers and ratings
  reviews  fetch an app's recent public reviews and flag the ones that match a pain

The pain is data: a regex (--pattern) or a file of patterns, one per line (--pattern-file).
Preset files live in ../presets/.

Output is JSON on stdout (or --out FILE). Requests are sequential with a pause between
pages, so the script never hammers Apple's servers.
"""
import argparse
import contextlib
import json
import os
import re
import stat
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) review-lead-finder/1.0"
PAUSE_SECONDS = 1.0
MAX_PAGES = 10

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


def fetch_json(url, retries=2):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == retries:
                raise
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(PAUSE_SECONDS * (attempt + 2))
    raise RuntimeError("unreachable")


def app_summary(result):
    size = result.get("fileSizeBytes")
    return {
        "app_id": result.get("trackId"),
        "name": result.get("trackName"),
        "seller": result.get("sellerName"),
        "seller_url": result.get("sellerUrl"),
        "genre": result.get("primaryGenreName"),
        "rating": round(result["averageUserRating"], 2) if result.get("averageUserRating") is not None else None,
        "rating_count": result.get("userRatingCount"),
        "size_mb": round(int(size) / 1_000_000) if size else None,
        "version": result.get("version"),
        "last_release": result.get("currentVersionReleaseDate"),
        "store_url": result.get("trackViewUrl"),
    }


def search(term, country, limit):
    query = urllib.parse.urlencode({"term": term, "entity": "software", "country": country, "limit": limit})
    data = fetch_json(f"https://itunes.apple.com/search?{query}")
    return [app_summary(result) for result in data.get("results", [])]


def lookup(app_id, country):
    data = fetch_json(f"https://itunes.apple.com/lookup?id={app_id}&country={country}")
    results = data.get("results", [])
    if not results:
        raise SystemExit(f"no App Store app with id {app_id} in country '{country}'")
    return app_summary(results[0])


def parse_feed(feed_json):
    """Return the reviews in one page of Apple's customer-review feed.

    The feed gives a list of entries, a single entry as a dict, or none at all, and older
    pages start with an entry describing the app itself, which has no rating.
    """
    entries = feed_json.get("feed", {}).get("entry", [])
    if isinstance(entries, dict):
        entries = [entries]
    reviews = []
    for entry in entries:
        if "im:rating" not in entry:
            continue
        reviews.append({
            "date": entry.get("updated", {}).get("label", "")[:10],
            "rating": int(entry["im:rating"]["label"]),
            "version": entry.get("im:version", {}).get("label"),
            "title": entry.get("title", {}).get("label", ""),
            "text": entry.get("content", {}).get("label", ""),
            "review_id": entry.get("id", {}).get("label"),
        })
    return reviews


def fetch_reviews(app_id, country, pages):
    reviews = []
    for page in range(1, min(pages, MAX_PAGES) + 1):
        url = f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
        page_reviews = parse_feed(fetch_json(url))
        if not page_reviews:
            break
        reviews.extend(page_reviews)
        time.sleep(PAUSE_SECONDS)
    return reviews


def load_pattern(pattern, pattern_file):
    """Return one regex from --pattern, or from a file with one pattern per line."""
    if pattern:
        return pattern
    lines = Path(pattern_file).read_text(encoding="utf-8").splitlines()
    parts = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not parts:
        raise SystemExit(f"no patterns in {pattern_file}")
    return "|".join(f"(?:{part})" for part in parts)


def flag_reviews(reviews, pattern, since_days, max_rating):
    matcher = re.compile(pattern, re.IGNORECASE)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).date().isoformat() if since_days else ""
    flagged = []
    for review in reviews:
        if cutoff and review["date"] < cutoff:
            continue
        if max_rating and review["rating"] > max_rating:
            continue
        text = f"{review['title']}\n{review['text']}"
        hits = sorted({match.group(0).lower() for match in matcher.finditer(text)})
        if hits:
            flagged.append({**review, "matched": hits})
    return flagged


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    search_parser = commands.add_parser("search", help="find apps by name")
    search_parser.add_argument("term")
    search_parser.add_argument("--country", default="us")
    search_parser.add_argument("--limit", type=int, default=5)

    reviews_parser = commands.add_parser("reviews", help="fetch and flag an app's recent reviews")
    reviews_parser.add_argument("--id", required=True, type=int, help="App Store app ID (the number after 'id' in the URL)")
    reviews_parser.add_argument("--country", default="us")
    reviews_parser.add_argument("--pages", type=int, default=6, help=f"pages of 50 reviews, at most {MAX_PAGES}")
    reviews_parser.add_argument("--since-days", type=int, default=365, help="only flag reviews this recent; 0 for all")
    reviews_parser.add_argument("--max-rating", type=int, default=4, help="only flag reviews at or below this rating; 0 for all")
    pain = reviews_parser.add_mutually_exclusive_group(required=True)
    pain.add_argument("--pattern", help="regex for the pain to flag")
    pain.add_argument("--pattern-file", help="file with one regex per line, # for comments (presets in ../presets/)")
    reviews_parser.add_argument("--all", action="store_true", help="also include every fetched review in the output")

    for sub in (search_parser, reviews_parser):
        sub.add_argument("--out", help="write JSON here instead of stdout")

    args = parser.parse_args()
    if args.command == "search":
        output = {"term": args.term, "country": args.country, "results": search(args.term, args.country, args.limit)}
    else:
        if not 1 <= args.pages <= MAX_PAGES:
            parser.error(f"--pages must be between 1 and {MAX_PAGES}")
        pattern = load_pattern(args.pattern, args.pattern_file)
        try:
            re.compile(pattern)
        except re.error as error:
            parser.error(f"invalid pain pattern: {error}")
        app = lookup(args.id, args.country)
        reviews = fetch_reviews(args.id, args.country, args.pages)
        flagged = flag_reviews(reviews, pattern, args.since_days, args.max_rating)
        output = {
            "app": app,
            "country": args.country,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "review_page": f"https://apps.apple.com/{args.country}/app/id{args.id}?see-all=reviews",
            "reviews_scanned": len(reviews),
            "oldest_scanned": min((r["date"] for r in reviews), default=None),
            "flagged_count": len(flagged),
            "flagged": flagged,
        }
        if args.all:
            output["reviews"] = reviews

    text = json.dumps(output, indent=2, ensure_ascii=False)
    if args.out:
        atomic_write(args.out, text + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
