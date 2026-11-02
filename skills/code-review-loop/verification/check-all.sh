#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 "$verification_dir/check-helper-decisions.py"
"$verification_dir/check-state-space.sh"
"$verification_dir/check-mutations.sh"
"$verification_dir/check-witnesses.sh"
"$verification_dir/check-liveness-limit.sh"
