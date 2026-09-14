#!/usr/bin/env python3
"""Tests for parallel-code-review-loop input validation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_input import InputError, validate_manifest  # noqa: E402


class ValidateInputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name).resolve()
        self.repo_a = self.workspace / "repo-a"
        self.repo_b = self.workspace / "repo-b"
        self.repo_a.mkdir()
        self.repo_b.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def manifest(self) -> dict[str, object]:
        return {
            "general_context": {"objective": "Complete the epic"},
            "assignments": [
                {
                    "id": "task-a",
                    "working_path": str(self.repo_a),
                    "agent_context": {"task": "Implement A"},
                },
                {
                    "id": "task b / provider-hostile",
                    "working_path": str(self.repo_b),
                    "agent_context": {"task": "Implement B"},
                },
            ],
        }

    def test_valid_manifest_derives_capacity_and_safe_names(self) -> None:
        manifest = self.manifest()
        manifest["max_parallel_pairs"] = 8

        result = validate_manifest(manifest, confirmed_worker_slots=4)

        self.assertEqual(result["assignment_count"], 2)
        self.assertEqual(result["pair_capacity"], 2)
        self.assertEqual(result["effective_parallel_pairs"], 2)
        self.assertFalse(result["waves_required"])
        names = [
            item[key]
            for item in result["assignments"]
            for key in ("implementor_launch_name", "reviewer_launch_name")
        ]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name.replace("_", "").isalnum() for name in names))

    def test_pair_limit_requires_a_positive_integer(self) -> None:
        for invalid in (None, 0, -1, True, 1.5, "2"):
            with self.subTest(invalid=invalid):
                manifest = self.manifest()
                manifest["max_parallel_pairs"] = invalid
                with self.assertRaisesRegex(InputError, "max_parallel_pairs"):
                    validate_manifest(manifest, confirmed_worker_slots=4)

    def test_at_least_two_confirmed_worker_slots_are_required(self) -> None:
        with self.assertRaisesRegex(InputError, "at least 2"):
            validate_manifest(self.manifest(), confirmed_worker_slots=1)

    def test_duplicate_working_roots_are_rejected(self) -> None:
        manifest = self.manifest()
        manifest["assignments"][1]["working_path"] = str(self.repo_a)

        with self.assertRaisesRegex(InputError, "overlaps"):
            validate_manifest(manifest, confirmed_worker_slots=4)

    def test_nested_working_roots_are_rejected(self) -> None:
        nested = self.repo_a / "nested-repo"
        nested.mkdir()
        manifest = self.manifest()
        manifest["assignments"][1]["working_path"] = str(nested)

        with self.assertRaisesRegex(InputError, "overlaps"):
            validate_manifest(manifest, confirmed_worker_slots=4)

    def test_relative_working_root_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["assignments"][0]["working_path"] = "repo-a"

        with self.assertRaisesRegex(InputError, "must be absolute"):
            validate_manifest(manifest, confirmed_worker_slots=4)

    def test_insufficient_capacity_never_produces_a_zero_pair_plan(self) -> None:
        manifest = self.manifest()
        manifest["max_parallel_pairs"] = 1

        result = validate_manifest(manifest, confirmed_worker_slots=2)

        self.assertEqual(result["effective_parallel_pairs"], 1)
        self.assertTrue(result["waves_required"])


if __name__ == "__main__":
    unittest.main()
