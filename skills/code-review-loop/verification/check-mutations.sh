#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
while IFS='|' read -r config diagnostic; do
    "$verification_dir/expect-tlc-failure.sh" "$config" "$diagnostic"
done <<'CHECKS'
CodeReviewLoopEarlyUnlock.cfg|Action property PublicationBeforeUnlock is violated.
CodeReviewLoopTempFileEarlyUnlock.cfg|Action property PublicationBeforeUnlock is violated.
CodeReviewLoopCrossSession.cfg|Invariant ResponseMatchesSession is violated.
CodeReviewLoopCloseBeforeStop.cfg|Invariant ClosedOnlyAfterStop is violated.
CodeReviewLoopDropFeedback.cfg|Action property FeedbackPreservedUntilAcknowledged is violated.
CodeReviewLoopReplaceRunning.cfg|Action property HandleChangesOnlyWhenUnavailable is violated.
CodeReviewLoopShutdownCloses.cfg|Invariant ClosedOnlyAfterStop is violated.
CHECKS
