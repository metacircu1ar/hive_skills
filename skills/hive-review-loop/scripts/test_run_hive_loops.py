#!/usr/bin/env python3
"""Behavioral tests for the Hive-backed review-loop launcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_hive_loops import (  # noqa: E402
    ConfigError,
    load_parallel,
    load_single,
    preflight,
    run_plan,
)


FAKE_REGISTRY = r'''#!/usr/bin/env python3
import json
import sys

agents = [
    {"id": "Implementor", "capabilities": ["act", "read_only"]},
    {"id": "ReviewerA", "capabilities": ["read_only"]},
    {"id": "ReviewerB", "capabilities": ["read_only"]},
    {"id": "ReviewerC", "capabilities": ["read_only"]},
]
if sys.argv[1:] == ["list", "--json"]:
    print(json.dumps({"schemaVersion": 1, "agents": agents}))
    raise SystemExit(0)
if sys.argv[1:2] == ["doctor"]:
    known = {agent["id"] for agent in agents}
    raise SystemExit(0 if all(name in known for name in sys.argv[2:]) else 1)
raise SystemExit(2)
'''


FAKE_WORKFLOW = r'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import time

args = sys.argv[1:]
if args[:2] == ["describe", "implement-and-run-reviewers"]:
    print("implement-and-run-reviewers")
    raise SystemExit(0)

def value(flag, default=None):
    try:
        return args[args.index(flag) + 1]
    except ValueError:
        return default

def append(event):
    log = os.environ.get("HIVE_TEST_EVENT_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(event) + "\n")

if args[:1] == ["cleanup"]:
    run_dir = pathlib.Path(args[1])
    append({"event": "cleanup", "run_dir": str(run_dir)})
    cleanup_exit = int(os.environ.get("HIVE_TEST_CLEANUP_EXIT", "0"))
    if cleanup_exit:
        print("cleanup failed", file=sys.stderr)
        raise SystemExit(cleanup_exit)
    (run_dir / "cleaned.marker").write_text("cleaned\n", encoding="utf-8")
    print("cleaned")
    raise SystemExit(0)

if args[:1] == ["resume"]:
    run_dir = pathlib.Path(args[1])
    prompt = "resume"
    reviewers = "recorded"
    action = "resume"
elif args[:2] == ["run", "implement-and-run-reviewers"]:
    run_dir = pathlib.Path(value("--run-dir"))
    prompt = value("--prompt", "")
    reviewers = value("--reviewers", "")
    implementor = value("--implementor", "")
    repo = value("--repo", "")
    max_rounds = int(value("--max-rounds", "5"))
    include_diff = next((entry.split("=", 1)[1] == "true" for entry in args if entry.startswith("--diff=")), True)
    action = "run"
else:
    raise SystemExit(2)

append({"event": "start", "action": action, "run_dir": str(run_dir), "reviewers": reviewers, "prompt": prompt})
time.sleep(float(os.environ.get("HIVE_TEST_DELAY", "0")))
run_dir.mkdir(parents=True, exist_ok=True)
(run_dir / "rounds").mkdir(exist_ok=True)
if action == "run":
    manifest = {
        "workflow": "implement-and-run-reviewers",
        "params": {
            "implementor": implementor,
            "reviewers": reviewers.split(","),
            "repo": repo,
            "maxRounds": max_rounds,
            "diff": include_diff,
            "prompt": prompt,
        },
    }
    (run_dir / "run.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
approved = os.environ.get("HIVE_TEST_SUMMARY_APPROVED", "")
if approved:
    approved = approved == "true"
else:
    approved = "[FAIL]" not in prompt
summary = {
    "workflow": "implement-and-run-reviewers",
    "runDir": str(run_dir),
    "steps": [],
    "collected": [{
        "path": str(run_dir / "rounds" / "round-1.md"),
        "feedback": "" if approved else "changes requested",
        "total": 2,
        "failed": 0 if approved else 1,
        "approved": approved,
    }],
    "failed": 0,
    "unmetLoops": 0 if approved else 1,
}
summary_mode = os.environ.get("HIVE_TEST_SUMMARY_MODE", "valid")
if summary_mode == "valid":
    (run_dir / "summary.json").write_text(json.dumps(summary) + "\n", encoding="utf-8")
elif summary_mode == "malformed":
    (run_dir / "summary.json").write_text("not json\n", encoding="utf-8")
elif summary_mode != "missing":
    raise RuntimeError(f"unknown HIVE_TEST_SUMMARY_MODE: {summary_mode}")
report = run_dir / "rounds" / "round-1.md"
report.write_text("review report\n", encoding="utf-8")
append({"event": "end", "action": action, "run_dir": str(run_dir)})
print(report)
print(run_dir)
if os.environ.get("HIVE_TEST_TRAILING_STDOUT") == "1":
    print("trailing workflow summary")
default_exit = 0 if approved else 1
raise SystemExit(int(os.environ.get("HIVE_TEST_EXIT_CODE", str(default_exit))))
'''


class HiveLoopLauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.registry = self._executable("fake_registry.py", FAKE_REGISTRY)
        self.workflow = self._executable("fake_workflow.py", FAKE_WORKFLOW)
        self.event_log = self.root / "events.jsonl"
        self.repo_a = self._repo("repo-a")
        self.repo_b = self._repo("repo-b")
        self.repo_c = self._repo("repo-c")
        self.task_source = self.root / "TASK.md"
        self.task_source.write_text("acceptance criteria\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _executable(self, name: str, body: str) -> Path:
        path = self.root / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def _repo(self, name: str) -> Path:
        path = self.root / name
        path.mkdir()
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        return path.resolve()

    def _write_json(self, name: str, payload: dict[str, object]) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def hive(self) -> dict[str, str]:
        return {"workflow_cli": str(self.workflow), "registry_cli": str(self.registry)}

    def single_payload(self, *, failing: bool = False) -> dict[str, object]:
        return {
            "schema_version": 1,
            "hive": self.hive(),
            "repo": str(self.repo_a),
            "run_dir": str(self.root / "single-hive-run"),
            "implementor": "implementor",
            "reviewers": ["reviewera", "ReviewerB"],
            "max_rounds": 4,
            "cleanup_on_success": True,
            "context": {
                "text": "Implement the task" + (" [FAIL]" if failing else ""),
                "sources": [{"path": str(self.task_source), "purpose": "Complete task"}],
            },
        }

    def test_single_run_uses_registry_panel_context_and_cleanup(self) -> None:
        config = self._write_json("single.json", self.single_payload())
        with mock.patch.dict(os.environ, {"HIVE_TEST_EVENT_LOG": str(self.event_log)}):
            plan = preflight(load_single(config), resume=False)
            results, summaries = run_plan(plan, parallel=False, resume=False)

        self.assertIsNone(summaries)
        self.assertEqual(results[0]["status"], "passed")
        self.assertIs(results[0]["consensus_reached"], True)
        self.assertIs(results[0]["consensus_exit_agree"], True)
        self.assertEqual(results[0]["reviewers"], ["ReviewerA", "ReviewerB"])
        self.assertTrue((Path(results[0]["run_dir"]) / "cleaned.marker").is_file())
        events = self.events()
        start = next(event for event in events if event["event"] == "start")
        self.assertEqual(start["reviewers"], "ReviewerA,ReviewerB")
        self.assertIn("Implement the task", start["prompt"])
        self.assertIn(str(self.task_source), start["prompt"])
        self.assertTrue(any(event["event"] == "cleanup" for event in events))

    def test_non_consensus_run_is_preserved_without_cleanup(self) -> None:
        config = self._write_json("failing.json", self.single_payload(failing=True))
        with mock.patch.dict(os.environ, {"HIVE_TEST_EVENT_LOG": str(self.event_log)}):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "needs_attention")
        self.assertIs(results[0]["consensus_reached"], False)
        self.assertIs(results[0]["consensus_exit_agree"], True)
        self.assertTrue((Path(results[0]["run_dir"]) / "run.json").is_file())
        self.assertFalse(any(event["event"] == "cleanup" for event in self.events()))

    def test_exit_zero_cannot_override_non_consensus_summary(self) -> None:
        config = self._write_json("false-consensus-zero-exit.json", self.single_payload(failing=True))
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_EXIT_CODE": "0",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "needs_attention")
        self.assertIs(results[0]["consensus_reached"], False)
        self.assertIs(results[0]["consensus_exit_agree"], False)
        self.assertFalse(any(event["event"] == "cleanup" for event in self.events()))

    def test_exit_one_cannot_override_consensus_summary(self) -> None:
        config = self._write_json("true-consensus-one-exit.json", self.single_payload())
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_EXIT_CODE": "1",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "needs_attention")
        self.assertIs(results[0]["consensus_reached"], True)
        self.assertIs(results[0]["consensus_exit_agree"], False)
        self.assertFalse(any(event["event"] == "cleanup" for event in self.events()))

    def test_trailing_stdout_does_not_hide_reported_run_directory(self) -> None:
        config = self._write_json("trailing-output.json", self.single_payload())
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_TRAILING_STDOUT": "1",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "passed")
        self.assertIs(results[0]["run_dir_reported"], True)

    def test_missing_summary_is_an_infrastructure_failure_without_cleanup(self) -> None:
        config = self._write_json("missing-summary.json", self.single_payload())
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_SUMMARY_MODE": "missing",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "infrastructure_failed")
        self.assertIsNone(results[0]["consensus_reached"])
        self.assertIn("missing", results[0]["summary_error"])
        self.assertFalse(any(event["event"] == "cleanup" for event in self.events()))

    def test_malformed_summary_is_an_infrastructure_failure_without_cleanup(self) -> None:
        config = self._write_json("malformed-summary.json", self.single_payload())
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_SUMMARY_MODE": "malformed",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "infrastructure_failed")
        self.assertIsNone(results[0]["consensus_reached"])
        self.assertIn("cannot read", results[0]["summary_error"])
        self.assertFalse(any(event["event"] == "cleanup" for event in self.events()))

    def test_cleanup_failure_is_reported_after_consensus(self) -> None:
        config = self._write_json("cleanup-failure.json", self.single_payload())
        environment = {
            "HIVE_TEST_EVENT_LOG": str(self.event_log),
            "HIVE_TEST_CLEANUP_EXIT": "1",
        }
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_single(config), resume=False)
            results, _ = run_plan(plan, parallel=False, resume=False)

        self.assertEqual(results[0]["status"], "cleanup_failed")
        self.assertIs(results[0]["consensus_reached"], True)
        self.assertEqual(results[0]["cleanup_exit_code"], 1)
        self.assertFalse((Path(results[0]["run_dir"]) / "cleaned.marker").exists())

    def test_resume_without_run_manifest_starts_a_new_run(self) -> None:
        config = self._write_json("resume-new.json", self.single_payload())
        with mock.patch.dict(os.environ, {"HIVE_TEST_EVENT_LOG": str(self.event_log)}):
            plan = preflight(load_single(config), resume=True)
            results, _ = run_plan(plan, parallel=False, resume=True)

        self.assertEqual(results[0]["status"], "passed")
        self.assertIs(results[0]["resumed"], False)
        start = next(event for event in self.events() if event["event"] == "start")
        self.assertEqual(start["action"], "run")

    def test_resume_rejects_changed_reviewer_roster(self) -> None:
        payload = self.single_payload(failing=True)
        payload["cleanup_on_success"] = False
        config = self._write_json("resume-original.json", payload)
        with mock.patch.dict(os.environ, {"HIVE_TEST_EVENT_LOG": str(self.event_log)}):
            plan = preflight(load_single(config), resume=False)
            run_plan(plan, parallel=False, resume=False)

        payload["reviewers"] = ["ReviewerC"]
        changed = self._write_json("resume-changed.json", payload)
        with self.assertRaisesRegex(ConfigError, "changes recorded reviewers"):
            preflight(load_single(changed), resume=True)

    def parallel_payload(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "hive": self.hive(),
            "artifact_root": str(self.root / "parallel-artifacts"),
            "max_parallel_runs": 2,
            "defaults": {
                "implementor": "Implementor",
                "reviewers": ["ReviewerA", "ReviewerB"],
                "cleanup_on_success": True,
            },
            "general_context": {"text": "Shared epic context"},
            "assignments": [
                {"id": "a", "repo": str(self.repo_a), "context": {"text": "Task A"}},
                {
                    "id": "b",
                    "repo": str(self.repo_b),
                    "reviewers": ["ReviewerC"],
                    "context": {"text": "Task B"},
                },
                {"id": "c", "repo": str(self.repo_c), "context": {"text": "Task C"}},
            ],
        }

    def test_parallel_run_bounds_workflows_and_supports_panel_overrides(self) -> None:
        config = self._write_json("parallel.json", self.parallel_payload())
        environment = {"HIVE_TEST_EVENT_LOG": str(self.event_log), "HIVE_TEST_DELAY": "0.08"}
        with mock.patch.dict(os.environ, environment):
            plan = preflight(load_parallel(config), resume=False)
            results, summaries = run_plan(plan, parallel=True, resume=False)

        self.assertEqual([result["status"] for result in results], ["passed"] * 3)
        self.assertIsNotNone(summaries)
        self.assertTrue(summaries[0].is_file())
        self.assertTrue(summaries[1].is_file())
        starts = [event for event in self.events() if event["event"] == "start"]
        self.assertEqual({event["reviewers"] for event in starts}, {"ReviewerA,ReviewerB", "ReviewerC"})
        active = 0
        peak = 0
        for event in self.events():
            if event["event"] == "start":
                active += 1
                peak = max(peak, active)
            elif event["event"] == "end":
                active -= 1
        self.assertEqual(peak, 2)
        self.assertEqual(active, 0)

    def test_parallel_repositories_must_be_disjoint(self) -> None:
        nested = self.repo_a / "nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        payload = self.parallel_payload()
        payload["assignments"][1]["repo"] = str(nested)
        config = self._write_json("nested.json", payload)

        with self.assertRaisesRegex(ConfigError, "repositories must be disjoint"):
            load_parallel(config)

    def events(self) -> list[dict[str, object]]:
        if not self.event_log.exists():
            return []
        return [json.loads(line) for line in self.event_log.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
