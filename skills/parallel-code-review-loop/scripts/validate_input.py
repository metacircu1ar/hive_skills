#!/usr/bin/env python3
"""Validate deterministic preflight rules for parallel-code-review-loop."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional


class InputError(ValueError):
    """Raised when a parallel review manifest is not safe to schedule."""


def _load_yaml(text: str, source: Path) -> Any:
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as error:
        raise InputError(
            f"{source}: YAML input requires PyYAML; use JSON for dependency-free validation"
        ) from error

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise InputError(f"{source}: invalid YAML: {error}") from error


def load_manifest(source: Path) -> Any:
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as error:
        raise InputError(f"cannot read manifest {source}: {error}") from error

    if source.suffix.lower() in {".yaml", ".yml"}:
        return _load_yaml(text, source)

    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise InputError(f"{source}: invalid JSON: {error}") from error


def _require_context(value: Any, field: str) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise InputError(f"{field} must not be empty")
        return
    if isinstance(value, (dict, list)) and value:
        return
    raise InputError(f"{field} must be a non-empty string, object, or array")


def _canonical_directory(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise InputError(f"{field} must be a non-empty absolute path string")
    if value != value.strip():
        raise InputError(f"{field} must not have leading or trailing whitespace")

    path = Path(value)
    if not path.is_absolute():
        raise InputError(f"{field} must be absolute: {value!r}")
    try:
        canonical = path.resolve(strict=True)
    except OSError as error:
        raise InputError(f"{field} does not resolve: {value!r}: {error}") from error
    if not canonical.is_dir():
        raise InputError(f"{field} is not a directory: {canonical}")
    return canonical


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        if os.path.samefile(first, second):
            return True
    except OSError:
        pass
    return first in second.parents or second in first.parents


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise InputError(f"{field} must be an integer greater than or equal to 1")
    return value


def validate_manifest(manifest: Any, confirmed_worker_slots: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise InputError("manifest must be a JSON or YAML object")

    if "general_context" not in manifest:
        raise InputError("manifest is missing general_context")
    _require_context(manifest["general_context"], "general_context")

    assignments = manifest.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise InputError("assignments must be a non-empty array")

    worker_slots = _positive_integer(
        confirmed_worker_slots, "confirmed_worker_slots"
    )
    if worker_slots < 2:
        raise InputError(
            "confirmed_worker_slots must be at least 2; one pair needs two concurrent roles"
        )

    configured_limit = None
    if "max_parallel_pairs" in manifest:
        configured_limit = _positive_integer(
            manifest["max_parallel_pairs"], "max_parallel_pairs"
        )

    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    roots: list[tuple[str, Path]] = []
    width = max(3, len(str(len(assignments))))

    for index, assignment in enumerate(assignments, start=1):
        prefix = f"assignments[{index - 1}]"
        if not isinstance(assignment, dict):
            raise InputError(f"{prefix} must be an object")

        identifier = assignment.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise InputError(f"{prefix}.id must be a non-empty string")
        if identifier != identifier.strip():
            raise InputError(f"{prefix}.id must not have surrounding whitespace")
        if identifier in identifiers:
            raise InputError(f"duplicate assignment id: {identifier!r}")
        identifiers.add(identifier)

        root = _canonical_directory(
            assignment.get("working_path"), f"{prefix}.working_path"
        )
        for earlier_id, earlier_root in roots:
            if _paths_overlap(earlier_root, root):
                raise InputError(
                    "working paths must be disjoint; "
                    f"{identifier!r} at {root} overlaps {earlier_id!r} at {earlier_root}"
                )
        roots.append((identifier, root))

        if "agent_context" not in assignment:
            raise InputError(f"{prefix} is missing agent_context")
        _require_context(assignment["agent_context"], f"{prefix}.agent_context")

        ordinal = f"{index:0{width}d}"
        normalized.append(
            {
                "id": identifier,
                "working_path": str(root),
                "implementor_launch_name": f"pair_{ordinal}_implementor",
                "reviewer_launch_name": f"pair_{ordinal}_reviewer",
            }
        )

    pair_capacity = worker_slots // 2
    effective_limit = min(len(assignments), pair_capacity)
    if configured_limit is not None:
        effective_limit = min(effective_limit, configured_limit)

    return {
        "assignment_count": len(assignments),
        "confirmed_worker_slots": worker_slots,
        "pair_capacity": pair_capacity,
        "effective_parallel_pairs": effective_limit,
        "waves_required": len(assignments) > effective_limit,
        "assignments": normalized,
    }


def parse_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--confirmed-worker-slots",
        required=True,
        type=int,
        help="worker slots concurrently available to pair roles, excluding the orchestrator",
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[list[str]] = None) -> int:
    options = parse_args(sys.argv[1:] if arguments is None else arguments)
    try:
        manifest = load_manifest(options.manifest)
        result = validate_manifest(manifest, options.confirmed_worker_slots)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
