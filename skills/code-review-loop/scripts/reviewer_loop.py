"""Complete reviewer endpoint for the code-review-loop file protocol."""

from __future__ import annotations

import argparse
from pathlib import Path

from review_loop_protocol import (
    IMPLEMENTOR_FINAL,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    REVIEWER_TEMP,
    ProtocolError,
    emit,
    fail,
    load_message_input,
    promote_channel,
    remove_exact,
    require_nonempty_channel,
    require_open_session,
    resolve_coordination_directory,
    resolve_session,
    session_closing,
    snapshot,
    write_channel_temp,
)


class ProtocolArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProtocolError(f"invalid arguments: {message}")


def read_request(session_directory: Path) -> None:
    """Read one dispatched round, returning immediately even if nothing is pending."""
    if session_closing(session_directory):
        emit(
            "ready",
            event="session_closing",
            session_directory=str(session_directory),
        )
        return
    state = snapshot(session_directory)
    if not state.review_lock:
        if state.reviewer_temp:
            if state.reviewer_final:
                raise ProtocolError(
                    "reviewer temp and final coexist without a review lock"
                )
            remove_exact(session_directory, (REVIEWER_TEMP,))
        emit(
            "ready",
            event="no_request",
            session_directory=str(session_directory),
        )
        return
    if state.implementor_temp:
        raise ProtocolError("implementor temp exists in submitted review")
    request_body = require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    if state.reviewer_temp and state.reviewer_final:
        raise ProtocolError("reviewer temp and final coexist while lock exists")
    if state.reviewer_final:
        body = require_nonempty_channel(session_directory, REVIEWER_FINAL)
        emit(
            "ready",
            event="review_ready_to_release",
            session_directory=str(session_directory),
            message=request_body,
            response_kind="no_findings"
            if body.strip() == "NO_FINDINGS"
            else "findings",
        )
        return
    emit(
        "ready",
        event="review_request",
        session_directory=str(session_directory),
        message=request_body,
    )


def prepare_response(session_directory: Path) -> list[str]:
    require_open_session(session_directory)
    state = snapshot(session_directory)
    if not state.review_lock:
        raise ProtocolError("cannot prepare reviewer response without a review lock")
    if state.implementor_temp:
        raise ProtocolError("cannot review while implementor temp exists")
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    if state.reviewer_final:
        raise ProtocolError(
            "reviewer final is already published; release it instead of replacing it"
        )
    removed = remove_exact(session_directory, (REVIEWER_TEMP,))
    after = snapshot(session_directory)
    if after.reviewer_temp or after.reviewer_final:
        raise ProtocolError("reviewer output cleanup did not finish")
    return removed


def release_review(session_directory: Path, *, emit_result: bool = True) -> bool:
    require_open_session(session_directory)
    state = snapshot(session_directory)
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
                session_directory=str(session_directory),
                recovered=True,
            )
        return True
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    require_nonempty_channel(session_directory, REVIEWER_FINAL)
    if state.review_lock:
        remove_exact(session_directory, (REVIEW_LOCK,))
    if emit_result:
        emit(
            "ready",
            event="review_released",
            session_directory=str(session_directory),
        )
    return False


def publish_response(session_directory: Path, body: str) -> None:
    require_open_session(session_directory)
    state = snapshot(session_directory)
    if state.implementor_temp:
        raise ProtocolError("cannot respond to an unstable implementor snapshot")

    if state.reviewer_final:
        existing = require_nonempty_channel(session_directory, REVIEWER_FINAL)
        if existing != body:
            raise ProtocolError("a different reviewer response is already published")
        release_review(session_directory, emit_result=False)
        emit(
            "ready",
            event="response_published",
            session_directory=str(session_directory),
            recovered=True,
        )
        return

    if not state.review_lock:
        if state.reviewer_temp:
            remove_exact(session_directory, (REVIEWER_TEMP,))
        raise ProtocolError("cannot publish reviewer response without a review lock")

    removed = prepare_response(session_directory)
    write_channel_temp(session_directory, REVIEWER_TEMP, body)
    before_promotion = snapshot(session_directory)
    if not before_promotion.review_lock:
        remove_exact(session_directory, (REVIEWER_TEMP,))
        emit(
            "ready",
            event="response_aborted",
            session_directory=str(session_directory),
        )
        return
    if before_promotion.implementor_temp or before_promotion.reviewer_final:
        raise ProtocolError("protocol state changed during response publication")
    require_nonempty_channel(session_directory, IMPLEMENTOR_FINAL)
    require_open_session(session_directory)
    promote_channel(session_directory, REVIEWER_TEMP, REVIEWER_FINAL)
    release_review(session_directory, emit_result=False)
    emit(
        "ready",
        event="response_published",
        session_directory=str(session_directory),
        removed=removed,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = ProtocolArgumentParser(
        description=__doc__,
        epilog="Example: reviewer_loop.py read-request --coordination-dir /workspace --session <id>",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("read-request", "publish-response", "release-review"):
        child = subparsers.add_parser(command)
        child.add_argument("--coordination-dir", required=True)
        child.add_argument(
            "--session", required=True, help="session ID or absolute session path"
        )
        if command == "publish-response":
            source = child.add_mutually_exclusive_group(required=True)
            source.add_argument("--message")
            source.add_argument("--message-file")
            source.add_argument("--message-stdin", action="store_true")
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        coordination_directory = resolve_coordination_directory(args.coordination_dir)
        directory = resolve_session(coordination_directory, args.session)
        if args.command == "read-request":
            read_request(directory)
        elif args.command == "publish-response":
            publish_response(
                directory,
                load_message_input(args.message, args.message_file, args.message_stdin),
            )
        elif args.command == "release-review":
            release_review(directory)
    except KeyboardInterrupt:
        return 130
    except (ProtocolError, OSError) as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
