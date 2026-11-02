#!/usr/bin/env python3
"""Validate deterministic preflight rules for parallel-code-review-loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


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
    except (OSError, RuntimeError) as error:
        raise InputError(f"{field} does not resolve: {value!r}: {error}") from error
    if not canonical.is_dir():
        raise InputError(f"{field} is not a directory: {canonical}")
    return canonical


def validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise InputError("manifest must be a JSON or YAML object")

    if "general_context" not in manifest:
        raise InputError("manifest is missing general_context")
    _require_context(manifest["general_context"], "general_context")
    session_mode = manifest.get("session_mode", "fresh")
    if session_mode not in ("fresh", "reuse"):
        raise InputError(
            'session_mode must be "fresh" or "reuse"; for example: "session_mode": "fresh"'
        )

    assignments = manifest.get("assignments")
    if not isinstance(assignments, list) or not assignments:
        raise InputError("assignments must be a non-empty array")

    coordination_directory = _canonical_directory(
        manifest.get("coordination_dir"), "coordination_dir"
    )
    for obsolete in ("max_parallel_pairs", "confirmed_worker_slots"):
        if obsolete in manifest:
            raise InputError(
                f"{obsolete} is no longer supported; remove it from the manifest"
            )

    normalized: list[dict[str, Any]] = []
    identifiers: set[str] = set()
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
        if "agent_context" not in assignment:
            raise InputError(f"{prefix} is missing agent_context")
        _require_context(assignment["agent_context"], f"{prefix}.agent_context")

        ordinal = f"{index:0{width}d}"
        normalized.append(
            {
                "id": identifier,
                "working_path": str(root),
                "implementor_launch_name": f"pair_{ordinal}_implementor",
                "agent_context": assignment["agent_context"],
            }
        )

    return {
        "coordination_dir": str(coordination_directory),
        "general_context": manifest["general_context"],
        "session_mode": session_mode,
        "assignment_count": len(assignments),
        "assignments": normalized,
    }


def parse_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    return parser.parse_args(arguments)


def main(arguments: list[str] | None = None) -> int:
    options = parse_args(sys.argv[1:] if arguments is None else arguments)
    try:
        manifest = load_manifest(options.manifest)
        result = validate_manifest(manifest)
    except InputError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
