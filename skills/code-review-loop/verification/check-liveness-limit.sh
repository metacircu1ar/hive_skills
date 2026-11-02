#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$verification_dir/expect-tlc-failure.sh" CodeReviewLoopNoAutomaticRecovery.cfg \
    'Temporal property LostWorkerEventuallyRecovers was violated.'
