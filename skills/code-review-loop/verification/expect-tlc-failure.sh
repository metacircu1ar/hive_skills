#!/bin/sh
# Internal helper: reject syntax errors, tool failures, and wrong counterexamples.
set -eu
if [ "$#" -ne 2 ]; then
    echo "usage: $0 config.cfg 'exact expected TLC diagnostic'" >&2
    exit 2
fi
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/code-review-loop-expected.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM
if TLC_CONFIG="$1" TLC_METADIR="$check_dir/states" \
    "$verification_dir/run-tlc.sh" >"$check_dir/tlc.out" 2>&1; then
    echo "Expected counterexample was not found for $1." >&2
    cat "$check_dir/tlc.out" >&2
    exit 1
fi
if ! grep -Fq "$2" "$check_dir/tlc.out"; then
    echo "TLC failed for $1, but not for the expected reason: $2" >&2
    cat "$check_dir/tlc.out" >&2
    exit 1
fi
echo "$1: $2"
