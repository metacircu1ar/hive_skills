"""Complete implementor endpoint for the code-review-loop file protocol."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path

from review_loop_protocol import (
    CLOSE_REQUEST,
    DISPATCH_REQUEST,
    IMPLEMENTOR_FINAL,
    IMPLEMENTOR_TEMP,
    POLL_INTERVAL_SECONDS,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    ProtocolError,
    create_empty_marker,
    emit,
    fail,
    load_message_input,
    marker_present,
    open_session,
    promote_channel,
    read_channel,
    read_session_state,
    remove_exact,
    require_nonempty_channel,
    require_open_session,
    resolve_coordination_directory,
    resolve_session,
    session_closing,
    session_info,
    snapshot,
    write_channel_temp,
)


class ProtocolArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProtocolError(f"invalid arguments: {message}")


def prepare_context(session_directory: Path) -> list[str]:
    require_open_session(session_directory)
    state = snapshot(session_directory)
    if state.review_lock:
        raise ProtocolError("cannot prepare implementor context while lock exists")
    if state.reviewer_temp:
        raise ProtocolError("cannot prepare context while reviewer temp exists")
    if state.reviewer_final:
        raise ProtocolError("cannot prepare context before feedback is acknowledged")
    removed = remove_exact(
        session_directory, (IMPLEMENTOR_TEMP, IMPLEMENTOR_FINAL, DISPATCH_REQUEST)
    )
    after = snapshot(session_directory)
    if after.review_lock:
        raise ProtocolError("review lock appeared during implementor cleanup")
    if after.implementor_temp or after.implementor_final:
        raise ProtocolError("implementor output cleanup did not finish")
    return removed


def publish_context(session_directory: Path, body: str) -> None:
    removed = prepare_context(session_directory)
    write_channel_temp(session_directory, IMPLEMENTOR_TEMP, body)
    state = snapshot(session_directory)
    if state.review_lock:
        raise ProtocolError("review lock appeared during context publication")
    if state.reviewer_temp or state.reviewer_final:
        raise ProtocolError("protocol state changed during context publication")
    if state.implementor_final or not state.implementor_temp:
        raise ProtocolError("implementor context temp is not ready for promotion")
    require_open_session(session_directory)
    promote_channel(session_directory, IMPLEMENTOR_TEMP, IMPLEMENTOR_FINAL)
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    emit(
        "ready",
        event="context_published",
        session_directory=str(session_directory),
        removed=removed,
    )


def request_review(session_directory: Path) -> None:
    require_open_session(session_directory)
    state = snapshot(session_directory)
    if state.implementor_temp:
        raise ProtocolError("cannot request review while implementor temp exists")
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    if state.review_lock:
        emit(
            "ready",
            event="review_requested",
            session_directory=str(session_directory),
            recovered=True,
        )
        return
    if state.reviewer_temp:
        raise ProtocolError("cannot request review while reviewer temp exists")
    if state.reviewer_final:
        raise ProtocolError("cannot request review before feedback is acknowledged")
    # Queue dispatch before publishing the lock. Replaying a locked request never
    # queues it again; an interrupted unlocked submission can reuse this marker.
    if not state.dispatch_requested:
        create_empty_marker(session_directory, DISPATCH_REQUEST)
    create_empty_marker(session_directory, REVIEW_LOCK)
    emit(
        "ready",
        event="review_requested",
        session_directory=str(session_directory),
    )


def wait_for_review(
    session_directory: Path,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    while True:
        if session_closing(session_directory):
            emit(
                "ready",
                event="session_closing",
                session_directory=str(session_directory),
            )
            return
        state = snapshot(session_directory)

        if state.implementor_temp:
            raise ProtocolError("implementor temp exists in a frozen review snapshot")

        if state.review_lock:
            require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
            if state.reviewer_temp and state.reviewer_final:
                raise ProtocolError("reviewer temp and final coexist while lock exists")
            sleep_fn(poll_interval)
            continue

        if state.reviewer_final:
            if state.reviewer_temp:
                raise ProtocolError("reviewer temp and final coexist after unlock")
            require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
            body = require_nonempty_channel(session_directory, REVIEWER_FINAL)
            emit(
                "ready",
                event="review_result",
                session_directory=str(session_directory),
                message=body,
                result_kind=(
                    "no_findings" if body.strip() == "NO_FINDINGS" else "findings"
                ),
            )
            return

        if state.reviewer_temp:
            raise ProtocolError("reviewer temp exists without a review lock")
        raise ProtocolError(
            "no review requested or feedback already acknowledged; "
            "use request-review explicitly to submit a round"
        )


def acknowledge_feedback(session_directory: Path) -> None:
    require_open_session(session_directory)
    state = snapshot(session_directory)
    if state.review_lock:
        raise ProtocolError("cannot acknowledge reviewer feedback while lock exists")
    if state.implementor_temp:
        raise ProtocolError("cannot acknowledge feedback while implementor temp exists")
    if state.reviewer_temp:
        raise ProtocolError("cannot acknowledge feedback while reviewer temp exists")
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    if not state.reviewer_final:
        emit(
            "ready",
            event="feedback_acknowledged",
            session_directory=str(session_directory),
            feedback_kind="unknown",
            recovered=True,
        )
        return
    body = require_nonempty_channel(session_directory, REVIEWER_FINAL)
    remove_exact(session_directory, (REVIEWER_FINAL,))
    emit(
        "ready",
        event="feedback_acknowledged",
        session_directory=str(session_directory),
        feedback_kind="no_findings" if body.strip() == "NO_FINDINGS" else "findings",
    )


def close_session(session_directory: Path) -> None:
    if not session_closing(session_directory):
        try:
            create_empty_marker(session_directory, CLOSE_REQUEST)
        except ProtocolError:
            if not marker_present(session_directory, CLOSE_REQUEST):
                raise
    emit("ready", event="close_requested", **session_info(session_directory))


def status(session_directory: Path) -> None:
    state = snapshot(session_directory)
    emit(
        "ready",
        event="session_status",
        **session_info(session_directory),
        context_message=read_channel(session_directory, IMPLEMENTOR_FINAL)
        if state.implementor_final
        else None,
        feedback_ready=state.reviewer_final and not state.review_lock,
    )


def wait_for_close(
    session_directory: Path,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    if not session_closing(session_directory):
        raise ProtocolError("close was not requested; run close-session first")
    while read_session_state(session_directory)["status"] != "closed":
        sleep_fn(poll_interval)
    emit("ready", event="session_closed", **session_info(session_directory))


def build_parser() -> argparse.ArgumentParser:
    parser = ProtocolArgumentParser(
        description=__doc__,
        epilog="Example: implementor_loop.py open-session --coordination-dir /workspace",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "open-session",
        "status",
        "publish-context",
        "request-review",
        "wait-for-review",
        "acknowledge-feedback",
        "close-session",
        "wait-for-close",
    ):
        child = subparsers.add_parser(command)
        child.add_argument("--coordination-dir", required=True)
        if command != "open-session":
            child.add_argument(
                "--session", required=True, help="session ID or absolute session path"
            )
        if command == "publish-context":
            source = child.add_mutually_exclusive_group(required=True)
            source.add_argument("--message")
            source.add_argument("--message-file")
            source.add_argument("--message-stdin", action="store_true")
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        coordination_directory = resolve_coordination_directory(args.coordination_dir)
        if args.command == "open-session":
            directory = open_session(coordination_directory)
            emit(
                "ready",
                event="session_opened",
                coordination_directory=str(coordination_directory),
                **session_info(directory),
            )
            return 0
        directory = resolve_session(coordination_directory, args.session)
        if args.command == "status":
            status(directory)
        elif args.command == "publish-context":
            publish_context(
                directory,
                load_message_input(args.message, args.message_file, args.message_stdin),
            )
        else:
            {
                "request-review": request_review,
                "wait-for-review": wait_for_review,
                "acknowledge-feedback": acknowledge_feedback,
                "close-session": close_session,
                "wait-for-close": wait_for_close,
            }[args.command](directory)
    except KeyboardInterrupt:
        return 130
    except (ProtocolError, OSError) as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
