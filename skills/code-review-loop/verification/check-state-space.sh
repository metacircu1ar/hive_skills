#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/code-review-loop-state-space.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM

while read -r config generated distinct depth; do
    if ! TLC_CONFIG="$config" TLC_WORKERS=1 TLC_METADIR="$check_dir/states" \
        "$verification_dir/run-tlc.sh" >"$check_dir/tlc.out" 2>&1; then
        echo "Positive model failed: $config" >&2
        cat "$check_dir/tlc.out" >&2
        exit 1
    fi
    expected_states="$generated states generated, $distinct distinct states found, 0 states left on queue."
    expected_depth="The depth of the complete state graph search is $depth."
    if ! grep -Fq 'Model checking completed. No error has been found.' "$check_dir/tlc.out" \
        || ! grep -Fxq "$expected_states" "$check_dir/tlc.out" \
        || ! grep -Fxq "$expected_depth" "$check_dir/tlc.out"; then
        echo "Recorded state space changed for $config; review the model and update the counts in this script." >&2
        cat "$check_dir/tlc.out" >&2
        exit 1
    fi
    echo "$config: $generated generated, $distinct distinct, depth $depth; all checks passed."
done <<'MODELS'
CodeReviewLoop.cfg 193067 64109 60
CodeReviewLoopLiveness.cfg 193067 64109 60
CodeReviewLoopRecovery.cfg 31004 11363 34
CodeReviewLoopIsolation.cfg 10013519 2392041 49
MODELS
