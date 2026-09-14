#!/bin/sh
set -eu

verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/code-review-loop-temp-unlock-negative.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM

if TLC_CONFIG=CodeReviewLoopTempFileEarlyUnlock.cfg \
    TLC_METADIR="$check_dir/states" \
    "$verification_dir/run-tlc.sh" >"$check_dir/tlc.out" 2>&1; then
    echo "Expected unlocking with a reviewer-to-implementor temp to violate the ordering property." >&2
    exit 1
fi

if ! grep -q "Action property ReviewerMessagePublishedBeforeUnlock is violated." "$check_dir/tlc.out"; then
    echo "TLC failed, but not on the expected temp-file ordering property:" >&2
    sed -n '1,220p' "$check_dir/tlc.out" >&2
    exit 1
fi

echo "Expected failure detected: unlocking with reviewerToImplementorTmp violates ReviewerMessagePublishedBeforeUnlock."
