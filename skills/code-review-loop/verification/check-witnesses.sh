#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for feature in TwoRounds DeferredRound Concurrent RecoveryRelease RecoveryTemp RestartIdle RestartReplacement; do
    "$verification_dir/expect-tlc-failure.sh" \
        "CodeReviewLoopWitness$feature.cfg" \
        "Invariant No${feature}Witness is violated."
done
