#!/bin/sh
set -eu
verification_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$verification_dir/expect-tlc-failure.sh" CodeReviewLoopTempFileEarlyUnlock.cfg \
    'Action property PublicationBeforeUnlock is violated.'
