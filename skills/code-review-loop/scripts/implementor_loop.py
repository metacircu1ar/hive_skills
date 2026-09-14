"""Complete implementor endpoint for the code-review-loop file protocol."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from review_loop_protocol import (
    IMPLEMENTOR_FINAL,
    IMPLEMENTOR_TEMP,
    POLL_INTERVAL_SECONDS,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    REVIEWER_TEMP,
    ROUND_COMPLETE,
    STALE_STATE_GRACE_SECONDS,
    ProtocolError,
    create_empty_marker,
    emit,
    fail,
    load_message_input,
    promote_channel,
    read_channel,
    remove_exact,
    require_nonempty_channel,
    resolve_coordination_directory,
    snapshot,
    write_channel_temp,
)

STARTUP_CLEANUP_ORDER = (
    REVIEW_LOCK,
    IMPLEMENTOR_FINAL,
    REVIEWER_FINAL,
    IMPLEMENTOR_TEMP,
    REVIEWER_TEMP,
    ROUND_COMPLETE,
)


class ProtocolArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProtocolError(f"invalid arguments: {message}")


def startup_cleanup(coordination_directory: Path) -> None:
    removed = remove_exact(coordination_directory, STARTUP_CLEANUP_ORDER)
    remaining = snapshot(coordination_directory).present_names()
    if remaining:
        raise ProtocolError(
            "startup cleanup left protocol files present: {}".format(
                ", ".join(remaining)
            )
        )
    emit(
        "ready",
        event="startup_cleanup_complete",
        coordination_directory=str(coordination_directory),
        removed=removed,
    )


def prepare_context(coordination_directory: Path) -> list[str]:
    state = snapshot(coordination_directory)
    if state.review_lock:
        raise ProtocolError("cannot prepare implementor context while lock exists")
    if state.round_complete:
        raise ProtocolError("cannot prepare implementor context after completion")
    if state.reviewer_temp:
        raise ProtocolError("cannot prepare context while reviewer temp exists")
    if state.reviewer_final:
        raise ProtocolError("cannot prepare context before feedback is acknowledged")
    removed = remove_exact(
        coordination_directory, (IMPLEMENTOR_TEMP, IMPLEMENTOR_FINAL)
    )
    after = snapshot(coordination_directory)
    if after.review_lock:
        raise ProtocolError("review lock appeared during implementor cleanup")
    if after.implementor_temp or after.implementor_final:
        raise ProtocolError("implementor output cleanup did not finish")
    return removed


def publish_context(coordination_directory: Path, body: str) -> None:
    removed = prepare_context(coordination_directory)
    write_channel_temp(coordination_directory, IMPLEMENTOR_TEMP, body)
    state = snapshot(coordination_directory)
    if state.review_lock:
        raise ProtocolError("review lock appeared during context publication")
    if state.round_complete or state.reviewer_temp or state.reviewer_final:
        raise ProtocolError("protocol state changed during context publication")
    if state.implementor_final or not state.implementor_temp:
        raise ProtocolError("implementor context temp is not ready for promotion")
    promote_channel(coordination_directory, IMPLEMENTOR_TEMP, IMPLEMENTOR_FINAL)
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    emit(
        "ready",
        event="context_published",
        coordination_directory=str(coordination_directory),
        removed=removed,
    )


def request_review(coordination_directory: Path) -> None:
    state = snapshot(coordination_directory)
    if state.round_complete:
        raise ProtocolError("cannot request review after completion")
    if state.implementor_temp:
        raise ProtocolError("cannot request review while implementor temp exists")
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    if state.review_lock:
        emit(
            "ready",
            event="review_requested",
            coordination_directory=str(coordination_directory),
            recovered=True,
        )
        return
    if state.reviewer_temp:
        raise ProtocolError("cannot request review while reviewer temp exists")
    if state.reviewer_final:
        raise ProtocolError("cannot request review before feedback is acknowledged")
    create_empty_marker(coordination_directory, REVIEW_LOCK)
    emit(
        "ready",
        event="review_requested",
        coordination_directory=str(coordination_directory),
    )


def wait_for_review(
    coordination_directory: Path,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stale_grace: float = STALE_STATE_GRACE_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    missing_lock_since: Optional[float] = None  # noqa: UP045
    orphaned_reviewer_temp_since: Optional[float] = None  # noqa: UP045

    while True:
        state = snapshot(coordination_directory)

        if state.round_complete:
            raise ProtocolError("completion marker appeared while waiting for review")
        if state.implementor_temp:
            raise ProtocolError("implementor temp exists in a frozen review snapshot")

        if state.review_lock:
            require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
            if state.reviewer_temp and state.reviewer_final:
                raise ProtocolError("reviewer temp and final coexist while lock exists")
            missing_lock_since = None
            orphaned_reviewer_temp_since = None
            sleep_fn(poll_interval)
            continue

        if state.reviewer_final:
            if state.reviewer_temp:
                raise ProtocolError("reviewer temp and final coexist after unlock")
            require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
            body = require_nonempty_channel(coordination_directory, REVIEWER_FINAL)
            emit(
                "ready",
                event="review_result",
                coordination_directory=str(coordination_directory),
                message=body,
                result_kind=(
                    "no_findings" if body.strip() == "NO_FINDINGS" else "findings"
                ),
            )
            return

        if state.reviewer_temp:
            missing_lock_since = None
            now = monotonic_fn()
            if orphaned_reviewer_temp_since is None:
                orphaned_reviewer_temp_since = now
            elif now - orphaned_reviewer_temp_since >= stale_grace:
                raise ProtocolError(
                    f"reviewer temp remained after unlock for {stale_grace:.0f} seconds"
                )
            sleep_fn(poll_interval)
            continue

        orphaned_reviewer_temp_since = None
        require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
        now = monotonic_fn()
        if missing_lock_since is None:
            missing_lock_since = now
            sleep_fn(poll_interval)
            continue
        if now - missing_lock_since < poll_interval:
            sleep_fn(poll_interval)
            continue

        try:
            create_empty_marker(coordination_directory, REVIEW_LOCK)
        except ProtocolError:
            if snapshot(coordination_directory).review_lock:
                missing_lock_since = None
                continue
            raise
        missing_lock_since = None


def acknowledge_feedback(coordination_directory: Path) -> None:
    state = snapshot(coordination_directory)
    if state.review_lock:
        raise ProtocolError("cannot acknowledge reviewer feedback while lock exists")
    if state.round_complete:
        raise ProtocolError("cannot acknowledge feedback after completion")
    if state.implementor_temp:
        raise ProtocolError("cannot acknowledge feedback while implementor temp exists")
    if state.reviewer_temp:
        raise ProtocolError("cannot acknowledge feedback while reviewer temp exists")
    require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    if not state.reviewer_final:
        emit(
            "ready",
            event="feedback_acknowledged",
            coordination_directory=str(coordination_directory),
            feedback_kind="unknown",
            recovered=True,
        )
        return
    body = require_nonempty_channel(coordination_directory, REVIEWER_FINAL)
    remove_exact(coordination_directory, (REVIEWER_FINAL,))
    emit(
        "ready",
        event="feedback_acknowledged",
        coordination_directory=str(coordination_directory),
        feedback_kind="no_findings" if body.strip() == "NO_FINDINGS" else "findings",
    )


def complete(coordination_directory: Path) -> None:
    state = snapshot(coordination_directory)
    if state.review_lock:
        raise ProtocolError("cannot complete while review lock exists")
    if state.round_complete:
        if len(state.present_names()) != 1:
            raise ProtocolError("completion marker must be the only protocol file")
        emit(
            "ready",
            event="completion_published",
            coordination_directory=str(coordination_directory),
            recovered=True,
        )
        return
    if state.implementor_temp or state.reviewer_temp:
        raise ProtocolError("cannot complete while a channel temp exists")
    if not state.present_names():
        emit(
            "ready",
            event="completion_already_acknowledged",
            coordination_directory=str(coordination_directory),
            recovered=True,
        )
        return

    if state.implementor_final:
        require_nonempty_channel(coordination_directory, IMPLEMENTOR_FINAL)
    reviewer_body = read_channel(coordination_directory, REVIEWER_FINAL)
    normal_completion = reviewer_body.strip() == "NO_FINDINGS"
    interrupted_completion = reviewer_body == "" and not state.implementor_final
    if not normal_completion and not interrupted_completion:
        raise ProtocolError("completion requires an exact NO_FINDINGS reviewer message")

    remove_exact(
        coordination_directory,
        (IMPLEMENTOR_FINAL, IMPLEMENTOR_TEMP, REVIEWER_TEMP),
    )
    before_marker = snapshot(coordination_directory)
    if before_marker.present_names() != [REVIEWER_FINAL]:
        raise ProtocolError(
            "final cleanup must leave only the reviewer final before completion"
        )

    reviewer_path = coordination_directory / REVIEWER_FINAL
    marker_path = coordination_directory / ROUND_COMPLETE
    if normal_completion:
        try:
            with reviewer_path.open("r+b") as channel:
                channel.truncate(0)
                channel.flush()
                os.fsync(channel.fileno())
        except OSError as exc:
            raise ProtocolError(
                f"cannot prepare completion marker {reviewer_path}: {exc}"
            ) from exc
    try:
        os.replace(str(reviewer_path), str(marker_path))
    except OSError as exc:
        raise ProtocolError(
            f"cannot publish completion marker {marker_path}: {exc}"
        ) from exc
    emit(
        "ready",
        event="completion_published",
        coordination_directory=str(coordination_directory),
    )


def wait_for_completion(
    coordination_directory: Path,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stale_grace: float = STALE_STATE_GRACE_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> None:
    invalid_completion_since: Optional[float] = None  # noqa: UP045

    while True:
        state = snapshot(coordination_directory)
        if not state.round_complete:
            if state.present_names():
                raise ProtocolError(
                    "protocol files remain after completion acknowledgement: {}".format(
                        ", ".join(state.present_names())
                    )
                )
            emit(
                "ready",
                event="completion_acknowledged",
                coordination_directory=str(coordination_directory),
            )
            return
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
        sleep_fn(poll_interval)


def _add_coordination_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--coordination-dir", required=True)


def _add_message_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message")
    source.add_argument("--message-file")
    source.add_argument("--message-stdin", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = ProtocolArgumentParser(
        description="Implementor-side protocol operations for code-review-loop."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in (
        "startup-cleanup",
        "request-review",
        "wait-for-review",
        "acknowledge-feedback",
        "complete",
        "wait-for-completion",
    ):
        _add_coordination_argument(subparsers.add_parser(name))
    publish_parser = subparsers.add_parser("publish-context")
    _add_coordination_argument(publish_parser)
    _add_message_arguments(publish_parser)
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        coordination_directory = resolve_coordination_directory(args.coordination_dir)
        if args.command == "startup-cleanup":
            startup_cleanup(coordination_directory)
        elif args.command == "publish-context":
            publish_context(
                coordination_directory,
                load_message_input(args.message, args.message_file, args.message_stdin),
            )
        elif args.command == "request-review":
            request_review(coordination_directory)
        elif args.command == "wait-for-review":
            wait_for_review(coordination_directory)
        elif args.command == "acknowledge-feedback":
            acknowledge_feedback(coordination_directory)
        elif args.command == "complete":
            complete(coordination_directory)
        elif args.command == "wait-for-completion":
            wait_for_completion(coordination_directory)
        else:
            raise ProtocolError(f"unsupported implementor command: {args.command}")
    except KeyboardInterrupt:
        return 130
    except (ProtocolError, OSError) as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
