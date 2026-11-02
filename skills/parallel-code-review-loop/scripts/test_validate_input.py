#!/usr/bin/env python3
"""Input checks for the shared-dispatcher wrapper."""

import tempfile
import unittest
from pathlib import Path

from validate_input import InputError, validate_manifest


class ValidateInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self):
        return {
            "coordination_dir": str(self.root),
            "general_context": {"task": "Shared requirements"},
            "assignments": [
                {
                    "id": "task-a",
                    "working_path": str(self.root),
                    "agent_context": "Task A",
                },
                {
                    "id": "task b / provider-hostile",
                    "working_path": str(self.root),
                    "agent_context": "Task B",
                },
            ],
        }

    def test_shared_coordination_and_names_need_no_capacity_input(self):
        result = validate_manifest(self.manifest())
        self.assertEqual(result["coordination_dir"], str(self.root))
        self.assertEqual(result["assignment_count"], 2)
        names = [a["implementor_launch_name"] for a in result["assignments"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(n.replace("_", "").isalnum() for n in names))

    def test_session_mode_defaults_to_fresh_and_accepts_explicit_reuse(self):
        manifest = self.manifest()
        self.assertEqual(validate_manifest(manifest)["session_mode"], "fresh")
        manifest["session_mode"] = "reuse"
        self.assertEqual(validate_manifest(manifest)["session_mode"], "reuse")
        for invalid in (None, "", "same", True, [], {}):
            manifest["session_mode"] = invalid
            with self.assertRaisesRegex(InputError, "session_mode"):
                validate_manifest(manifest)

    def test_source_paths_are_not_compared(self):
        manifest = self.manifest()
        validate_manifest(manifest)  # Equal paths are the operator's concern.
        nested = self.root / "nested"
        nested.mkdir()
        manifest["assignments"][1]["working_path"] = str(nested)
        validate_manifest(manifest)
        alias = self.root / "alias"
        alias.symlink_to(nested, target_is_directory=True)
        manifest["assignments"][0]["working_path"] = str(alias)
        validate_manifest(manifest)

    def test_obsolete_capacity_options_are_rejected(self):
        for name in ("max_parallel_pairs", "confirmed_worker_slots"):
            manifest = self.manifest()
            manifest[name] = 2
            with self.assertRaisesRegex(InputError, "no longer supported"):
                validate_manifest(manifest)

    def test_coordination_directory_is_required_and_absolute(self):
        for value in (None, "", "relative"):
            manifest = self.manifest()
            manifest["coordination_dir"] = value
            with self.assertRaisesRegex(InputError, "coordination_dir"):
                validate_manifest(manifest)

    def test_task_identity_and_context_remain_required(self):
        manifest = self.manifest()
        manifest["assignments"][1]["id"] = "task-a"
        with self.assertRaisesRegex(InputError, "duplicate"):
            validate_manifest(manifest)
        manifest = self.manifest()
        manifest["assignments"][0]["agent_context"] = ""
        with self.assertRaisesRegex(InputError, "agent_context"):
            validate_manifest(manifest)

    def test_each_source_directory_still_must_exist_and_be_absolute(self):
        for value in ("relative", str(self.root / "missing")):
            manifest = self.manifest()
            manifest["assignments"][0]["working_path"] = value
            with self.assertRaisesRegex(InputError, "working_path"):
                validate_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
