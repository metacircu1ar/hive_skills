"""Shared file-state primitives for the code-review-loop role CLIs."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

REVIEW_LOCK = ".hive_skills_review_lock"
DISPATCH_REQUEST = "dispatch-request"
IMPLEMENTOR_FINAL = ".hive_skills_implementor_to_reviewer.txt"
REVIEWER_FINAL = ".hive_skills_reviewer_to_implementor.txt"
CLOSE_REQUEST = "close-request"
STATE_FILE = "state.json"
SERVICE_DIRECTORY = ".hive_skills_reviews"
DISPATCHER_LOCK = "dispatcher.lock"
IMPLEMENTOR_TEMP = ".hive_skills_implementor_to_reviewer.tmp"
REVIEWER_TEMP = ".hive_skills_reviewer_to_implementor.tmp"

PROTOCOL_FILES = (
    REVIEW_LOCK,
    DISPATCH_REQUEST,
    IMPLEMENTOR_FINAL,
    REVIEWER_FINAL,
    CLOSE_REQUEST,
    IMPLEMENTOR_TEMP,
    REVIEWER_TEMP,
)
MARKER_FILES = frozenset((REVIEW_LOCK, DISPATCH_REQUEST, CLOSE_REQUEST))
POLL_INTERVAL_SECONDS = 1.0


class ProtocolError(RuntimeError):
    """The coordination directory does not represent a valid protocol state."""


@dataclass(frozen=True)
class Snapshot:
    review_lock: bool
    dispatch_requested: bool
    implementor_final: bool
    reviewer_final: bool
    close_requested: bool
    implementor_temp: bool
    reviewer_temp: bool

    def present_names(self) -> list[str]:
        values = {
            REVIEW_LOCK: self.review_lock,
            DISPATCH_REQUEST: self.dispatch_requested,
            IMPLEMENTOR_FINAL: self.implementor_final,
            REVIEWER_FINAL: self.reviewer_final,
            CLOSE_REQUEST: self.close_requested,
            IMPLEMENTOR_TEMP: self.implementor_temp,
            REVIEWER_TEMP: self.reviewer_temp,
        }
        return [name for name in PROTOCOL_FILES if values[name]]


def resolve_coordination_directory(raw_path: str) -> Path:
    if not raw_path:
        raise ProtocolError("coordination directory is required")

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        raise ProtocolError("coordination directory must be an absolute path")

    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProtocolError(
            f"cannot resolve coordination directory {raw_path!r}: {exc}"
        ) from exc

    if not resolved.is_dir():
        raise ProtocolError(f"coordination directory is not a directory: {resolved}")
    return resolved


def _metadata_kind(metadata: os.stat_result) -> str:
    if stat.S_ISREG(metadata.st_mode):
        return "file"
    if stat.S_ISLNK(metadata.st_mode):
        return "symlink"
    if stat.S_ISDIR(metadata.st_mode):
        return "directory"
    return "other"


def _path_kind(path: Path) -> str:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return "absent"
    except OSError as exc:
        raise ProtocolError(f"cannot inspect {path}: {exc}") from exc

    return _metadata_kind(metadata)


def _inspect_path(path: Path) -> Optional[os.stat_result]:  # noqa: UP045
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProtocolError(f"cannot inspect {path}: {exc}") from exc


def snapshot(coordination_directory: Path) -> Snapshot:
    presence: dict[str, bool] = {}
    for name in PROTOCOL_FILES:
        path = coordination_directory / name
        metadata = _inspect_path(path)
        if metadata is None:
            presence[name] = False
            continue
        kind = _metadata_kind(metadata)
        if kind != "file":
            raise ProtocolError(
                f"protocol path must be an ordinary file or absent: {path} ({kind})"
            )
        if name in MARKER_FILES and metadata.st_size != 0:
            raise ProtocolError(f"marker must be empty: {path}")
        presence[name] = True

    return Snapshot(
        review_lock=presence[REVIEW_LOCK],
        dispatch_requested=presence[DISPATCH_REQUEST],
        implementor_final=presence[IMPLEMENTOR_FINAL],
        reviewer_final=presence[REVIEWER_FINAL],
        close_requested=presence[CLOSE_REQUEST],
        implementor_temp=presence[IMPLEMENTOR_TEMP],
        reviewer_temp=presence[REVIEWER_TEMP],
    )


def remove_exact(coordination_directory: Path, names: Iterable[str]) -> list[str]:
    removed: list[str] = []
    for name in names:
        if name not in PROTOCOL_FILES:
            raise ProtocolError(f"refusing to remove unknown protocol path: {name}")
        path = coordination_directory / name
        kind = _path_kind(path)
        if kind == "absent":
            continue
        if kind == "directory":
            raise ProtocolError(f"refusing to remove protocol directory: {path}")
        try:
            path.unlink()
        except FileNotFoundError:
            # Another compliant actor may complete the same removal between
            # lstat() and unlink().  The requested postcondition is satisfied.
            continue
        except OSError as exc:
            raise ProtocolError(f"cannot remove {path}: {exc}") from exc
        removed.append(name)
    return removed


def create_empty_marker(coordination_directory: Path, name: str) -> None:
    if name not in MARKER_FILES:
        raise ProtocolError(f"refusing to create non-marker path: {name}")

    path = coordination_directory / name
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = None
    try:
        descriptor = os.open(str(path), flags, 0o600)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != 0:
            raise ProtocolError(f"created marker is not an empty ordinary file: {path}")
    except FileExistsError as exc:
        raise ProtocolError(f"marker already exists: {path}") from exc
    except OSError as exc:
        raise ProtocolError(f"cannot create marker {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_channel(coordination_directory: Path, name: str) -> str:
    if name not in (IMPLEMENTOR_FINAL, REVIEWER_FINAL):
        raise ProtocolError(f"refusing to read non-channel path: {name}")
    path = coordination_directory / name
    if _path_kind(path) != "file":
        raise ProtocolError(f"required channel is absent: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProtocolError(f"cannot read UTF-8 channel {path}: {exc}") from exc


def require_nonempty_channel(coordination_directory: Path, name: str) -> str:
    body = read_channel(coordination_directory, name)
    if not body.strip():
        raise ProtocolError(
            f"channel must contain a non-empty message: {coordination_directory / name}"
        )
    return body


def write_channel_temp(coordination_directory: Path, name: str, body: str) -> None:
    if name not in (IMPLEMENTOR_TEMP, REVIEWER_TEMP):
        raise ProtocolError(f"refusing to write non-temp channel path: {name}")
    if not body.strip():
        raise ProtocolError("channel message must not be empty")

    path = coordination_directory / name
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    descriptor = None
    try:
        descriptor = os.open(str(path), flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as channel:
            descriptor = None
            channel.write(body)
            channel.flush()
            os.fsync(channel.fileno())
    except FileExistsError as exc:
        raise ProtocolError(f"temporary channel already exists: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise ProtocolError(f"cannot write temporary channel {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def promote_channel(
    coordination_directory: Path, temp_name: str, final_name: str
) -> None:
    allowed_pairs = {
        (IMPLEMENTOR_TEMP, IMPLEMENTOR_FINAL),
        (REVIEWER_TEMP, REVIEWER_FINAL),
    }
    if (temp_name, final_name) not in allowed_pairs:
        raise ProtocolError(
            f"refusing unsupported channel promotion: {temp_name} -> {final_name}"
        )
    temp_path = coordination_directory / temp_name
    final_path = coordination_directory / final_name
    if _path_kind(temp_path) != "file":
        raise ProtocolError(f"temporary channel is absent: {temp_path}")
    try:
        if not temp_path.read_text(encoding="utf-8").strip():
            raise ProtocolError(f"temporary channel must not be empty: {temp_path}")
    except (OSError, UnicodeError) as exc:
        raise ProtocolError(
            f"cannot read temporary channel {temp_path}: {exc}"
        ) from exc
    if _path_kind(final_path) != "absent":
        raise ProtocolError(f"final channel already exists: {final_path}")
    try:
        os.replace(str(temp_path), str(final_path))
    except OSError as exc:
        raise ProtocolError(
            f"cannot publish channel {temp_path} -> {final_path}: {exc}"
        ) from exc


def atomic_write(path: Path, body: str) -> None:
    """Publish complete metadata without exposing a partially written final file."""
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def service_directory(coordination_directory: Path) -> Path:
    root = coordination_directory / SERVICE_DIRECTORY
    for directory in (root, root / "sessions"):
        if directory.is_symlink():
            raise ProtocolError(
                f"protocol directory must not be a symlink: {directory}"
            )
        directory.mkdir(exist_ok=True)
    if not (root / ".gitignore").exists():
        atomic_write(root / ".gitignore", "*\n")
    return root


def open_session(coordination_directory: Path) -> Path:
    directory = (
        service_directory(coordination_directory) / "sessions" / uuid.uuid4().hex
    )
    directory.mkdir()
    return directory


def resolve_session(coordination_directory: Path, session: str) -> Path:
    root = service_directory(coordination_directory) / "sessions"
    candidate = Path(session)
    if not candidate.is_absolute():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", session):
            raise ProtocolError(
                "invalid session ID; use the ID returned by open-session"
            )
        candidate = root / session
    if candidate.is_symlink() or candidate.parent.resolve() != root.resolve():
        raise ProtocolError(f"session must belong to {root}: {session}")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ProtocolError(
            f"session does not exist: {session}; use open-session first"
        ) from exc
    if not resolved.is_dir():
        raise ProtocolError(f"session is not a directory: {session}")
    return resolved


def read_session_state(directory: Path) -> dict[str, Any]:
    path = directory / STATE_FILE
    kind = _path_kind(path)
    if kind == "absent":
        if _path_kind(directory) != "directory":
            raise ProtocolError(
                f"session directory is missing or not a directory: {directory}"
            )
        return {"status": "open", "worker_handle": None, "error": None}
    if kind != "file":
        raise ProtocolError(f"session state must be an ordinary file: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProtocolError(f"cannot read session state {path}: {exc}") from exc
    if not isinstance(state, dict) or state.get("status") not in ("open", "closed"):
        raise ProtocolError(f"invalid session status in {path}")
    if "worker_handle" not in state:
        raise ProtocolError(f"session state is missing worker_handle: {path}")
    handle = state.get("worker_handle")
    if handle is not None and (not isinstance(handle, str) or not handle.strip()):
        raise ProtocolError(f"invalid worker handle in {path}")
    return state


def save_session_state(directory: Path, state: dict[str, Any]) -> None:
    atomic_write(directory / STATE_FILE, json.dumps(state, indent=2) + "\n")


def marker_present(directory: Path, name: str) -> bool:
    metadata = _inspect_path(directory / name)
    if metadata is None:
        return False
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size:
        raise ProtocolError(
            f"marker must be an empty ordinary file: {directory / name}"
        )
    return True


def session_closing(directory: Path) -> bool:
    return (
        marker_present(directory, CLOSE_REQUEST)
        or read_session_state(directory)["status"] == "closed"
    )


def require_open_session(directory: Path) -> None:
    if session_closing(directory):
        raise ProtocolError(
            "session is closing or closed; wait-for-close instead of publishing"
        )


def session_info(directory: Path) -> dict[str, Any]:
    state = read_session_state(directory)
    return {
        "session_id": directory.name,
        "session_directory": str(directory),
        **{key: value for key, value in state.items() if key != "status"},
        "session_status": state["status"],
        "close_requested": marker_present(directory, CLOSE_REQUEST),
        "review_pending": marker_present(directory, REVIEW_LOCK),
        "dispatch_requested": marker_present(directory, DISPATCH_REQUEST),
    }


def load_message_input(
    message: Optional[str],  # noqa: UP045
    message_file: Optional[str],  # noqa: UP045
    message_stdin: bool,
) -> str:
    if message is not None:
        body = message
    elif message_file is not None:
        source = Path(message_file)
        if not source.is_absolute():
            raise ProtocolError("message file must be an absolute path")
        try:
            body = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ProtocolError(f"cannot read message file {source}: {exc}") from exc
    elif message_stdin:
        body = sys.stdin.read()
    else:
        raise ProtocolError("message source is required")
    if not body.strip():
        raise ProtocolError("message must not be empty")
    return body


def emit(status: str, **fields: Any) -> None:
    payload = {"status": status}
    payload.update(fields)
    print(json.dumps(payload, sort_keys=True), flush=True)


def fail(error: BaseException) -> int:
    payload = {"status": "error", "message": str(error)}
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)
    return 2
