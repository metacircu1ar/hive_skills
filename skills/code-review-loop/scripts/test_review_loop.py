"""Deterministic tests for the code-review-loop role scripts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Optional
from unittest import mock

import implementor_loop
import review_loop_protocol
import reviewer_loop
from review_loop_protocol import (
    DISPATCH_REQUEST,
    IMPLEMENTOR_FINAL,
    IMPLEMENTOR_TEMP,
    POLL_INTERVAL_SECONDS,
    PROTOCOL_FILES,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    REVIEWER_TEMP,
    ProtocolError,
    create_empty_marker,
    remove_exact,
    snapshot,
)


class BackgroundCall:
    def __init__(self, target: Callable[[], None]) -> None:
        self.error: Optional[BaseException] = None  # noqa: UP045

        def invoke() -> None:
            try:
                target()
            except Exception as exc:  # noqa: BLE001 - forward background failures
                self.error = exc

        self.thread = threading.Thread(target=invoke, daemon=True)
        self.thread.start()

    def assert_running(self, testcase: unittest.TestCase) -> None:
        testcase.assertTrue(self.thread.is_alive(), "blocking wait returned too early")

    def join_cleanly(self, testcase: unittest.TestCase) -> None:
        self.thread.join(timeout=2)
        testcase.assertFalse(self.thread.is_alive(), "blocking wait did not finish")
        if self.error is not None:
            raise self.error


class ReviewLoopScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name).resolve()
        self.coordination_directory = review_loop_protocol.open_session(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, body: str = "") -> Path:
        path = self.coordination_directory / name
        path.write_text(body, encoding="utf-8")
        return path

    def session_arguments(self, arguments: tuple[str, ...]) -> list[str]:
        args = list(arguments)
        if "--coordination-dir" in args:
            index = args.index("--coordination-dir") + 1
            args[index] = str(self.workspace)
            args.extend(("--session", self.coordination_directory.name))
        return args

    def start_cli(self, script_name: str, *arguments: str) -> subprocess.Popen[str]:
        arguments = self.session_arguments(arguments)
        script = Path(__file__).resolve().parent / script_name
        return subprocess.Popen(
            [sys.executable, str(script), *arguments],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def run_cli(
        self,
        script_name: str,
        *arguments: str,
        input_text: Optional[str] = None,  # noqa: UP045
    ) -> dict[str, object]:
        arguments = self.session_arguments(arguments)
        script = Path(__file__).resolve().parent / script_name
        completed = subprocess.run(
            [sys.executable, str(script), *arguments],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_poll_interval_is_one_second(self) -> None:
        self.assertEqual(POLL_INTERVAL_SECONDS, 1.0)

    def test_marker_creation_does_not_require_a_post_creation_path_lookup(self) -> None:
        with mock.patch.object(
            Path,
            "lstat",
            side_effect=AssertionError("marker creation re-inspected its path"),
        ):
            create_empty_marker(self.coordination_directory, REVIEW_LOCK)

        self.assertTrue((self.coordination_directory / REVIEW_LOCK).exists())

    def test_cleanup_tolerates_a_path_disappearing_before_unlink(self) -> None:
        lock = self.write(REVIEW_LOCK)
        real_unlink = Path.unlink

        def disappear_then_report_missing(path: Path) -> None:
            real_unlink(path)
            raise FileNotFoundError

        with mock.patch.object(
            Path, "unlink", autospec=True, side_effect=disappear_then_report_missing
        ):
            removed = remove_exact(self.coordination_directory, (REVIEW_LOCK,))

        self.assertEqual(removed, [])
        self.assertFalse(lock.exists())

    def test_prepare_context_removes_only_implementor_outputs(self) -> None:
        self.write(IMPLEMENTOR_TEMP, "partial")
        self.write(IMPLEMENTOR_FINAL, "stale")
        self.write(DISPATCH_REQUEST)
        unrelated = self.write("keep-me.txt", "keep")

        implementor_loop.prepare_context(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertFalse(state.implementor_temp)
        self.assertFalse(state.implementor_final)
        self.assertFalse(state.dispatch_requested)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_prepare_context_rejects_unacknowledged_feedback(self) -> None:
        implementor_final = self.write(IMPLEMENTOR_FINAL, "reviewed context")
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")

        with self.assertRaisesRegex(ProtocolError, "feedback is acknowledged"):
            implementor_loop.prepare_context(self.coordination_directory)

        self.assertEqual(
            implementor_final.read_text(encoding="utf-8"), "reviewed context"
        )
        self.assertEqual(reviewer_final.read_text(encoding="utf-8"), "NO_FINDINGS")

    def test_publish_context_atomically_replaces_implementor_output(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "old context")

        implementor_loop.publish_context(self.coordination_directory, "new context")

        state = snapshot(self.coordination_directory)
        self.assertFalse(state.implementor_temp)
        self.assertTrue(state.implementor_final)
        self.assertEqual(
            (self.coordination_directory / IMPLEMENTOR_FINAL).read_text(
                encoding="utf-8"
            ),
            "new context",
        )

    def test_publish_context_cli_accepts_stdin_without_exposing_a_path(self) -> None:
        process = self.start_cli(
            "implementor_loop.py",
            "publish-context",
            "--coordination-dir",
            str(self.coordination_directory),
            "--message-stdin",
        )
        stdout, stderr = process.communicate(input="complete context", timeout=3)

        self.assertEqual(process.returncode, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["event"], "context_published")
        self.assertNotIn("message_path", payload)
        self.assertEqual(
            (self.coordination_directory / IMPLEMENTOR_FINAL).read_text(
                encoding="utf-8"
            ),
            "complete context",
        )

    def test_request_review_creates_lock_and_is_replay_safe(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")

        implementor_loop.request_review(self.coordination_directory)
        implementor_loop.request_review(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertTrue(state.review_lock)
        self.assertTrue(state.implementor_final)
        self.assertTrue(state.dispatch_requested)

    def test_submission_replays_after_interruption_between_dispatch_and_lock(
        self,
    ) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        real_create = create_empty_marker

        def interrupt_before_lock(directory, name):
            if name == REVIEW_LOCK:
                raise OSError("interrupted")
            real_create(directory, name)

        with (
            mock.patch.object(
                implementor_loop, "create_empty_marker", interrupt_before_lock
            ),
            self.assertRaisesRegex(OSError, "interrupted"),
        ):
            implementor_loop.request_review(self.coordination_directory)
        state = snapshot(self.coordination_directory)
        self.assertTrue(state.dispatch_requested)
        self.assertFalse(state.review_lock)
        implementor_loop.request_review(self.coordination_directory)
        self.assertTrue(snapshot(self.coordination_directory).review_lock)

    def test_implementor_wait_stays_blocked_until_review_result(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        with mock.patch.object(implementor_loop, "emit") as emit_mock:
            call = BackgroundCall(
                lambda: implementor_loop.wait_for_review(
                    self.coordination_directory, poll_interval=0.01
                )
            )

            time.sleep(0.04)
            call.assert_running(self)
            emit_mock.assert_not_called()
            self.write(REVIEWER_FINAL, "finding")
            lock.unlink()

            call.join_cleanly(self)
            self.assertEqual(emit_mock.call_count, 1)

    def test_implementor_cli_process_blocks_until_review_result(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        process = self.start_cli(
            "implementor_loop.py",
            "wait-for-review",
            "--coordination-dir",
            str(self.coordination_directory),
        )
        try:
            time.sleep(0.2)
            self.assertIsNone(
                process.poll(), "implementor CLI returned after an idle poll"
            )
            self.write(REVIEWER_FINAL, "NO_FINDINGS")
            lock.unlink()
            stdout, stderr = process.communicate(timeout=3)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

        self.assertEqual(process.returncode, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["event"], "review_result")
        self.assertEqual(payload["message"], "NO_FINDINGS")
        self.assertEqual(payload["result_kind"], "no_findings")
        self.assertNotIn("message_path", payload)

    def test_implementor_wait_never_submits_an_unrequested_round(self) -> None:
        with self.assertRaisesRegex(ProtocolError, "no review requested"):
            implementor_loop.wait_for_review(self.coordination_directory)
        self.write(IMPLEMENTOR_FINAL, "context")
        with self.assertRaisesRegex(ProtocolError, "no review requested"):
            implementor_loop.wait_for_review(self.coordination_directory)
        self.assertFalse(snapshot(self.coordination_directory).review_lock)

    def test_implementor_wait_reports_deleted_lock_without_recreating_it(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        with self.assertRaisesRegex(ProtocolError, "no review requested"):
            implementor_loop.wait_for_review(
                self.coordination_directory,
                sleep_fn=lambda _: remove_exact(
                    self.coordination_directory, (REVIEW_LOCK,)
                ),
            )
        self.assertFalse(snapshot(self.coordination_directory).review_lock)

    def test_reviewer_read_returns_immediately_without_request(self) -> None:
        with mock.patch.object(reviewer_loop, "emit") as emit_mock:
            reviewer_loop.read_request(self.coordination_directory)
            self.assertEqual(emit_mock.call_count, 1)
            self.assertEqual(emit_mock.call_args.kwargs["event"], "no_request")

    def test_reviewer_cli_reads_once_and_exits_even_when_idle(self) -> None:
        self.assertEqual(
            self.run_cli(
                "reviewer_loop.py",
                "read-request",
                "--coordination-dir",
                str(self.coordination_directory),
            )["event"],
            "no_request",
        )
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        payload = self.run_cli(
            "reviewer_loop.py",
            "read-request",
            "--coordination-dir",
            str(self.coordination_directory),
        )
        self.assertEqual(payload["event"], "review_request")
        self.assertEqual(payload["message"], "context")
        self.assertNotIn("message_path", payload)

    def test_reviewer_cleans_orphaned_response_temp(self) -> None:
        reviewer_temp = self.write(REVIEWER_TEMP, "partial")
        self.write(IMPLEMENTOR_FINAL, "context")

        with mock.patch.object(reviewer_loop, "emit") as emit_mock:
            reviewer_loop.read_request(self.coordination_directory)

        self.assertFalse(reviewer_temp.exists())
        self.assertEqual(emit_mock.call_args.kwargs["event"], "no_request")

    def test_reviewer_read_recovers_a_published_response_without_repeating_it(
        self,
    ) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")

        with mock.patch.object(reviewer_loop, "emit") as emit_mock:
            reviewer_loop.read_request(self.coordination_directory)

        self.assertEqual(emit_mock.call_args.kwargs["event"], "review_ready_to_release")
        self.assertEqual(reviewer_final.read_text(encoding="utf-8"), "NO_FINDINGS")

    def test_prepare_response_removes_only_unpublished_reviewer_temp(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        self.write(REVIEWER_TEMP, "partial")

        reviewer_loop.prepare_response(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertTrue(state.review_lock)
        self.assertTrue(state.implementor_final)
        self.assertFalse(state.reviewer_temp)
        self.assertFalse(state.reviewer_final)

    def test_prepare_response_does_not_replace_a_published_response(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")

        with self.assertRaisesRegex(ProtocolError, "already published"):
            reviewer_loop.prepare_response(self.coordination_directory)

        self.assertEqual(reviewer_final.read_text(encoding="utf-8"), "NO_FINDINGS")

    def test_prepare_response_tolerates_lock_loss_during_cleanup(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        self.write(REVIEWER_TEMP, "partial")
        real_remove_exact = review_loop_protocol.remove_exact

        def remove_then_lose_lock(
            coordination_directory: Path, names: tuple[str, ...]
        ) -> list[str]:
            removed = real_remove_exact(coordination_directory, names)
            lock.unlink()
            return removed

        with mock.patch.object(
            reviewer_loop, "remove_exact", side_effect=remove_then_lose_lock
        ):
            reviewer_loop.prepare_response(self.coordination_directory)

        self.assertFalse(snapshot(self.coordination_directory).reviewer_temp)

    def test_publish_response_aborts_temp_if_lock_disappears(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        real_write = reviewer_loop.write_channel_temp

        def write_then_lose_lock(*args, **kwargs) -> None:
            real_write(*args, **kwargs)
            lock.unlink()

        with (
            mock.patch.object(
                reviewer_loop, "write_channel_temp", side_effect=write_then_lose_lock
            ),
            mock.patch.object(reviewer_loop, "emit") as emit_mock,
        ):
            reviewer_loop.publish_response(self.coordination_directory, "finding")

        self.assertFalse(snapshot(self.coordination_directory).reviewer_temp)
        self.assertFalse(snapshot(self.coordination_directory).reviewer_final)
        self.assertEqual(emit_mock.call_args.kwargs["event"], "response_aborted")

    def test_publish_response_atomically_publishes_before_unlock(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)

        reviewer_loop.publish_response(self.coordination_directory, "finding")

        state = snapshot(self.coordination_directory)
        self.assertFalse(state.review_lock)
        self.assertFalse(state.reviewer_temp)
        self.assertTrue(state.reviewer_final)
        self.assertEqual(
            (self.coordination_directory / REVIEWER_FINAL).read_text(encoding="utf-8"),
            "finding",
        )

    def test_publish_response_rejects_a_missing_request(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")

        with self.assertRaisesRegex(ProtocolError, "without a review lock"):
            reviewer_loop.publish_response(self.coordination_directory, "finding")

    def test_publish_response_cli_accepts_stdin(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        process = self.start_cli(
            "reviewer_loop.py",
            "publish-response",
            "--coordination-dir",
            str(self.coordination_directory),
            "--message-stdin",
        )
        stdout, stderr = process.communicate(input="NO_FINDINGS", timeout=3)

        self.assertEqual(process.returncode, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["event"], "response_published")
        self.assertNotIn("message_path", payload)
        self.assertFalse(snapshot(self.coordination_directory).review_lock)

    def test_release_review_publishes_before_unlock(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "NO_FINDINGS")
        self.write(REVIEW_LOCK)

        reviewer_loop.release_review(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertFalse(state.review_lock)
        self.assertTrue(state.reviewer_final)

    def test_release_review_rejects_a_missing_response_while_locked(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)

        with self.assertRaisesRegex(ProtocolError, "required channel is absent"):
            reviewer_loop.release_review(self.coordination_directory)

    def test_release_review_accepts_an_already_missing_lock(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "NO_FINDINGS")

        reviewer_loop.release_review(self.coordination_directory)

        self.assertTrue(snapshot(self.coordination_directory).reviewer_final)

    def test_release_review_tolerates_immediate_feedback_consumption(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")
        real_remove_exact = review_loop_protocol.remove_exact

        def remove_then_consume(
            coordination_directory: Path, names: tuple[str, ...]
        ) -> list[str]:
            removed = real_remove_exact(coordination_directory, names)
            self.assertFalse(lock.exists())
            reviewer_final.unlink()
            return removed

        with mock.patch.object(
            reviewer_loop, "remove_exact", side_effect=remove_then_consume
        ):
            reviewer_loop.release_review(self.coordination_directory)

    def test_release_review_replay_tolerates_consumption_after_snapshot(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")
        real_snapshot = reviewer_loop.snapshot

        def snapshot_then_consume(coordination_directory: Path):
            state = real_snapshot(coordination_directory)
            reviewer_final.unlink()
            return state

        with mock.patch.object(
            reviewer_loop, "snapshot", side_effect=snapshot_then_consume
        ):
            reviewer_loop.release_review(self.coordination_directory)

        self.assertFalse(reviewer_final.exists())

    def test_feedback_acknowledgement_removes_an_unlocked_final(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "finding")

        implementor_loop.acknowledge_feedback(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertTrue(state.implementor_final)
        self.assertFalse(state.reviewer_final)

    def test_feedback_acknowledgement_rejects_a_locked_final(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "finding")
        self.write(REVIEW_LOCK)

        with self.assertRaisesRegex(ProtocolError, "while lock exists"):
            implementor_loop.acknowledge_feedback(self.coordination_directory)

    def test_feedback_acknowledgement_is_replay_safe(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")

        implementor_loop.acknowledge_feedback(self.coordination_directory)

    def test_invalid_cli_arguments_emit_structured_error(self) -> None:
        process = self.start_cli("implementor_loop.py", "wait-for-review")
        stdout, stderr = process.communicate(timeout=2)

        self.assertEqual(process.returncode, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["status"], "error")

    def test_coordination_resolution_wraps_runtime_error(self) -> None:
        with (
            mock.patch.object(Path, "resolve", side_effect=RuntimeError("loop")),
            self.assertRaisesRegex(ProtocolError, "cannot resolve"),
        ):
            review_loop_protocol.resolve_coordination_directory(
                str(self.coordination_directory)
            )

    def test_cleanup_refuses_a_directory_at_a_protocol_path(self) -> None:
        (self.coordination_directory / REVIEW_LOCK).mkdir()
        with self.assertRaises(ProtocolError):
            remove_exact(self.coordination_directory, PROTOCOL_FILES)


if __name__ == "__main__":
    unittest.main()
