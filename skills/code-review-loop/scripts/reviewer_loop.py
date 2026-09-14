"""Complete reviewer endpoint for the code-review-loop file protocol."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from review_loop_protocol import (
    IMPLEMENTOR_FINAL,
    POLL_INTERVAL_SECONDS,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    REVIEWER_TEMP,
    ROUND_COMPLETE,
    STALE_STATE_GRACE_SECONDS,
    ProtocolError,
    emit,
    fail,
    load_message_input,
    promote_channel,
    remove_exact,
    require_nonempty_channel,
    resolve_coordination_directory,
    snapshot,
    write_channel_temp,
)


class ProtocolArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProtocolError(f"invalid arguments: {message}")


def wait_for_request(
    coordination_directory: Path,
    participated: bool,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stale_grace: float = STALE_STATE_GRACE_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    unexpected_completion_since: Optional[float] = None  # noqa: UP045
    invalid_completion_since: Optional[float] = None  # noqa: UP045
    orphaned_reviewer_temp_since: Optional[float] = None  # noqa: UP045

    while True:
        state = snapshot(coordination_directory)

        if state.round_complete:
            if len(state.present_names()) != 1:
                now = monotonic_fn()
                if invalid_completion_since is None:
                    invalid_completion_since = now
                elif now - invalid_completion_since >= stale_grace:
                    raise ProtocolError(
                        "completion marker coexisted with protocol files for "
                        f"{stale_grace:.0f} seconds"
                    )
                sleep_fn(poll_interval)
                continue
            invalid_completion_since = None
            if participated:
                emit(
                    "ready",
                    event="completion",
                    coordination_directory=str(coordination_directory),
                )
                return

            now = monotonic_fn()
            if unexpected_completion_since is None:
                unexpected_completion_since = now
            elif now - unexpected_completion_since >= stale_grace:
                raise ProtocolError(
                    f"completion marker remained for {stale_grace:.0f} seconds before "
                    "this reviewer participated"
                )
            sleep_fn(poll_interval)
            continue

        invalid_completion_since = None
        unexpected_completion_since = None
        if not state.review_lock:
            if state.reviewer_temp:
                if state.reviewer_final:
                    raise ProtocolError(
                        "reviewer temp and final coexist without a review lock"
                    )
                if participated:
                    remove_exact(coordination_directory, (REVIEWER_TEMP,))
                    orphaned_reviewer_temp_since = None
                    continue
                now = monotonic_fn()
                if orphaned_reviewer_temp_since is None:
                    orphaned_reviewer_temp_since = now
                elif now - orphaned_reviewer_temp_since >= stale_grace:
                    raise ProtocolError(
                        f"reviewer temp remained for {stale_grace:.0f} seconds before this "
                        "reviewer participated"
                    )
            else:
                orphaned_reviewer_temp_since = None
            sleep_fn(poll_interval)
            continue
        orphaned_reviewer_temp_since = None
        if state.implementor_temp:
            raise ProtocolError("implementor temp exists in submitted review snapshot")
        require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
        if state.reviewer_temp and state.reviewer_final:
            raise ProtocolError("reviewer temp and final coexist while lock exists")
        if state.reviewer_final:
            request_body = require_nonempty_channel(
                coordination_directory, IMPLEMENTOR_FINAL
            )
            response_body = require_nonempty_channel(
                coordination_directory, REVIEWER_FINAL
            )
            emit(
                "ready",
                event="review_ready_to_release",
                coordination_directory=str(coordination_directory),
                message=request_body,
                response_kind=(
                    "no_findings"
                    if response_body.strip() == "NO_FINDINGS"
                    else "findings"
                ),
            )
            return
        request_body = require_nonempty_channel(
            coordination_directory, IMPLEMENTOR_FINAL
        )
        emit(
            "ready",
            event="review_request",
            coordination_directory=str(coordination_directory),
            message=request_body,
        )
        return


def prepare_response(coordination_directory: Path) -> list[str]:
    state = snapshot(coordination_directory)
    if not state.review_lock:
        raise ProtocolError("cannot prepare reviewer response without a review lock")
    if state.implementor_temp:
        raise ProtocolError("cannot review while implementor temp exists")
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    if state.reviewer_final:
        raise ProtocolError(
            "reviewer final is already published; release it instead of replacing it"
        )
    removed = remove_exact(coordination_directory, (REVIEWER_TEMP,))
    after = snapshot(coordination_directory)
    if after.reviewer_temp or after.reviewer_final:
        raise ProtocolError("reviewer output cleanup did not finish")
    return removed


def release_review(coordination_directory: Path, *, emit_result: bool = True) -> bool:
    state = snapshot(coordination_directory)
    if state.round_complete:
        raise ProtocolError("cannot release review after completion")
    if state.implementor_temp:
        raise ProtocolError("cannot release an unstable implementor snapshot")
    if state.reviewer_temp:
        raise ProtocolError("cannot release review while reviewer temp exists")
    if not state.review_lock:
        # Unlock is the command's durable postcondition.  Once it is absent,
        # the implementor may consume the response at any time, including
        # between this snapshot and a replay-time channel read.
        if emit_result:
            emit(
                "ready",
                event="review_released",
                coordination_directory=str(coordination_directory),
                recovered=True,
            )
        return True
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    require_nonempty_channel(coordination_directory, REVIEWER_FINAL)
    if state.review_lock:
        remove_exact(coordination_directory, (REVIEW_LOCK,))
    if emit_result:
        emit(
            "ready",
            event="review_released",
            coordination_directory=str(coordination_directory),
        )
    return False


def publish_response(coordination_directory: Path, body: str) -> None:
    state = snapshot(coordination_directory)
    if state.round_complete:
        raise ProtocolError("cannot publish reviewer response after completion")
    if state.implementor_temp:
        raise ProtocolError("cannot respond to an unstable implementor snapshot")

    if state.reviewer_final:
        existing = require_nonempty_channel(coordination_directory, REVIEWER_FINAL)
        if existing != body:
            raise ProtocolError("a different reviewer response is already published")
        release_review(coordination_directory, emit_result=False)
        emit(
            "ready",
            event="response_published",
            coordination_directory=str(coordination_directory),
            recovered=True,
        )
        return

    if not state.review_lock:
        if state.reviewer_temp:
            remove_exact(coordination_directory, (REVIEWER_TEMP,))
        raise ProtocolError("cannot publish reviewer response without a review lock")

    removed = prepare_response(coordination_directory)
    write_channel_temp(coordination_directory, REVIEWER_TEMP, body)
    before_promotion = snapshot(coordination_directory)
    if not before_promotion.review_lock:
        remove_exact(coordination_directory, (REVIEWER_TEMP,))
        emit(
            "ready",
            event="response_aborted",
            coordination_directory=str(coordination_directory),
        )
        return
    if before_promotion.implementor_temp or before_promotion.reviewer_final:
        raise ProtocolError("protocol state changed during response publication")
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    promote_channel(coordination_directory, REVIEWER_TEMP, REVIEWER_FINAL)
    release_review(coordination_directory, emit_result=False)
    emit(
        "ready",
        event="response_published",
        coordination_directory=str(coordination_directory),
        removed=removed,
    )


def acknowledge_completion(coordination_directory: Path, participated: bool) -> None:
    if not participated:
        raise ProtocolError(
            "completion acknowledgement requires reviewer participation"
        )
    state = snapshot(coordination_directory)
    if not state.round_complete:
        if not state.present_names():
            emit(
                "ready",
                event="completion_acknowledged",
                coordination_directory=str(coordination_directory),
                recovered=True,
            )
            return
        raise ProtocolError("completion marker is absent")
    if len(state.present_names()) != 1:
        raise ProtocolError("completion marker must be the only protocol file")
    remove_exact(coordination_directory, (ROUND_COMPLETE,))
    if snapshot(coordination_directory).present_names():
        raise ProtocolError("protocol files remain after completion acknowledgement")
    emit(
        "ready",
        event="completion_acknowledged",
        coordination_directory=str(coordination_directory),
    )


def _add_coordination_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--coordination-dir", required=True)


def _add_message_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message")
    source.add_argument("--message-file")
    source.add_argument("--message-stdin", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = ProtocolArgumentParser(
        description="Reviewer-side protocol operations for code-review-loop."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    wait_parser = subparsers.add_parser("wait-for-request")
    _add_coordination_argument(wait_parser)
    participation = wait_parser.add_mutually_exclusive_group(required=True)
    participation.add_argument("--fresh", action="store_true")
    participation.add_argument("--participated", action="store_true")

    publish_parser = subparsers.add_parser("publish-response")
    _add_coordination_argument(publish_parser)
    _add_message_arguments(publish_parser)

    release_parser = subparsers.add_parser("release-review")
    _add_coordination_argument(release_parser)

    acknowledge_parser = subparsers.add_parser("acknowledge-completion")
    _add_coordination_argument(acknowledge_parser)
    acknowledge_parser.add_argument(
        "--participated", action="store_true", required=True
    )
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        coordination_directory = resolve_coordination_directory(args.coordination_dir)
        if args.command == "wait-for-request":
            wait_for_request(coordination_directory, participated=args.participated)
        elif args.command == "publish-response":
            publish_response(
                coordination_directory,
                load_message_input(args.message, args.message_file, args.message_stdin),
            )
        elif args.command == "release-review":
            release_review(coordination_directory)
        elif args.command == "acknowledge-completion":
            acknowledge_completion(
                coordination_directory, participated=args.participated
            )
        else:
            raise ProtocolError(f"unsupported reviewer command: {args.command}")
    except KeyboardInterrupt:
        return 130
    except (ProtocolError, OSError) as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
