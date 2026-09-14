#!/bin/sh
set -eu

verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
check_dir=$(mktemp -d "${TMPDIR:-/tmp}/code-review-loop-state-space.XXXXXX")
trap 'rm -rf "$check_dir"' EXIT HUP INT TERM

expected_states='1127 states generated, 738 distinct states found, 0 states left on queue.'
expected_depth='The depth of the complete state graph search is 23.'

if ! TLC_CONFIG=CodeReviewLoop.cfg \
    TLC_METADIR="$check_dir/states" \
    "$verification_dir/run-tlc.sh" >"$check_dir/tlc.out" 2>&1; then
    echo "The normal model failed before its state space could be checked:" >&2
    sed -n '1,220p' "$check_dir/tlc.out" >&2
    exit 1
fi

observed_states=$(sed -n '/ states generated, .* distinct states found, .* states left on queue\.$/p' "$check_dir/tlc.out" | tail -n 1)
observed_depth=$(sed -n '/^The depth of the complete state graph search is /p' "$check_dir/tlc.out" | tail -n 1)

if [ "$observed_states" != "$expected_states" ] || [ "$observed_depth" != "$expected_depth" ]; then
    echo "The recorded TLC state space has changed." >&2
    echo "Expected: $expected_states" >&2
    echo "Observed: ${observed_states:-<missing>}" >&2
    echo "Expected: $expected_depth" >&2
    echo "Observed: ${observed_depth:-<missing>}" >&2
    echo "Review the model change, then update this script and README.md together." >&2
    exit 1
fi

echo "Expected state space confirmed: 1127 generated, 738 distinct, depth 23."
