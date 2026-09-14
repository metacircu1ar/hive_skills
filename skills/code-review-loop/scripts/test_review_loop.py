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
    IMPLEMENTOR_FINAL,
    IMPLEMENTOR_TEMP,
    POLL_INTERVAL_SECONDS,
    PROTOCOL_FILES,
    REVIEW_LOCK,
    REVIEWER_FINAL,
    REVIEWER_TEMP,
    ROUND_COMPLETE,
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
        self.coordination_directory = Path(self.temporary.name).resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, body: str = "") -> Path:
        path = self.coordination_directory / name
        path.write_text(body, encoding="utf-8")
        return path

    def start_cli(self, script_name: str, *arguments: str) -> subprocess.Popen[str]:
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

    def test_public_clis_cover_a_clean_round_without_manual_file_operations(
        self,
    ) -> None:
        common = ("--coordination-dir", str(self.coordination_directory))

        self.assertEqual(
            self.run_cli("implementor_loop.py", "startup-cleanup", *common)["event"],
            "startup_cleanup_complete",
        )
        self.assertEqual(
            self.run_cli(
                "implementor_loop.py",
                "publish-context",
                *common,
                "--message-stdin",
                input_text="complete context",
            )["event"],
            "context_published",
        )
        self.run_cli("implementor_loop.py", "request-review", *common)
        request = self.run_cli(
            "reviewer_loop.py", "wait-for-request", *common, "--fresh"
        )
        self.assertEqual(request["message"], "complete context")
        self.run_cli(
            "reviewer_loop.py",
            "publish-response",
            *common,
            "--message-stdin",
            input_text="NO_FINDINGS",
        )
        result = self.run_cli("implementor_loop.py", "wait-for-review", *common)
        self.assertEqual(result["message"], "NO_FINDINGS")
        self.run_cli("implementor_loop.py", "complete", *common)
        self.assertEqual(
            self.run_cli(
                "reviewer_loop.py",
                "wait-for-request",
                *common,
                "--participated",
            )["event"],
            "completion",
        )
        self.run_cli(
            "reviewer_loop.py",
            "acknowledge-completion",
            *common,
            "--participated",
        )
        self.run_cli("implementor_loop.py", "wait-for-completion", *common)
        self.assertEqual(snapshot(self.coordination_directory).present_names(), [])

    def test_startup_cleanup_removes_only_protocol_files(self) -> None:
        for name in PROTOCOL_FILES:
            self.write(name, "" if name in (REVIEW_LOCK, ROUND_COMPLETE) else "stale")
        unrelated = self.write("keep-me.txt", "keep")

        implementor_loop.startup_cleanup(self.coordination_directory)

        self.assertEqual(snapshot(self.coordination_directory).present_names(), [])
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_startup_cleanup_removes_malformed_nonempty_markers(self) -> None:
        lock = self.write(REVIEW_LOCK, "stale lock contents")
        completion = self.write(ROUND_COMPLETE, "stale completion contents")

        with self.assertRaisesRegex(ProtocolError, "marker must be empty"):
            snapshot(self.coordination_directory)

        implementor_loop.startup_cleanup(self.coordination_directory)

        self.assertFalse(lock.exists())
        self.assertFalse(completion.exists())
        self.assertEqual(snapshot(self.coordination_directory).present_names(), [])

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
        unrelated = self.write("keep-me.txt", "keep")

        implementor_loop.prepare_context(self.coordination_directory)

        state = snapshot(self.coordination_directory)
        self.assertFalse(state.implementor_temp)
        self.assertFalse(state.implementor_final)
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

    def test_implementor_wait_recreates_a_missing_lock(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        lock = self.write(REVIEW_LOCK)
        call = BackgroundCall(
            lambda: implementor_loop.wait_for_review(
                self.coordination_directory, poll_interval=0.01
            )
        )

        lock.unlink()
        deadline = time.monotonic() + 1
        while not lock.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(lock.exists(), "missing review lock was not recreated")

        self.write(REVIEWER_FINAL, "NO_FINDINGS")
        lock.unlink()
        call.join_cleanly(self)

    def test_reviewer_wait_stays_blocked_until_valid_request(self) -> None:
        with mock.patch.object(reviewer_loop, "emit") as emit_mock:
            call = BackgroundCall(
                lambda: reviewer_loop.wait_for_request(
                    self.coordination_directory,
                    participated=False,
                    poll_interval=0.01,
                )
            )

            time.sleep(0.04)
            call.assert_running(self)
            emit_mock.assert_not_called()
            self.write(IMPLEMENTOR_FINAL, "context")
            self.write(REVIEW_LOCK)

            call.join_cleanly(self)
            self.assertEqual(emit_mock.call_count, 1)

    def test_reviewer_cli_process_blocks_until_request(self) -> None:
        process = self.start_cli(
            "reviewer_loop.py",
            "wait-for-request",
            "--coordination-dir",
            str(self.coordination_directory),
            "--fresh",
        )
        try:
            time.sleep(0.2)
            self.assertIsNone(
                process.poll(), "reviewer CLI returned after an idle poll"
            )
            self.write(IMPLEMENTOR_FINAL, "context")
            self.write(REVIEW_LOCK)
            stdout, stderr = process.communicate(timeout=3)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

        self.assertEqual(process.returncode, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(payload["event"], "review_request")
        self.assertEqual(payload["message"], "context")
        self.assertNotIn("message_path", payload)

    def test_participating_reviewer_observes_completion(self) -> None:
        self.write(ROUND_COMPLETE)
        reviewer_loop.wait_for_request(
            self.coordination_directory,
            participated=True,
            poll_interval=0.01,
        )

    def test_reviewer_retries_a_transitional_completion_snapshot(self) -> None:
        self.write(REVIEWER_FINAL, "NO_FINDINGS")
        self.write(ROUND_COMPLETE)

        def finish_promotion(_: float) -> None:
            (self.coordination_directory / REVIEWER_FINAL).unlink()

        reviewer_loop.wait_for_request(
            self.coordination_directory,
            participated=True,
            poll_interval=0.01,
            stale_grace=1,
            sleep_fn=finish_promotion,
        )

    def test_participating_reviewer_cleans_orphaned_response_temp(self) -> None:
        reviewer_temp = self.write(REVIEWER_TEMP, "partial")
        self.write(IMPLEMENTOR_FINAL, "context")

        with mock.patch.object(reviewer_loop, "emit") as emit_mock:

            def finish_wait(_: float) -> None:
                if not reviewer_temp.exists():
                    self.write(REVIEW_LOCK)

            reviewer_loop.wait_for_request(
                self.coordination_directory,
                participated=True,
                poll_interval=0.01,
                sleep_fn=finish_wait,
            )

        self.assertFalse(reviewer_temp.exists())
        self.assertEqual(emit_mock.call_args.kwargs["event"], "review_request")

    def test_reviewer_wait_recovers_a_published_response_without_repeating_it(
        self,
    ) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEW_LOCK)
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")

        with mock.patch.object(reviewer_loop, "emit") as emit_mock:
            reviewer_loop.wait_for_request(
                self.coordination_directory,
                participated=False,
                poll_interval=0.01,
            )

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

    def test_completion_requires_exact_no_findings_and_cleans_first(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "NO_FINDINGS\n")

        implementor_loop.complete(self.coordination_directory)

        self.assertEqual(
            snapshot(self.coordination_directory).present_names(), [ROUND_COMPLETE]
        )

    def test_completion_atomically_promotes_the_clean_response_last(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")
        real_replace = implementor_loop.os.replace

        def assert_ready_then_replace(source: str, destination: str) -> None:
            state = snapshot(self.coordination_directory)
            self.assertEqual(state.present_names(), [REVIEWER_FINAL])
            self.assertEqual(reviewer_final.read_bytes(), b"")
            real_replace(source, destination)

        with mock.patch.object(
            implementor_loop.os, "replace", side_effect=assert_ready_then_replace
        ):
            implementor_loop.complete(self.coordination_directory)

        self.assertEqual(
            snapshot(self.coordination_directory).present_names(), [ROUND_COMPLETE]
        )

    def test_completion_recovers_after_interruption_before_atomic_promotion(
        self,
    ) -> None:
        reviewer_final = self.write(REVIEWER_FINAL, "NO_FINDINGS")
        with (
            mock.patch.object(
                implementor_loop.os,
                "replace",
                side_effect=OSError("simulated interruption"),
            ),
            self.assertRaisesRegex(ProtocolError, "cannot publish"),
        ):
            implementor_loop.complete(self.coordination_directory)

        self.assertEqual(reviewer_final.read_bytes(), b"")
        implementor_loop.complete(self.coordination_directory)
        self.assertEqual(
            snapshot(self.coordination_directory).present_names(), [ROUND_COMPLETE]
        )

    def test_completion_replay_accepts_an_existing_marker(self) -> None:
        self.write(ROUND_COMPLETE)

        implementor_loop.complete(self.coordination_directory)

    def test_completion_replay_accepts_an_already_acknowledged_state(self) -> None:
        implementor_loop.complete(self.coordination_directory)

    def test_completion_rejects_findings(self) -> None:
        self.write(IMPLEMENTOR_FINAL, "context")
        self.write(REVIEWER_FINAL, "finding")

        with self.assertRaises(ProtocolError):
            implementor_loop.complete(self.coordination_directory)

    def test_completion_wait_blocks_until_acknowledged(self) -> None:
        marker = self.write(ROUND_COMPLETE)
        call = BackgroundCall(
            lambda: implementor_loop.wait_for_completion(
                self.coordination_directory, poll_interval=0.01
            )
        )

        time.sleep(0.04)
        call.assert_running(self)
        marker.unlink()
        call.join_cleanly(self)

    def test_reviewer_acknowledges_completion_only_after_participation(self) -> None:
        self.write(ROUND_COMPLETE)
        with self.assertRaises(ProtocolError):
            reviewer_loop.acknowledge_completion(
                self.coordination_directory, participated=False
            )

        reviewer_loop.acknowledge_completion(
            self.coordination_directory, participated=True
        )
        self.assertEqual(snapshot(self.coordination_directory).present_names(), [])

        reviewer_loop.acknowledge_completion(
            self.coordination_directory, participated=True
        )

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
            implementor_loop.startup_cleanup(self.coordination_directory)


if __name__ == "__main__":
    unittest.main()
