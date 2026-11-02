"""Dispatcher bookkeeping and lifecycle decisions; agent runtime calls stay with the agent."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import sys
import time
from pathlib import Path
from typing import Any

from review_loop_protocol import (
    DISPATCH_REQUEST,
    DISPATCHER_LOCK,
    IMPLEMENTOR_FINAL,
    POLL_INTERVAL_SECONDS,
    ProtocolError,
    atomic_write,
    emit,
    fail,
    marker_present,
    read_session_state,
    remove_exact,
    require_nonempty_channel,
    resolve_coordination_directory,
    resolve_session,
    save_session_state,
    service_directory,
    session_info,
)

WORKER_STATUSES = ("running", "resumable", "stopped", "gone", "unknown", "error")


def session_error(directory: Path, error: Exception) -> dict[str, Any]:
    return {
        "event": "session_error",
        "action": "report",
        "session_id": directory.name,
        "session_directory": str(directory),
        "error": str(error),
    }


def sessions(coordination_directory: Path) -> list[dict[str, Any]]:
    root = service_directory(coordination_directory) / "sessions"
    result = []
    for path in sorted(root.iterdir()):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", path.name):
            continue
        try:
            if not stat.S_ISDIR(path.lstat().st_mode):
                continue
            info = session_info(resolve_session(coordination_directory, path.name))
            if stat.S_ISDIR(path.lstat().st_mode):
                result.append(info)
        except FileNotFoundError:
            continue
        except (ProtocolError, OSError) as error:
            # Maintenance may retire a closed directory during this scan.
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            except OSError:
                pass
            result.append(session_error(path, error))
    return result


def cleanup_closed(coordination_directory: Path) -> dict[str, Any]:
    """Delete terminal sessions, removing them from scans before recursive deletion."""
    root = service_directory(coordination_directory)
    deleted = 0
    errors = []

    def delete_retired(path: Path) -> None:
        nonlocal deleted
        try:
            if path.is_symlink() or not path.is_dir():
                raise ProtocolError(
                    f"deletion target must be an ordinary directory: {path}"
                )
            shutil.rmtree(path)
            deleted += 1
        except (ProtocolError, OSError) as error:
            errors.append(
                {
                    "session_id": path.name.removeprefix(".deleting-"),
                    "error": str(error),
                }
            )

    # Retry an interrupted deletion, including one that already removed state.json.
    for path in sorted(root.glob(".deleting-*")):
        if re.fullmatch(r"\.deleting-[A-Za-z0-9_-]+", path.name):
            delete_retired(path)

    for info in sessions(coordination_directory):
        if info.get("event") == "session_error":
            errors.append(info)
        elif info["session_status"] == "closed":
            directory = Path(info["session_directory"])
            retired = root / (".deleting-" + info["session_id"])
            try:
                if retired.exists() or retired.is_symlink():
                    raise ProtocolError(f"deletion target already exists: {retired}")
                # Atomic rename prevents the listener from reading a half-deleted
                # state.json as a fresh open session. This is temporary, not archival.
                directory.rename(retired)
            except (ProtocolError, OSError) as error:
                errors.append(session_error(directory, error))
            else:
                delete_retired(retired)
    return {
        "event": "closed_sessions_deleted",
        "deleted_count": deleted,
        "errors": errors,
    }


def start(coordination_directory: Path, revive: bool = False) -> dict[str, Any]:
    root = service_directory(coordination_directory)
    marker = root / DISPATCHER_LOCK
    if marker.exists() and not revive:
        raise ProtocolError(
            "dispatcher marker exists; stop the previous dispatcher and start --revive"
        )
    atomic_write(marker, "")
    return {
        "event": "service_started",
        "sessions": [
            s
            for s in sessions(coordination_directory)
            if s.get("session_status") != "closed"
        ],
    }


def decide_action(
    info: dict[str, Any], worker_status: str, shutdown: bool = False
) -> str:
    if worker_status not in WORKER_STATUSES:
        raise ProtocolError(f"unknown runtime status: {worker_status}")
    if info["session_status"] == "closed":
        return "leave"
    if worker_status == "error":
        return "report"
    stopped = not info["worker_handle"] or worker_status in (
        "stopped",
        "gone",
        "unknown",
    )
    if info["close_requested"] or shutdown:
        if stopped:
            return "mark_closed" if info["close_requested"] else "leave"
        return "stop"
    if not info["review_pending"]:
        return "leave"
    if not info["worker_handle"]:
        return "launch"
    if worker_status == "running":
        return "await_worker" if info["dispatch_requested"] else "continue"
    if worker_status == "resumable":
        return "resume"
    return "replace"


def reconcile(
    directory: Path,
    worker_status: str,
    error: str | None = None,
    shutdown: bool = False,
) -> dict[str, Any]:
    info = session_info(directory)
    if worker_status == "error" and (not error or not error.strip()):
        raise ProtocolError(
            "runtime status error requires --error with the actual failure"
        )
    action = decide_action(info, worker_status, shutdown)
    state = read_session_state(directory)
    if state["status"] != "closed":
        # Acknowledge BEFORE the runtime call: a fast worker can release the round
        # and the implementor can submit another before bind/resume returns.
        # Failed/interrupted runtime calls are retried through explicit recovery.
        if action in ("launch", "replace", "resume"):
            remove_exact(directory, (DISPATCH_REQUEST,))
        state["error"] = error if action == "report" else None
        state["error_operation"] = (
            ("close" if info["close_requested"] else "runtime")
            if action == "report"
            else None
        )
        if action == "mark_closed":
            state["status"] = "closed"
        save_session_state(directory, state)
    return {"event": "lifecycle_action", **session_info(directory), "action": action}


def bind(directory: Path, worker_handle: str) -> dict[str, Any]:
    if not worker_handle.strip():
        raise ProtocolError(
            "worker handle must be the non-empty handle returned by the runtime"
        )
    state = read_session_state(directory)
    if state["status"] == "closed":
        raise ProtocolError(
            "cannot bind a worker to a closed session; stop the newly created worker"
        )
    state.update(worker_handle=worker_handle, error=None, error_operation=None)
    save_session_state(directory, state)
    info = session_info(directory)
    return {
        "event": "worker_bound",
        **info,
        "action": "stop" if info["close_requested"] else "continue",
    }


def pending_events(coordination_directory: Path) -> list[dict[str, Any]]:
    events = []
    for info in sessions(coordination_directory):
        if info.get("event") == "session_error":
            events.append(info)
            continue
        if info["session_status"] == "closed":
            continue
        if info["close_requested"]:
            if info.get("error_operation") != "close":
                events.append({"event": "close_requested", **info})
        elif (
            info["dispatch_requested"]
            and not info.get("error")
            and info["review_pending"]
        ):
            directory = Path(info["session_directory"])
            try:
                require_nonempty_channel(directory, IMPLEMENTOR_FINAL)
                events.append({"event": "review_submitted", **info})
            except (ProtocolError, OSError) as error:
                events.append(session_error(directory, error))
    return events


def wait_for_events(
    coordination_directory: Path,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    reported_errors: list[str] | None = None,
    busy_sessions: list[str] | None = None,
) -> dict[str, Any]:
    root = service_directory(coordination_directory)
    reported = set(reported_errors or ())
    busy = set(busy_sessions or ())
    while marker_present(root, DISPATCHER_LOCK):
        events = []
        current_errors = set()
        for event in pending_events(coordination_directory):
            if event["event"] == "session_error":
                current_errors.add(event["session_id"])
                if event["session_id"] not in reported:
                    events.append(event)
            elif not (
                event["event"] == "review_submitted" and event["session_id"] in busy
            ):
                events.append(event)
        if events:
            return {
                "event": "dispatch_events",
                "sessions": events,
                "reported_errors": sorted(current_errors),
            }
        reported = current_errors
        time.sleep(poll_interval)
    return {"event": "service_stopped"}


def shutdown(coordination_directory: Path, statuses: dict[str, Any]) -> dict[str, Any]:
    """Consume freshly observed statuses; only remove the marker after every worker stops."""
    if not isinstance(statuses, dict):
        raise ProtocolError("shutdown input must map session IDs to runtime statuses")
    actions = []
    for info in sessions(coordination_directory):
        if info.get("event") == "session_error":
            actions.append(info)
            continue
        if info["session_status"] == "closed":
            continue
        worker_status = statuses.get(
            info["session_id"], "gone" if not info["worker_handle"] else "error"
        )
        if worker_status not in WORKER_STATUSES:
            raise ProtocolError(
                f"invalid runtime status for {info['session_id']}: {worker_status!r}"
            )
        directory = Path(info["session_directory"])
        try:
            actions.append(
                reconcile(
                    directory,
                    worker_status,
                    error="runtime status missing or failed; inspect this worker before shutdown"
                    if worker_status == "error"
                    else None,
                    shutdown=True,
                )
            )
        except (ProtocolError, OSError) as error:
            actions.append(session_error(directory, error))
    if any(item["action"] in ("stop", "report") for item in actions):
        return {"event": "shutdown_pending", "sessions": actions}
    (service_directory(coordination_directory) / DISPATCHER_LOCK).unlink(
        missing_ok=True
    )
    return {"event": "service_stopped", "sessions": actions}


class ProtocolArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProtocolError(f"invalid arguments: {message}; see --help for examples")


def build_parser() -> argparse.ArgumentParser:
    parser = ProtocolArgumentParser(
        description=__doc__,
        epilog="Example: dispatcher_loop.py start --coordination-dir /workspace --revive",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in (
        "start",
        "status",
        "wait",
        "reconcile",
        "bind",
        "shutdown",
        "cleanup-closed",
    ):
        child = commands.add_parser(command)
        child.add_argument("--coordination-dir", required=True)
        if command == "start":
            child.add_argument("--revive", action="store_true")
        if command in ("reconcile", "bind"):
            child.add_argument("--session", required=True)
        if command == "status":
            child.add_argument("--session")
        if command == "wait":
            child.add_argument(
                "--busy-session",
                action="append",
                default=[],
                metavar="SESSION_ID",
                help="defer a request until this worker's runtime completion notification; never hides closure or errors",
            )
            child.add_argument(
                "--reported-error",
                action="append",
                default=[],
                metavar="SESSION_ID",
                help="already-reported broken session; repeat for IDs in the last reported_errors result",
            )
        if command == "reconcile":
            child.add_argument(
                "--worker-status", choices=WORKER_STATUSES, required=True
            )
            child.add_argument("--error")
        if command == "bind":
            child.add_argument("--worker-handle", required=True)
        if command == "shutdown":
            child.add_argument(
                "--statuses-stdin",
                action="store_true",
                required=True,
                help='JSON mapping, e.g. {"session-id": "stopped"}',
            )
    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        coordination_directory = resolve_coordination_directory(args.coordination_dir)
        if args.command == "start":
            result = start(coordination_directory, args.revive)
        elif args.command == "cleanup-closed":
            result = cleanup_closed(coordination_directory)
            if result["errors"]:
                print(
                    json.dumps({"status": "error", **result}),
                    file=sys.stderr,
                    flush=True,
                )
                return 2
        elif args.command == "status":
            entries = (
                [session_info(resolve_session(coordination_directory, args.session))]
                if args.session
                else sessions(coordination_directory)
            )
            result = {"event": "session_status", "sessions": entries}
        elif args.command == "wait":
            result = wait_for_events(
                coordination_directory,
                reported_errors=args.reported_error,
                busy_sessions=args.busy_session,
            )
        elif args.command == "shutdown":
            result = shutdown(coordination_directory, json.load(sys.stdin))
        else:
            directory = resolve_session(coordination_directory, args.session)
            if args.command == "bind":
                result = bind(directory, args.worker_handle)
            else:
                result = reconcile(directory, args.worker_status, args.error)
        emit("ready", **result)
    except KeyboardInterrupt:
        return 130
    except (ProtocolError, OSError, ValueError) as exc:
        return fail(exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
