#!/bin/sh
set -eu

verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/code-review-loop-cleanup-negative.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM

if TLC_CONFIG=CodeReviewLoopEarlyCompletionPublication.cfg \
    TLC_METADIR="$check_dir/states" \
    "$verification_dir/run-tlc.sh" >"$check_dir/tlc.out" 2>&1; then
    echo "Expected early completion publication to violate cleanup ordering." >&2
    exit 1
fi

if ! grep -q "Action property CompletionMarkerPublishedLast is violated." "$check_dir/tlc.out"; then
    echo "TLC failed, but not on the expected cleanup-order property:" >&2
    sed -n '1,220p' "$check_dir/tlc.out" >&2
    exit 1
fi

echo "Expected failure detected: early completion publication violates CompletionMarkerPublishedLast."
