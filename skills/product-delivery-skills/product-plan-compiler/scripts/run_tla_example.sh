#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="$ROOT/examples/order-cancellation"
JAR="${TLA2TOOLS_JAR:-${1:-}}"

if [[ -z "$JAR" || ! -f "$JAR" ]]; then
  echo "Set TLA2TOOLS_JAR or pass the path to tla2tools.jar as the first argument." >&2
  exit 2
fi

run_tlc() {
  local module="$1"
  (
    cd "$EXAMPLE"
    java -cp "$JAR" tlc2.TLC -config "${module}.cfg" "${module}.tla"
  )
}

echo "Running buggy model; an invariant violation is expected."
set +e
run_tlc OrderLifecycle_Buggy
buggy_rc=$?
set -e
if [[ $buggy_rc -eq 0 ]]; then
  echo "ERROR: buggy model unexpectedly passed." >&2
  exit 1
fi

echo
echo "Running fixed model; success is expected."
run_tlc OrderLifecycle_Fixed

echo
echo "Example behaved as expected: buggy failed, fixed passed."
