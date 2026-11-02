"""Process checks for shared sessions and the dispatcher's executable lifecycle policy."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import dispatcher_loop as dispatcher
import implementor_loop as implementor
import review_loop_protocol as protocol


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.coord = Path(self.tmp.name).resolve()
        self.scripts = Path(__file__).resolve().parent
        self.children = []

    def tearDown(self):
        for child in self.children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=3)
        self.tmp.cleanup()

    def command(self, role, command, session=None, *args):
        result = [
            sys.executable,
            str(self.scripts / (role + "_loop.py")),
            command,
            "--coordination-dir",
            str(self.coord),
        ]
        if session is not None:
            result += ["--session", session]
        return result + list(args)

    def call(self, role, command, session=None, *args, body=None, code=0):
        result = subprocess.run(
            self.command(role, command, session, *args),
            input=body,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stderr)
        return json.loads(result.stdout if code == 0 else result.stderr)

    def background(self, role, command, session=None, *args):
        child = subprocess.Popen(
            self.command(role, command, session, *args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.children.append(child)
        return child

    def receive(self, child):
        stdout, stderr = child.communicate(timeout=4)
        self.assertEqual(child.returncode, 0, stderr)
        return json.loads(stdout)

    def open(self):
        return self.call("implementor", "open-session")["session_id"]

    def submit(self, session, body):
        self.call("implementor", "publish-context", session, "--message", body)
        self.call("implementor", "request-review", session)

    def reconcile(self, session, status, *args):
        return self.call(
            "dispatcher", "reconcile", session, "--worker-status", status, *args
        )

    def bind(self, session, handle):
        return self.call("dispatcher", "bind", session, "--worker-handle", handle)

    def test_stray_entries_do_not_block_start_status_wait_or_shutdown(self):
        sid = self.open()
        root = protocol.service_directory(self.coord) / "sessions"
        (root / ".DS_Store").write_bytes(b"Finder metadata")
        (root / "stray_file").write_text("not a session")
        (root / ".hidden_directory").mkdir()
        self.assertEqual(
            [row["session_id"] for row in self.call("dispatcher", "start")["sessions"]],
            [sid],
        )
        self.assertEqual(
            [
                row["session_id"]
                for row in self.call("dispatcher", "status")["sessions"]
            ],
            [sid],
        )
        self.submit(sid, "task")
        self.assertEqual(
            self.call("dispatcher", "wait")["sessions"][0]["session_id"], sid
        )
        self.assertEqual(
            self.call("dispatcher", "shutdown", None, "--statuses-stdin", body="{}")[
                "event"
            ],
            "service_stopped",
        )

    def test_cleanup_deletes_closed_sessions_and_keeps_open_and_pending_close(self):
        self.call("dispatcher", "start")
        closed, active, closing = [self.open() for _ in range(3)]
        self.submit(closed, "canceled request retained until cleanup")
        self.call("implementor", "close-session", closed)
        self.reconcile(closed, "gone")
        self.call("implementor", "wait-for-close", closed)
        self.call("implementor", "close-session", closing)
        result = self.call("dispatcher", "cleanup-closed")
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(
            {
                row["session_id"]
                for row in self.call("dispatcher", "status")["sessions"]
            },
            {active, closing},
        )
        self.call("implementor", "status", closed, code=2)
        self.assertEqual(self.call("dispatcher", "cleanup-closed")["deleted_count"], 0)
        self.submit(active, "still dispatchable")
        events = self.call("dispatcher", "wait")["sessions"]
        self.assertEqual({row["session_id"] for row in events}, {active, closing})

    def test_missing_state_defaults_to_open_only_for_an_existing_session(self):
        sid = self.open()
        directory = protocol.resolve_session(self.coord, sid)
        self.assertEqual(protocol.read_session_state(directory)["status"], "open")
        directory.rmdir()
        with self.assertRaisesRegex(
            protocol.ProtocolError, "session directory is missing"
        ):
            protocol.read_session_state(directory)

    def test_close_wait_errors_if_cleanup_removes_session_between_polls(self):
        sid = self.open()
        directory = protocol.resolve_session(self.coord, sid)
        self.call("implementor", "close-session", sid)
        polls = 0

        def close_and_delete_before_next_poll(_):
            nonlocal polls
            polls += 1
            self.assertEqual(polls, 1, "waiter kept polling a deleted session")
            self.assertEqual(self.reconcile(sid, "gone")["action"], "mark_closed")
            self.assertEqual(
                self.call("dispatcher", "cleanup-closed")["deleted_count"], 1
            )

        with self.assertRaisesRegex(
            protocol.ProtocolError, "session directory is missing"
        ):
            implementor.wait_for_close(
                directory, sleep_fn=close_and_delete_before_next_poll
            )
        self.assertEqual(polls, 1)

    def test_cleanup_reports_broken_sessions_without_deleting_them(self):
        closed, broken = self.open(), self.open()
        self.call("implementor", "close-session", closed)
        self.reconcile(closed, "gone")
        broken_dir = protocol.resolve_session(self.coord, broken)
        (broken_dir / protocol.STATE_FILE).write_text("{broken")
        result = self.call("dispatcher", "cleanup-closed", code=2)
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["errors"][0]["session_id"], broken)
        self.assertTrue(broken_dir.is_dir())

    def test_interrupted_cleanup_is_outside_scans_and_retryable(self):
        sid = self.open()
        self.call("implementor", "close-session", sid)
        self.reconcile(sid, "gone")

        def partial_deletion(path):
            self.assertEqual(dispatcher.sessions(self.coord), [])
            (path / protocol.STATE_FILE).unlink()
            raise OSError("interrupted deletion")

        with mock.patch.object(dispatcher.shutil, "rmtree", partial_deletion):
            result = dispatcher.cleanup_closed(self.coord)
        self.assertEqual(result["deleted_count"], 0)
        self.assertIn("interrupted deletion", result["errors"][0]["error"])
        self.assertEqual(dispatcher.sessions(self.coord), [])
        result = self.call("dispatcher", "cleanup-closed")
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(
            list(protocol.service_directory(self.coord).glob(".deleting-*")), []
        )

    def test_scan_ignores_a_session_retired_while_its_state_is_being_read(self):
        sid = self.open()
        self.call("implementor", "close-session", sid)
        self.reconcile(sid, "gone")

        def retire_before_read(directory):
            directory.rename(
                protocol.service_directory(self.coord) / (".deleting-" + sid)
            )
            return protocol.session_info(directory)

        with mock.patch.object(dispatcher, "session_info", retire_before_read):
            self.assertEqual(dispatcher.sessions(self.coord), [])
        self.assertEqual(self.call("dispatcher", "cleanup-closed")["deleted_count"], 1)

    def test_broken_session_is_reported_while_healthy_sessions_continue(self):
        broken, healthy = self.open(), self.open()
        broken_dir = protocol.resolve_session(self.coord, broken)
        (broken_dir / protocol.STATE_FILE).write_text("{broken")
        for command in ("start", "status"):
            rows = self.call("dispatcher", command)["sessions"]
            error = next(row for row in rows if row["session_id"] == broken)
            self.assertEqual(error["event"], "session_error")
            self.assertEqual(error["action"], "report")
            self.assertNotIn("worker_handle", error)
            self.assertIn(healthy, {row["session_id"] for row in rows})
        self.submit(healthy, "healthy review")
        events = self.call("dispatcher", "wait", None, "--reported-error", broken)[
            "sessions"
        ]
        self.assertEqual([row["session_id"] for row in events], [healthy])
        self.bind(healthy, "healthy-worker")
        self.call("implementor", "close-session", healthy)
        result = self.call(
            "dispatcher",
            "shutdown",
            None,
            "--statuses-stdin",
            body=json.dumps({healthy: "stopped"}),
        )
        self.assertEqual(result["event"], "shutdown_pending")
        self.assertEqual(
            self.call("implementor", "status", healthy)["session_status"], "closed"
        )
        self.assertTrue(
            protocol.marker_present(
                protocol.service_directory(self.coord), protocol.DISPATCHER_LOCK
            )
        )
        self.assertEqual(
            next(row for row in result["sessions"] if row["session_id"] == broken)[
                "action"
            ],
            "report",
        )

    def test_errors_complete_wait_and_reported_errors_do_not_block_healthy_sessions(
        self,
    ):
        self.call("dispatcher", "start")
        broken, healthy = self.open(), self.open()
        self.submit(broken, "will be corrupted")
        directory = protocol.resolve_session(self.coord, broken)
        (directory / protocol.IMPLEMENTOR_FINAL).write_bytes(b"\xff")
        # Capture output only after process exit, as a buffered/background host does.
        result = self.call("dispatcher", "wait")
        self.assertEqual(result["sessions"][0]["event"], "session_error")
        self.assertEqual(result["sessions"][0]["session_id"], broken)
        self.assertEqual(result["reported_errors"], [broken])

        waiter = self.background("dispatcher", "wait", None, "--reported-error", broken)
        time.sleep(0.2)
        self.assertIsNone(waiter.poll(), "reported error caused a busy return loop")
        self.submit(healthy, "healthy request")
        result = self.receive(waiter)
        self.assertEqual([row["session_id"] for row in result["sessions"]], [healthy])
        self.assertEqual(result["reported_errors"], [broken])
        self.reconcile(healthy, "gone")
        self.bind(healthy, "healthy-worker")

        other = self.open()
        other_dir = protocol.resolve_session(self.coord, other)
        (other_dir / protocol.STATE_FILE).write_text("{broken")
        result = self.call("dispatcher", "wait", None, "--reported-error", broken)
        self.assertEqual([row["session_id"] for row in result["sessions"]], [other])
        self.assertEqual(result["sessions"][0]["event"], "session_error")
        self.assertEqual(set(result["reported_errors"]), {broken, other})

        # A repaired session still dispatches; its ID leaves the acknowledgement list.
        protocol.atomic_write(
            directory / protocol.IMPLEMENTOR_FINAL, "repaired request"
        )
        result = self.call(
            "dispatcher",
            "wait",
            None,
            "--reported-error",
            broken,
            "--reported-error",
            other,
        )
        self.assertEqual(result["sessions"][0]["event"], "review_submitted")
        self.assertEqual(result["sessions"][0]["session_id"], broken)
        self.assertEqual(result["reported_errors"], [other])
        self.bind(broken, "repaired-worker")
        (directory / protocol.STATE_FILE).write_text("{broken again")
        result = self.call("dispatcher", "wait", None, "--reported-error", other)
        self.assertEqual(result["sessions"][0]["event"], "session_error")
        self.assertEqual(result["sessions"][0]["session_id"], broken)

    def test_reported_context_error_does_not_hide_a_close_request(self):
        self.call("dispatcher", "start")
        sid = self.open()
        self.submit(sid, "will be corrupted")
        directory = protocol.resolve_session(self.coord, sid)
        (directory / protocol.IMPLEMENTOR_FINAL).write_text("")
        result = self.call("dispatcher", "wait")
        self.assertEqual(result["reported_errors"], [sid])
        self.call("implementor", "close-session", sid)
        result = self.call("dispatcher", "wait", None, "--reported-error", sid)
        self.assertEqual(result["sessions"][0]["event"], "close_requested")
        self.assertEqual(result["sessions"][0]["session_id"], sid)
        self.assertEqual(result["reported_errors"], [])

    def test_three_sessions_and_followup_rounds_remain_independent(self):
        self.call("dispatcher", "start")
        ids = [self.open() for _ in range(3)]
        for index, sid in enumerate(ids):
            self.submit(sid, f"task {index}")
        events = self.call("dispatcher", "wait")["sessions"]
        self.assertEqual({row["session_id"] for row in events}, set(ids))
        for index, sid in enumerate(ids):
            self.assertEqual(self.reconcile(sid, "gone")["action"], "launch")
            self.bind(sid, f"worker-{index}")
            self.assertEqual(
                self.call("reviewer", "read-request", sid)["message"], f"task {index}"
            )
        waiters = [
            self.background("implementor", "wait-for-review", sid) for sid in ids
        ]
        for index in (2, 0, 1):
            self.call(
                "reviewer",
                "publish-response",
                ids[index],
                "--message",
                f"finding {index}",
            )
            self.assertEqual(
                self.receive(waiters[index])["message"], f"finding {index}"
            )
            self.call("implementor", "acknowledge-feedback", ids[index])
        for index, sid in enumerate(ids):
            self.submit(sid, f"corrected {index}")
            event = self.call("dispatcher", "wait")["sessions"][0]
            self.assertEqual(event["session_id"], sid)
            self.assertEqual(self.reconcile(sid, "resumable")["action"], "resume")
            self.assertEqual(
                self.call("reviewer", "read-request", sid)["message"],
                f"corrected {index}",
            )
            self.call("reviewer", "publish-response", sid, "--message", "NO_FINDINGS")
            self.assertEqual(
                self.call("implementor", "wait-for-review", sid)["result_kind"],
                "no_findings",
            )
        self.assertEqual(dispatcher.pending_events(self.coord), [])
        handles = [
            row["worker_handle"]
            for row in self.call("dispatcher", "status")["sessions"]
        ]
        self.assertEqual(set(handles), {"worker-0", "worker-1", "worker-2"})

    def test_close_wakes_dispatcher_but_client_waits_for_stop_confirmation(
        self,
    ):
        self.call("dispatcher", "start")
        sid, other = self.open(), self.open()
        self.bind(sid, "idle-worker")
        service = self.background("dispatcher", "wait")
        time.sleep(0.1)
        self.assertIsNone(service.poll())
        self.call("implementor", "close-session", sid)
        client = self.background("implementor", "wait-for-close", sid)
        self.assertEqual(
            self.receive(service)["sessions"][0]["event"], "close_requested"
        )
        self.assertEqual(
            self.call("reviewer", "read-request", sid)["event"], "session_closing"
        )
        self.assertIsNone(client.poll())
        self.assertEqual(self.reconcile(sid, "running")["action"], "stop")
        self.assertEqual(
            self.reconcile(sid, "error", "--error", "stop failed")["action"], "report"
        )
        self.assertEqual(dispatcher.pending_events(self.coord), [])
        self.assertIsNone(client.poll())
        self.assertEqual(self.reconcile(sid, "stopped")["action"], "mark_closed")
        self.assertEqual(self.receive(client)["event"], "session_closed")
        self.assertEqual(
            self.call("implementor", "status", other)["session_status"], "open"
        )
        self.call("implementor", "request-review", sid, code=2)

    def test_dispatch_claim_is_replay_safe_and_survives_fast_followup_before_bind(self):
        self.call("dispatcher", "start")
        sid = self.open()
        self.submit(sid, "round one")
        self.assertEqual(self.reconcile(sid, "gone")["action"], "launch")
        self.call("implementor", "request-review", sid)
        self.assertEqual(dispatcher.pending_events(self.coord), [])
        self.call("reviewer", "publish-response", sid, "--message", "finding")
        self.call("implementor", "wait-for-review", sid)
        self.call("implementor", "acknowledge-feedback", sid)
        self.submit(sid, "round two before first runtime call returns")
        self.bind(sid, "same-worker")
        self.assertEqual(self.reconcile(sid, "running")["action"], "await_worker")

        # The finishing worker still owns the runtime turn. Its completion event,
        # supplied by the host, removes this deferral; no model status polling.
        waiter = self.background("dispatcher", "wait", None, "--busy-session", sid)
        time.sleep(0.2)
        self.assertIsNone(waiter.poll(), "busy worker caused a repeated dispatch")
        self.assertEqual(self.reconcile(sid, "resumable")["action"], "resume")
        state = self.call("implementor", "status", sid)
        self.assertEqual(state["worker_handle"], "same-worker")
        self.assertFalse(state["dispatch_requested"])
        self.assertEqual(
            self.call("reviewer", "read-request", sid)["message"],
            "round two before first runtime call returns",
        )
        self.call("reviewer", "publish-response", sid, "--message", "NO_FINDINGS")
        self.assertEqual(self.reconcile(sid, "resumable")["action"], "leave")
        # Deferral must never hide closure, even before the caller restarts wait.
        self.call("implementor", "close-session", sid)
        self.assertEqual(
            self.receive(waiter)["sessions"][0]["event"], "close_requested"
        )

    def test_busy_session_does_not_hide_other_requests_or_its_errors(self):
        self.call("dispatcher", "start")
        busy, other = self.open(), self.open()
        self.submit(busy, "busy")
        self.bind(busy, "finishing-worker")
        self.assertEqual(self.reconcile(busy, "running")["action"], "await_worker")
        self.submit(other, "other")
        result = self.call("dispatcher", "wait", None, "--busy-session", busy)
        self.assertEqual([s["session_id"] for s in result["sessions"]], [other])
        self.reconcile(other, "gone")
        directory = protocol.resolve_session(self.coord, busy)
        (directory / protocol.IMPLEMENTOR_FINAL).write_text("")
        result = self.call("dispatcher", "wait", None, "--busy-session", busy)
        self.assertEqual(result["sessions"][0]["event"], "session_error")

    def test_revive_retries_a_claimed_request_without_waking_idle_workers(self):
        self.call("dispatcher", "start")
        idle, pending = self.open(), self.open()
        self.bind(idle, "idle-conversation")
        self.submit(pending, "interrupted launch")
        self.reconcile(pending, "gone")
        self.assertEqual(dispatcher.pending_events(self.coord), [])
        rows = self.call("dispatcher", "start", None, "--revive")["sessions"]
        self.assertEqual({s["session_id"] for s in rows}, {idle, pending})
        self.assertEqual(self.reconcile(idle, "resumable")["action"], "leave")
        self.assertEqual(self.reconcile(idle, "unknown")["action"], "leave")
        self.assertEqual(self.reconcile(pending, "gone")["action"], "launch")
        self.bind(pending, "new-worker")
        self.assertEqual(
            self.call("reviewer", "read-request", pending)["message"],
            "interrupted launch",
        )

    def test_fresh_reviews_close_each_session_and_preserve_each_result(self):
        self.call("dispatcher", "start")
        ids = []
        for index, result in enumerate(("finding", "NO_FINDINGS")):
            sid = self.open()
            ids.append(sid)
            self.submit(
                sid, f"full task, round {index + 1}, prior findings and disposition"
            )
            self.assertEqual(self.reconcile(sid, "gone")["action"], "launch")
            self.bind(sid, f"fresh-worker-{index}")
            self.call("reviewer", "read-request", sid)
            self.call("reviewer", "publish-response", sid, "--message", result)
            self.assertEqual(
                self.call("implementor", "wait-for-review", sid)["message"], result
            )
            self.call("implementor", "close-session", sid)
            self.assertEqual(self.reconcile(sid, "stopped")["action"], "mark_closed")
            self.call("implementor", "wait-for-close", sid)
            self.call(
                "implementor",
                "publish-context",
                sid,
                "--message",
                "another round",
                code=2,
            )
        self.assertNotEqual(*ids)
        rows = self.call("dispatcher", "status")["sessions"]
        self.assertTrue(all(s["session_status"] == "closed" for s in rows))
        self.assertEqual(
            {s["worker_handle"] for s in rows}, {"fresh-worker-0", "fresh-worker-1"}
        )
        self.assertEqual(dispatcher.pending_events(self.coord), [])

    def test_close_cancels_pending_review_without_relocking_or_returning_feedback(self):
        sid = self.open()
        self.bind(sid, "reviewing-worker")
        self.submit(sid, "task")
        client = self.background("implementor", "wait-for-review", sid)
        self.call("implementor", "close-session", sid)
        self.assertEqual(self.receive(client)["event"], "session_closing")
        self.call(
            "reviewer", "publish-response", sid, "--message", "NO_FINDINGS", code=2
        )
        self.assertEqual(self.reconcile(sid, "unknown")["action"], "mark_closed")
        self.assertEqual(
            self.call("implementor", "wait-for-close", sid)["event"], "session_closed"
        )

    def test_worker_already_ended_on_closure_needs_only_stop_confirmation(self):
        sid = self.open()
        self.bind(sid, "completed-but-resumable-worker")
        self.call("implementor", "close-session", sid)
        self.assertEqual(
            self.call("reviewer", "read-request", sid)["event"], "session_closing"
        )
        self.assertEqual(self.reconcile(sid, "stopped")["action"], "mark_closed")
        self.assertEqual(
            self.call("implementor", "wait-for-close", sid)["event"], "session_closed"
        )

    def test_start_recovers_idle_sessions_and_unknown_handles_without_reopening_closed(
        self,
    ):
        self.call("dispatcher", "start")
        idle, submitted, closed = [self.open() for _ in range(3)]
        for sid in (idle, submitted, closed):
            self.bind(sid, "worker-" + sid)
        self.submit(submitted, "pending review")
        self.call("implementor", "close-session", closed)
        self.reconcile(closed, "gone")
        statuses = {idle: "running", submitted: "stopped"}
        pending = self.call(
            "dispatcher",
            "shutdown",
            None,
            "--statuses-stdin",
            body=json.dumps(statuses),
        )
        self.assertEqual(pending["event"], "shutdown_pending")
        self.call("dispatcher", "start", code=2)
        statuses[idle] = "stopped"
        self.assertEqual(
            self.call(
                "dispatcher",
                "shutdown",
                None,
                "--statuses-stdin",
                body=json.dumps(statuses),
            )["event"],
            "service_stopped",
        )
        restarted = self.call("dispatcher", "start")
        self.assertEqual(
            {row["session_id"] for row in restarted["sessions"]}, {idle, submitted}
        )
        self.assertEqual(self.reconcile(idle, "resumable")["action"], "leave")
        self.assertEqual(self.reconcile(submitted, "unknown")["action"], "replace")
        self.bind(submitted, "replacement")
        self.assertEqual(
            self.call("reviewer", "read-request", submitted)["message"],
            "pending review",
        )
        self.call("dispatcher", "start", code=2)
        self.assertEqual(
            len(self.call("dispatcher", "start", None, "--revive")["sessions"]), 2
        )

    def test_recovery_preserves_response_and_prioritizes_vanished_worker_close(self):
        sid = self.open()
        self.submit(sid, "task")
        self.bind(sid, "old")
        directory = protocol.resolve_session(self.coord, sid)
        # Simulate a crash between response promotion and release.
        protocol.write_channel_temp(directory, protocol.REVIEWER_TEMP, "NO_FINDINGS")
        protocol.promote_channel(
            directory, protocol.REVIEWER_TEMP, protocol.REVIEWER_FINAL
        )
        self.assertEqual(self.reconcile(sid, "unknown")["action"], "replace")
        self.bind(sid, "new")
        self.assertEqual(
            self.call("reviewer", "read-request", sid)["event"],
            "review_ready_to_release",
        )
        self.call("reviewer", "release-review", sid)
        self.assertEqual(
            self.call("implementor", "wait-for-review", sid)["message"], "NO_FINDINGS"
        )
        self.call("implementor", "close-session", sid)
        self.assertEqual(self.reconcile(sid, "unknown")["action"], "mark_closed")

    def test_launch_failure_waits_for_revive_but_close_is_still_discovered(self):
        sid = self.open()
        self.submit(sid, "task")
        self.assertEqual(
            self.reconcile(sid, "error", "--error", "provider unavailable")["action"],
            "report",
        )
        self.assertEqual(dispatcher.pending_events(self.coord), [])
        self.assertEqual(self.reconcile(sid, "gone")["action"], "launch")
        self.reconcile(sid, "error", "--error", "provider unavailable")
        self.call("implementor", "close-session", sid)
        self.assertEqual(
            dispatcher.pending_events(self.coord)[0]["event"], "close_requested"
        )
        self.assertEqual(self.reconcile(sid, "gone")["action"], "mark_closed")

    def test_all_runtime_decisions_are_helper_owned(self):
        sid = self.open()
        self.bind(sid, "worker")
        self.assertEqual(self.reconcile(sid, "resumable")["action"], "leave")
        self.submit(sid, "task")
        self.assertEqual(self.reconcile(sid, "running")["action"], "await_worker")
        self.assertEqual(self.reconcile(sid, "resumable")["action"], "resume")
        for status, action in (
            ("running", "continue"),
            ("resumable", "resume"),
            ("stopped", "replace"),
            ("gone", "replace"),
            ("unknown", "replace"),
        ):
            self.assertEqual(self.reconcile(sid, status)["action"], action)
        self.call("implementor", "close-session", sid)
        self.assertEqual(self.reconcile(sid, "resumable")["action"], "stop")
        self.assertEqual(self.reconcile(sid, "gone")["action"], "mark_closed")
        self.assertEqual(self.reconcile(sid, "running")["action"], "leave")

    def test_cli_rejects_old_modes_and_cross_directory_session_paths(self):
        sid = self.open()
        self.call("implementor", "startup-cleanup", code=2)
        self.call("reviewer", "read-request", sid, "--fresh", code=2)
        self.call("implementor", "status", "../elsewhere", code=2)
        self.call("implementor", "status", str(self.coord), code=2)
        self.assertEqual(
            (self.coord / protocol.SERVICE_DIRECTORY / ".gitignore").read_text(), "*\n"
        )

    def test_returning_implementor_recovers_context_and_unread_feedback_through_cli(
        self,
    ):
        sid = self.open()
        self.submit(sid, "Repository /example; full task and context")
        self.call("reviewer", "publish-response", sid, "--message", "finding")
        state = self.call("implementor", "status", sid)
        self.assertEqual(
            state["context_message"], "Repository /example; full task and context"
        )
        self.assertFalse(state["review_pending"])
        self.assertTrue(state["feedback_ready"])
        self.assertEqual(
            self.call("implementor", "wait-for-review", sid)["message"], "finding"
        )
        self.call("implementor", "acknowledge-feedback", sid)
        self.assertFalse(self.call("implementor", "status", sid)["feedback_ready"])
        result = self.call("implementor", "wait-for-review", sid, code=2)
        self.assertIn("feedback already acknowledged", result["message"])
        self.assertFalse(self.call("implementor", "status", sid)["review_pending"])


if __name__ == "__main__":
    unittest.main()
