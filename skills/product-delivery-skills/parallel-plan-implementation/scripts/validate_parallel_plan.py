#!/usr/bin/env python3
"""Validate parallel implementation boundaries and execution manifest.

The validator uses only the Python standard library. It checks structure, identifiers,
dependency acyclicity, wave ordering, contract references, path ownership, and artifact
existence. It cannot prove that a boundary is behaviorally complete or that code is correct.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

PLAN_RELATIVE_PATH = Path("docs") / "implementation-plan"
PARALLEL_RELATIVE_PATH = PLAN_RELATIVE_PATH / "parallel-implementation"
DELIVERY_STATUS_PATH = "docs/implementation-plan/delivery-status.md"

REQUIRED_FILES = (
    "README.md",
    "execution-manifest.json",
    "dependency-graph.md",
    "contract-baseline.md",
    "integration-order.md",
    "implementation-ledger.md",
)

REQUIRED_DIRS = ("boundaries", "worker-prompts")

README_HEADINGS = (
    "implementation status and approved scope",
    "baseline and contract-baseline commits",
    "environment capability result",
    "component and phase scope",
    "contract summary",
    "verified parallel waves",
    "integration strategy",
    "document index",
    "current blockers and decision gates",
    "how to resume or revise execution",
)

DEPENDENCY_GRAPH_HEADINGS = (
    "graph purpose and source",
    "node registry",
    "edge registry",
    "dependency-type decisions",
    "mermaid dependency graph",
    "cycles found and resolutions",
    "contract-parallel edges",
    "implementation-bound edges",
    "decision-gated units",
    "shared-path serialization constraints",
)

CONTRACT_BASELINE_HEADINGS = (
    "baseline purpose",
    "baseline commit",
    "contract registry",
    "materialized declarations and schemas",
    "generated artifacts",
    "mocks, fakes, fixtures, and emulators",
    "contract tests and validation commands",
    "compatibility and versioning",
    "contract ownership",
    "contract gaps and reclassified dependencies",
    "change-control procedure",
)

INTEGRATION_ORDER_HEADINGS = (
    "ordering principles",
    "integration checkpoint history",
    "ordered phase list",
    "per-wave order",
    "shared-file reconciliation owners",
    "migration and generated-artifact order",
    "validation after each phase",
    "stop conditions",
    "replanning triggers",
)

LEDGER_HEADINGS = (
    "ledger status",
    "phase implementation records",
    "contract change records",
    "integration issues and resolutions",
    "validation summary",
    "pre-existing failures and environmental limitations",
    "deviations and approvals",
    "retained worktrees and branches",
    "remaining units and production gates",
)

BOUNDARY_HEADINGS = (
    "boundary purpose",
    "component ownership and non-ownership",
    "canonical contract registry",
    "shared invariants",
    "path ownership policy",
    "phase boundaries",
    "cross-component compatibility rules",
    "change-control owner",
    "known blockers and deferred decisions",
)

PHASE_BOUNDARY_SUBHEADINGS = (
    "phase identity",
    "inbound guarantees",
    "exact interface surface",
    "behavioral contract",
    "data and migration contract",
    "cross-component responsibilities",
    "test doubles and contract tests",
    "path ownership",
    "outbound obligations",
    "validation and exit evidence",
    "decision gates and prohibited assumptions",
    "integration prerequisites",
)

MANIFEST_REQUIRED_KEYS = (
    "schema_version",
    "status",
    "repository_root",
    "planning_root",
    "parallel_root",
    "approved_scope",
    "integration",
    "agent_profiles",
    "capabilities",
    "shared_path_owners",
    "contracts",
    "units",
    "waves",
    "integration_order",
    "excluded_units",
    "validation_commands",
    "review_gate",
    "updated_at",
)

APPROVED_SCOPE_REQUIRED_KEYS = (
    "phase_ids",
    "description",
    "delivery_scope_mode",
    "requested_outcome",
    "impact_cone",
    "preserved_behavior",
    "non_goals",
)

UNIT_REQUIRED_KEYS = (
    "id",
    "component_id",
    "title",
    "plan_path",
    "boundary_path",
    "worker_prompt_path",
    "wave",
    "integration_index",
    "base_commit",
    "branch",
    "worktree",
    "classification",
    "decision_gates",
    "dependencies",
    "consumes_contracts",
    "produces_contracts",
    "owned_paths",
    "read_only_paths",
    "shared_paths",
    "generated_paths",
    "forbidden_paths",
    "validation_commands",
    "status",
    "worker_commits",
    "integration_commit",
    "limitations",
    "blockers",
)

CONTRACT_REQUIRED_KEYS = (
    "id",
    "name",
    "kind",
    "owner_phase",
    "consumer_phases",
    "canonical_path",
    "version",
    "status",
    "validation_commands",
)

PHASE_ID_RE = re.compile(r"^PH-(\d{3,})-(\d{2,})$")
COMPONENT_ID_RE = re.compile(r"^CMP-(\d{3,})$")
CONTRACT_ID_RE = re.compile(r"^CTR-\d{3,}$")
DECISION_ID_RE = re.compile(r"^DEC-\d{3,}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
COMPONENT_DOC_ID_RE = re.compile(r"\bComponent\s+ID\s*:\s*(CMP-\d{3,})\b", re.IGNORECASE)
PLAN_SCOPE_BEGIN = "<!-- delivery-scope:begin -->"
PLAN_SCOPE_END = "<!-- delivery-scope:end -->"
DECOMPOSITION_BEGIN = "<!-- decomposition-assessment:begin -->"
DECOMPOSITION_END = "<!-- decomposition-assessment:end -->"
PROMPT_SCOPE_BEGIN = "<!-- approved-scope:begin -->"
PROMPT_SCOPE_END = "<!-- approved-scope:end -->"
PROMPT_PATH_POLICY_BEGIN = "<!-- path-policy:begin -->"
PROMPT_PATH_POLICY_END = "<!-- path-policy:end -->"
PLAN_SCOPE_KEYS = {
    "schema_version",
    "delivery_scope_mode",
    "requested_outcome",
    "impact_cone",
    "preserved_behavior",
    "non_goals",
    "planned_phase_ids",
    "authorized_phase_ids",
    "applicable_documents",
    "preserved_document_sources",
}
DECOMPOSITION_KEYS = {
    "schema_version",
    "context",
    "decision_kind",
    "axes",
    "language_constraints",
    "affected_subsystems",
    "data_ownership",
    "scenarios",
    "candidates",
}
DATA_OWNERSHIP_KEYS = {
    "resource",
    "owner_component_id",
    "authorized_writer_component_ids",
    "write_paths",
    "coordination",
}
PROMPT_SCOPE_KEYS = {
    "delivery_scope_mode",
    "requested_outcome",
    "impact_cone",
    "preserved_behavior",
    "non_goals",
}
PROMPT_PATH_POLICY_KEYS = {
    "owned_paths",
    "read_only_paths",
    "shared_paths",
    "generated_paths",
    "forbidden_paths",
}

DELIVERY_SCOPE_MODES = {
    "full product",
    "scoped change",
    "modernization or migration",
    "remediation or reliability",
}

VALID_MANIFEST_STATUSES = {
    "draft",
    "boundaries-ready",
    "contract-baseline-frozen",
    "executing",
    "blocked",
    "completed",
}
VALID_CONTRACT_STATUSES = {"draft", "frozen", "implemented", "deprecated", "retired"}
VALID_CLASSIFICATIONS = {"independent", "contract-bound", "implementation-bound", "decision-gated"}
VALID_DEPENDENCY_TYPES = {"contract-bound", "implementation-bound"}
VALID_UNIT_STATUSES = {
    "planned",
    "blocked",
    "ready",
    "running",
    "worker-completed",
    "integration-failed",
    "integrated",
    "verified",
    "rejected",
}
VALID_WAVE_STATUSES = {"planned", "ready", "running", "integrating", "completed", "blocked"}


def normalize_heading(value: str) -> str:
    value = re.sub(r"[`*_]", "", value)
    value = re.sub(r"\s+", " ", value.strip().lower())
    return value


def heading_entries(text: str) -> list[tuple[int, str, int]]:
    return [
        (len(match.group(1)), normalize_heading(match.group(2)), match.start())
        for match in HEADING_RE.finditer(text)
    ]


def missing_headings(text: str, required: Iterable[str]) -> list[str]:
    available = {name for _, name, _ in heading_entries(text)}
    return [name for name in required if normalize_heading(name) not in available]


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{path}: file is not valid UTF-8")
    except OSError as exc:
        errors.append(f"{path}: cannot read file: {exc}")
    return ""


def validate_markdown(path: Path, required: Iterable[str], errors: list[str]) -> str:
    text = read_text(path, errors)
    if text:
        for heading in missing_headings(text, required):
            errors.append(f"{path}: missing required section '{heading}'")
    return text


def repo_file(repo_root: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty repository-relative path")
        return None
    raw = Path(value)
    if raw.is_absolute():
        errors.append(f"{label}: must be repository-relative, got absolute path {value!r}")
        return None
    candidate = (repo_root / raw).resolve()
    try:
        candidate.relative_to(repo_root)
    except ValueError:
        errors.append(f"{label}: escapes repository root: {value!r}")
        return None
    return candidate


def check_required_keys(obj: Any, required: Iterable[str], label: str, errors: list[str]) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{label}: expected an object")
        return False
    missing = [key for key in required if key not in obj]
    if missing:
        errors.append(f"{label}: missing keys: {', '.join(missing)}")
        return False
    return True


def string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{label}: expected an array of strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label}: duplicate values are not allowed")
    return value


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def parse_json_block(
    text: str,
    begin: str,
    end: str,
    required_keys: set[str],
    label: str,
    errors: list[str],
    record_name: str = "scope",
) -> dict[str, Any] | None:
    if text.count(begin) != 1 or text.count(end) != 1:
        errors.append(f"{label}: expected exactly one {begin} ... {end} block")
        return None
    start = text.find(begin) + len(begin)
    finish = text.find(end, start)
    if finish < start:
        errors.append(f"{label}: {record_name} block markers are out of order")
        return None
    try:
        value = json.loads(
            text[start:finish].strip(), object_pairs_hook=reject_duplicate_keys
        )
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{label}: invalid {record_name} JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: {record_name} block must contain one JSON object")
        return None
    if set(value) != required_keys:
        errors.append(
            f"{label}: {record_name} keys differ; missing={sorted(required_keys - set(value))}, "
            f"extra={sorted(set(value) - required_keys)}"
        )
        return None
    return value


def scope_projection(scope: dict[str, Any]) -> dict[str, Any]:
    return {key: scope.get(key) for key in PROMPT_SCOPE_KEYS}


def validate_prompt_scope(
    text: str, expected: dict[str, Any], label: str, errors: list[str]
) -> None:
    actual = parse_json_block(
        text,
        PROMPT_SCOPE_BEGIN,
        PROMPT_SCOPE_END,
        PROMPT_SCOPE_KEYS,
        label,
        errors,
    )
    if actual is not None and actual != expected:
        errors.append(f"{label}: approved-scope block does not match its immutable source")


def path_policy_is_valid(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(value.get(key), list)
        and all(isinstance(item, str) for item in value.get(key, []))
        for key in PROMPT_PATH_POLICY_KEYS
    )


def validate_prompt_path_policy(
    text: str,
    expected: dict[str, Any] | None,
    label: str,
    errors: list[str],
) -> None:
    if not path_policy_is_valid(expected):
        errors.append(
            f"{label}: source execution-manifest path policy must contain arrays of "
            "strings for all five path fields"
        )
        expected = None
    actual = parse_json_block(
        text,
        PROMPT_PATH_POLICY_BEGIN,
        PROMPT_PATH_POLICY_END,
        PROMPT_PATH_POLICY_KEYS,
        label,
        errors,
        record_name="path policy",
    )
    if actual is None:
        return
    if not path_policy_is_valid(actual):
        errors.append(f"{label}: path-policy fields must all be arrays of strings")
        return
    if expected is not None and actual != expected:
        errors.append(f"{label}: path-policy block does not match its immutable source")
    for path_kind in ("owned_paths", "shared_paths", "generated_paths"):
        singular_kind = path_kind.removesuffix("_paths").replace("_", "-")
        for write_path in actual[path_kind]:
            if patterns_may_overlap(write_path, DELIVERY_STATUS_PATH):
                errors.append(
                    f"{label}: {singular_kind} path {write_path!r} overlaps "
                    f"orchestration-owned {DELIVERY_STATUS_PATH!r}"
                )


def validate_plan_data_ownership(
    decomposition: dict[str, Any] | None, label: str, errors: list[str]
) -> list[dict[str, Any]]:
    if decomposition is None:
        return []
    if decomposition.get("schema_version") != 1:
        errors.append(f"{label}: decomposition-assessment.schema_version must equal 1")
    records = decomposition.get("data_ownership")
    if not isinstance(records, list):
        errors.append(f"{label}: decomposition-assessment.data_ownership must be an array")
        return []
    valid: list[dict[str, Any]] = []
    resources: list[str] = []
    for index, record in enumerate(records):
        item_label = f"{label}: decomposition-assessment.data_ownership[{index}]"
        record_error_count = len(errors)
        if not isinstance(record, dict) or set(record) != DATA_OWNERSHIP_KEYS:
            keys = set(record) if isinstance(record, dict) else set()
            errors.append(
                f"{item_label}: keys differ; missing={sorted(DATA_OWNERSHIP_KEYS - keys)}, "
                f"extra={sorted(keys - DATA_OWNERSHIP_KEYS)}"
            )
            continue
        resource = record.get("resource")
        if not isinstance(resource, str) or not resource.strip():
            errors.append(f"{item_label}.resource must be a non-empty string")
        else:
            resources.append(resource)
        owner = record.get("owner_component_id")
        if not isinstance(owner, str) or not COMPONENT_ID_RE.fullmatch(owner):
            errors.append(f"{item_label}.owner_component_id must match CMP-###")
        writers = string_list(
            record.get("authorized_writer_component_ids"),
            f"{item_label}.authorized_writer_component_ids",
            errors,
        )
        if not writers:
            errors.append(f"{item_label}.authorized_writer_component_ids must not be empty")
        for writer in writers:
            if not COMPONENT_ID_RE.fullmatch(writer):
                errors.append(f"{item_label}: invalid writer component ID {writer!r}")
        if isinstance(owner, str) and owner not in writers:
            errors.append(f"{item_label}: owner_component_id must be an authorized writer")
        paths = string_list(record.get("write_paths"), f"{item_label}.write_paths", errors)
        if not paths:
            errors.append(f"{item_label}.write_paths must not be empty")
        for path_index, pattern in enumerate(paths):
            validate_path_pattern(pattern, f"{item_label}.write_paths[{path_index}]", errors)
        coordination = record.get("coordination")
        if coordination is not None and (
            not isinstance(coordination, str) or not coordination.strip()
        ):
            errors.append(f"{item_label}.coordination must be null or a non-empty string")
        if len(writers) > 1 and coordination is None:
            errors.append(f"{item_label}.coordination is required for multiple writers")
        if len(errors) == record_error_count:
            valid.append(record)
    if len(resources) != len(set(resources)):
        errors.append(f"{label}: decomposition-assessment resources must be unique")
    for left_index, left in enumerate(valid):
        for right in valid[left_index + 1 :]:
            if left.get("owner_component_id") == right.get("owner_component_id"):
                continue
            if any(
                patterns_may_overlap(left_path, right_path)
                for left_path in usable_string_list(left.get("write_paths"))
                for right_path in usable_string_list(right.get("write_paths"))
            ):
                errors.append(
                    f"{label}: decomposition resources {left.get('resource')!r} and "
                    f"{right.get('resource')!r} have overlapping write paths but different owners"
                )
    return valid


def validate_unit_data_ownership(
    units: dict[str, dict[str, Any]],
    ownership_records: list[dict[str, Any]],
    shared_owners: list[dict[str, Any]],
    errors: list[str],
) -> None:
    for ownership in ownership_records:
        declared_paths = usable_string_list(ownership.get("write_paths"))
        authorized_writers = set(
            usable_string_list(ownership.get("authorized_writer_component_ids"))
        )
        matching_units: list[tuple[str, dict[str, Any], list[str]]] = []
        for phase_id, unit in units.items():
            component_id = unit.get("component_id")
            write_capable_paths = (
                usable_string_list(unit.get("owned_paths"))
                + usable_string_list(unit.get("shared_paths"))
                + usable_string_list(unit.get("generated_paths"))
            )
            matching_paths = [
                unit_path
                for unit_path in write_capable_paths
                if any(
                    patterns_may_overlap(unit_path, declared_path)
                    for declared_path in declared_paths
                )
            ]
            if not matching_paths:
                continue
            matching_units.append((phase_id, unit, matching_paths))
            if component_id not in authorized_writers:
                errors.append(
                    f"unit {phase_id}: component {component_id!r} writes declared resource "
                    f"{ownership.get('resource')!r} but is not an authorized writer; "
                    f"allowed={sorted(authorized_writers)}"
                )

        if len(authorized_writers) <= 1:
            continue
        for left_index, (left_id, left_unit, left_paths) in enumerate(matching_units):
            left_component = left_unit.get("component_id")
            for right_id, right_unit, right_paths in matching_units[left_index + 1 :]:
                right_component = right_unit.get("component_id")
                if left_component == right_component or left_unit.get("wave") != right_unit.get(
                    "wave"
                ):
                    continue
                reconcilers = {
                    entry.get("owner")
                    for entry in shared_owners
                    if isinstance(entry.get("path"), str)
                    and isinstance(entry.get("owner"), str)
                    and isinstance(entry.get("strategy"), str)
                    and bool(entry.get("strategy"))
                    and any(
                        registry_pattern_covers(entry["path"], left_path)
                        for left_path in left_paths
                    )
                    and any(
                        registry_pattern_covers(entry["path"], right_path)
                        for right_path in right_paths
                    )
                }
                if len(reconcilers) != 1:
                    errors.append(
                        f"resource {ownership.get('resource')!r}: authorized writer components "
                        f"{left_component} ({left_id}) and {right_component} ({right_id}) share "
                        f"wave {left_unit.get('wave')} without one shared-path reconciliation "
                        "owner; place them in different waves or register one owner and strategy"
                    )


def validate_same_wave_write_ownership(
    units: dict[str, dict[str, Any]],
    shared_owners: list[dict[str, Any]],
    errors: list[str],
) -> None:
    units_by_wave: dict[int, list[str]] = defaultdict(list)
    for phase_id, unit in units.items():
        wave = unit.get("wave")
        if isinstance(wave, int):
            units_by_wave[wave].append(phase_id)
    for wave, phase_ids in units_by_wave.items():
        for left_index, left_id in enumerate(phase_ids):
            left_paths = usable_string_list(
                units[left_id].get("owned_paths")
            ) + usable_string_list(units[left_id].get("generated_paths"))
            for right_id in phase_ids[left_index + 1 :]:
                right_paths = usable_string_list(
                    units[right_id].get("owned_paths")
                ) + usable_string_list(units[right_id].get("generated_paths"))
                for left_path in left_paths:
                    for right_path in right_paths:
                        if patterns_may_overlap(left_path, right_path):
                            errors.append(
                                f"wave {wave}: overlapping exclusive or generated writes are "
                                "not allowed: "
                                f"{left_id}:{left_path!r} and {right_id}:{right_path!r}"
                            )

        for owner_id in phase_ids:
            owner_paths = usable_string_list(
                units[owner_id].get("owned_paths")
            ) + usable_string_list(units[owner_id].get("generated_paths"))
            for shared_id in phase_ids:
                if owner_id == shared_id:
                    continue
                shared_paths = usable_string_list(units[shared_id].get("shared_paths"))
                for owner_path in owner_paths:
                    for shared_path in shared_paths:
                        if not patterns_may_overlap(owner_path, shared_path):
                            continue
                        matching_owners = {
                            entry.get("owner")
                            for entry in shared_owners
                            if isinstance(entry.get("path"), str)
                            and isinstance(entry.get("owner"), str)
                            and registry_pattern_covers(entry["path"], owner_path)
                            and registry_pattern_covers(entry["path"], shared_path)
                        }
                        if matching_owners != {owner_id}:
                            errors.append(
                                f"wave {wave}: {owner_id} owns {owner_path!r} while {shared_id} "
                                f"declares overlapping shared path {shared_path!r}, but the registry "
                                f"does not name {owner_id} as the sole owner"
                            )

        for left_index, left_id in enumerate(phase_ids):
            left_shared_paths = usable_string_list(units[left_id].get("shared_paths"))
            for right_id in phase_ids[left_index + 1 :]:
                right_shared_paths = usable_string_list(units[right_id].get("shared_paths"))
                for left_path in left_shared_paths:
                    for right_path in right_shared_paths:
                        if not patterns_may_overlap(left_path, right_path):
                            continue
                        reconcilers = {
                            entry.get("owner")
                            for entry in shared_owners
                            if isinstance(entry.get("path"), str)
                            and isinstance(entry.get("owner"), str)
                            and isinstance(entry.get("strategy"), str)
                            and bool(entry.get("strategy"))
                            and registry_pattern_covers(entry["path"], left_path)
                            and registry_pattern_covers(entry["path"], right_path)
                        }
                        if len(reconcilers) != 1:
                            errors.append(
                                f"wave {wave}: overlapping shared writes require one common "
                                f"reconciliation owner: {left_id}:{left_path!r} and "
                                f"{right_id}:{right_path!r}"
                            )


def commit_exists(repo_root: Path, commit: str) -> bool:
    if not COMMIT_RE.fullmatch(commit):
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def normalize_git_tree_path(relative_path: str) -> str | None:
    """Normalize a repository-relative Git tree path without rewriting dotfiles or traversal."""

    if "\\" in relative_path:
        return None
    value = relative_path
    while value.startswith("./"):
        value = value.removeprefix("./")
    path = PurePosixPath(value)
    if (
        not value
        or not path.parts
        or "\x00" in value
        or path.is_absolute()
        or re.match(r"^[A-Za-z]:", value)
        or ".." in path.parts
    ):
        return None
    return path.as_posix()


def validate_immutable_planning_commit(
    repo_root: Path, planning_commit: str, errors: list[str]
) -> None:
    """Run the companion planner validator against planning files from one commit."""

    planner_validator = (
        Path(__file__).resolve().parents[2]
        / "product-implementation-planner"
        / "scripts"
        / "validate_plan.py"
    )
    if not planner_validator.is_file():
        errors.append(
            "companion product-implementation-planner validator is unavailable at "
            f"{planner_validator}"
        )
        return

    listing = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            planning_commit,
            "--",
            PLAN_RELATIVE_PATH.as_posix(),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if listing.returncode != 0:
        errors.append(
            f"cannot enumerate planning files at {planning_commit}: "
            f"{listing.stderr.decode('utf-8', errors='replace').strip()}"
        )
        return

    relative_paths = [
        path.decode("utf-8", errors="surrogateescape")
        for path in listing.stdout.split(b"\0")
        if path
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="parallel-plan-validation-") as temp_dir:
            snapshot_root = Path(temp_dir)
            destination_spellings: dict[str, str] = {}
            for relative_path in relative_paths:
                normalized = normalize_git_tree_path(relative_path)
                if normalized is None or not normalized.startswith(
                    PLAN_RELATIVE_PATH.as_posix() + "/"
                ):
                    errors.append(
                        f"planning commit contains an invalid planning path: {relative_path!r}"
                    )
                    return
                normalized_parts = PurePosixPath(normalized).parts
                for depth in range(1, len(normalized_parts) + 1):
                    destination_prefix = "/".join(normalized_parts[:depth])
                    destination_key = unicodedata.normalize(
                        "NFC", destination_prefix
                    ).casefold()
                    previous_spelling = destination_spellings.get(destination_key)
                    if (
                        previous_spelling is not None
                        and previous_spelling != destination_prefix
                    ):
                        errors.append(
                            "planning commit contains paths that alias in the validation "
                            f"snapshot: {previous_spelling!r} and {destination_prefix!r}"
                        )
                        return
                    destination_spellings[destination_key] = destination_prefix

                blob = subprocess.run(
                    ["git", "-C", str(repo_root), "show", f"{planning_commit}:{relative_path}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                if blob.returncode != 0:
                    errors.append(
                        f"cannot read planning file {relative_path!r} at {planning_commit}: "
                        f"{blob.stderr.decode('utf-8', errors='replace').strip()}"
                    )
                    return
                target = snapshot_root / normalized
                if target.exists():
                    errors.append(
                        "planning commit path aliases an existing validation destination: "
                        f"{relative_path!r}"
                    )
                    return
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob.stdout)

            try:
                validation = subprocess.run(
                    [sys.executable, str(planner_validator), str(snapshot_root)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=60,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                errors.append(
                    f"companion planner validation timed out for planning commit {planning_commit}"
                )
                return
            if validation.returncode != 0:
                output = "\n".join(
                    part.strip()
                    for part in (validation.stdout, validation.stderr)
                    if part.strip()
                )
                if len(output) > 6000:
                    output = output[:6000] + "\n... output truncated"
                errors.append(
                    f"planning commit {planning_commit} fails companion planner validation:\n"
                    + "\n".join(f"    {line}" for line in output.splitlines())
                )
    except OSError as exc:
        errors.append(
            f"cannot materialize planning commit {planning_commit} for validation: {exc}"
        )


def commit_contains_path(repo_root: Path, commit: str, relative_path: str) -> bool:
    """Return whether a repository-relative path exists in a commit tree."""

    if not COMMIT_RE.fullmatch(commit):
        return False
    normalized = normalize_git_tree_path(relative_path)
    if normalized is None:
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"{commit}:{normalized}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def git_show_text(repo_root: Path, commit: str, relative_path: str) -> str | None:
    """Read a repository-relative UTF-8 file from a commit without consulting the worktree."""

    normalized = normalize_git_tree_path(relative_path)
    if not COMMIT_RE.fullmatch(commit) or normalized is None:
        return None
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{commit}:{normalized}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def git_show_json(repo_root: Path, commit: str, relative_path: str) -> dict[str, Any] | None:
    text = git_show_text(repo_root, commit, relative_path)
    if text is None:
        return None
    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    """Return whether ancestor is reachable from descendant."""

    if not COMMIT_RE.fullmatch(ancestor) or not COMMIT_RE.fullmatch(descendant):
        return False
    result = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def usable_string_list(value: Any) -> list[str]:
    """Return a validated-looking string list, or an empty list after prior errors."""

    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return []
    return value


def validate_path_pattern(pattern: str, label: str, errors: list[str]) -> None:
    """Reject empty, absolute, or repository-escaping path patterns."""

    if not pattern.strip():
        errors.append(f"{label}: path pattern must not be empty")
        return
    normalized = pattern.replace("\\", "/").strip()
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        errors.append(f"{label}: path pattern must be repository-relative: {pattern!r}")
        return
    if ".." in normalized.split("/"):
        errors.append(f"{label}: path pattern escapes the repository: {pattern!r}")


def normalize_pattern(pattern: str) -> str:
    value = canonical_path_pattern(pattern)
    if not value:
        return ""
    wildcard_positions = [pos for char in "*?[" if (pos := value.find(char)) >= 0]
    if wildcard_positions:
        cut = min(wildcard_positions)
        # A wildcard inside a segment can match multiple concrete segment names.
        # Retain only complete preceding segments so overlap checks fail closed.
        if cut > 0 and value[cut - 1] != "/":
            cut = value.rfind("/", 0, cut) + 1
        value = value[:cut]
    return value.rstrip("/")


def canonical_path_pattern(pattern: str) -> str:
    value = pattern.replace("\\", "/").strip()
    parts = value.split("/")
    if ".." in parts:
        return ""
    return "/".join(part for part in parts if part not in ("", ".")).rstrip("/")


def registry_pattern_covers(registry_pattern: str, candidate_pattern: str) -> bool:
    """Prove simple registry coverage without using conservative overlap as authority."""

    registry = canonical_path_pattern(registry_pattern)
    candidate = canonical_path_pattern(candidate_pattern)
    if not registry or not candidate:
        return False
    if registry == candidate or registry == "**":
        return True
    if not registry.endswith("/**"):
        return False
    base = registry[:-3].rstrip("/")
    if any(character in base for character in "*?["):
        return False
    return candidate == base or candidate.startswith(base + "/")


def patterns_may_overlap(first: str, second: str) -> bool:
    a = normalize_pattern(first).casefold()
    b = normalize_pattern(second).casefold()
    if not a or not b:
        return True
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


def find_cycle(nodes: set[str], adjacency: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {node: 0 for node in nodes}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for neighbor in adjacency.get(node, set()):
            if state.get(neighbor, 0) == 0:
                cycle = visit(neighbor)
                if cycle:
                    return cycle
            elif state.get(neighbor) == 1:
                index = stack.index(neighbor)
                return stack[index:] + [neighbor]
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(nodes):
        if state[node] == 0:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


def validate_phase_boundary(
    boundary_path: Path,
    boundary_text: str,
    phase_id: str,
    errors: list[str],
) -> None:
    phase_heading = re.compile(
        rf"^###\s+{re.escape(phase_id)}\s+(?:—|-)\s+[^\n]+$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = phase_heading.search(boundary_text)
    if not match:
        errors.append(f"{boundary_path}: missing phase boundary heading for {phase_id}")
        return

    following = [
        item
        for item in re.finditer(r"^###\s+PH-\d{3,}-\d{2,}\s+(?:—|-)\s+[^\n]+$", boundary_text, re.MULTILINE)
        if item.start() > match.start()
    ]
    end = following[0].start() if following else len(boundary_text)
    block = boundary_text[match.start() : end]
    for heading in missing_headings(block, PHASE_BOUNDARY_SUBHEADINGS):
        errors.append(f"{boundary_path}: {phase_id} missing subsection '{heading}'")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate docs/implementation-plan/parallel-implementation."
    )
    parser.add_argument(
        "repository_root",
        nargs="?",
        default=".",
        help="Target repository root (default: current directory)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repository_root).expanduser().resolve()
    parallel_root = repo_root / PARALLEL_RELATIVE_PATH
    errors: list[str] = []
    warnings: list[str] = []

    git_check = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if git_check.returncode != 0:
        errors.append(f"{repo_root}: not a Git repository")

    if not parallel_root.is_dir():
        print(f"ERROR: parallel implementation directory does not exist: {parallel_root}")
        return 1

    for name in REQUIRED_FILES:
        if not (parallel_root / name).is_file():
            errors.append(f"missing required file: {parallel_root / name}")
    for name in REQUIRED_DIRS:
        if not (parallel_root / name).is_dir():
            errors.append(f"missing required directory: {parallel_root / name}")

    markdown_specs = {
        "README.md": README_HEADINGS,
        "dependency-graph.md": DEPENDENCY_GRAPH_HEADINGS,
        "contract-baseline.md": CONTRACT_BASELINE_HEADINGS,
        "integration-order.md": INTEGRATION_ORDER_HEADINGS,
        "implementation-ledger.md": LEDGER_HEADINGS,
    }
    markdown_texts: dict[str, str] = {}
    for name, headings in markdown_specs.items():
        path = parallel_root / name
        if path.is_file():
            markdown_texts[name] = validate_markdown(path, headings, errors)

    manifest_path = parallel_root / "execution-manifest.json"
    if not manifest_path.is_file():
        manifest: dict[str, Any] = {}
    else:
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = loaded if isinstance(loaded, dict) else {}
            if not isinstance(loaded, dict):
                errors.append(f"{manifest_path}: top-level JSON value must be an object")
        except json.JSONDecodeError as exc:
            errors.append(f"{manifest_path}: invalid JSON: {exc}")
            manifest = {}
        except OSError as exc:
            errors.append(f"{manifest_path}: cannot read file: {exc}")
            manifest = {}

    if not check_required_keys(manifest, MANIFEST_REQUIRED_KEYS, "manifest", errors):
        manifest = manifest or {}

    if manifest.get("schema_version") != 2:
        errors.append("manifest.schema_version must equal 2")
    manifest_status = manifest.get("status")
    if not isinstance(manifest_status, str) or manifest_status not in VALID_MANIFEST_STATUSES:
        errors.append(f"manifest.status must be one of {sorted(VALID_MANIFEST_STATUSES)}")

    manifest_repository_root = manifest.get("repository_root")
    if not isinstance(manifest_repository_root, str) or not manifest_repository_root.strip():
        errors.append("manifest.repository_root must be a non-empty path")
    else:
        recorded_root = Path(manifest_repository_root).expanduser()
        if not recorded_root.is_absolute():
            recorded_root = repo_root / recorded_root
        try:
            recorded_root = recorded_root.resolve()
        except OSError:
            pass
        if recorded_root != repo_root:
            errors.append(
                "manifest.repository_root does not resolve to the validated repository: "
                f"{manifest_repository_root!r}"
            )

    if manifest.get("planning_root") != PLAN_RELATIVE_PATH.as_posix():
        errors.append(
            f"manifest.planning_root must equal {PLAN_RELATIVE_PATH.as_posix()!r}"
        )
    if manifest.get("parallel_root") != PARALLEL_RELATIVE_PATH.as_posix():
        errors.append(
            f"manifest.parallel_root must equal {PARALLEL_RELATIVE_PATH.as_posix()!r}"
        )

    approved_scope = manifest.get("approved_scope", {})
    delivery_scope_mode: Any = None
    requested_outcome: Any = None
    impact_cone: Any = None
    preserved_behavior: list[str] = []
    non_goals: list[str] = []
    scope_error_count = len(errors)
    if not isinstance(approved_scope, dict):
        errors.append("manifest.approved_scope must be an object")
    else:
        check_required_keys(
            approved_scope,
            APPROVED_SCOPE_REQUIRED_KEYS,
            "manifest.approved_scope",
            errors,
        )
        delivery_scope_mode = approved_scope.get("delivery_scope_mode")
        if not isinstance(delivery_scope_mode, str) or delivery_scope_mode not in DELIVERY_SCOPE_MODES:
            errors.append(
                "manifest.approved_scope.delivery_scope_mode must be one of "
                f"{sorted(DELIVERY_SCOPE_MODES)}"
            )
        for key in ("description", "requested_outcome", "impact_cone"):
            if not isinstance(approved_scope.get(key), str) or not approved_scope.get(key, "").strip():
                errors.append(f"manifest.approved_scope.{key} must be a non-empty string")
        requested_outcome = approved_scope.get("requested_outcome")
        impact_cone = approved_scope.get("impact_cone")
        preserved_behavior = string_list(
            approved_scope.get("preserved_behavior"),
            "manifest.approved_scope.preserved_behavior",
            errors,
        )
        non_goals = string_list(
            approved_scope.get("non_goals"),
            "manifest.approved_scope.non_goals",
            errors,
        )
        for key, values in (("preserved_behavior", preserved_behavior), ("non_goals", non_goals)):
            if any(not item.strip() for item in values):
                errors.append(f"manifest.approved_scope.{key} entries must be non-empty")
        if not non_goals:
            errors.append("manifest.approved_scope.non_goals must not be empty")
        if (
            isinstance(delivery_scope_mode, str)
            and delivery_scope_mode in DELIVERY_SCOPE_MODES - {"full product"}
            and not preserved_behavior
        ):
            errors.append(
                "manifest.approved_scope.preserved_behavior must not be empty "
                "for a bounded mode"
            )
    scope_prompt_values_valid = len(errors) == scope_error_count

    product_description_path = repo_root / PLAN_RELATIVE_PATH / "00-product-description.md"
    planning_commit_for_scope = (
        manifest.get("integration", {}).get("planning_commit")
        if isinstance(manifest.get("integration"), dict)
        else None
    )
    if (
        isinstance(planning_commit_for_scope, str)
        and COMMIT_RE.fullmatch(planning_commit_for_scope)
        and commit_exists(repo_root, planning_commit_for_scope)
    ):
        product_description = git_show_text(
            repo_root,
            planning_commit_for_scope,
            (PLAN_RELATIVE_PATH / "00-product-description.md").as_posix(),
        ) or ""
        plan_scope_label = (
            f"{planning_commit_for_scope}:"
            f"{(PLAN_RELATIVE_PATH / '00-product-description.md').as_posix()}"
        )
    else:
        product_description = read_text(product_description_path, errors)
        plan_scope_label = str(product_description_path)
    plan_scope = parse_json_block(
        product_description,
        PLAN_SCOPE_BEGIN,
        PLAN_SCOPE_END,
        PLAN_SCOPE_KEYS,
        plan_scope_label,
        errors,
    )
    plan_authorized_ids: set[str] = set()
    plan_planned_ids: set[str] = set()
    if plan_scope is not None:
        if plan_scope.get("schema_version") != 1:
            errors.append(f"{plan_scope_label}: delivery-scope.schema_version must equal 1")
        for key in PROMPT_SCOPE_KEYS:
            if scope_prompt_values_valid and plan_scope.get(key) != approved_scope.get(key):
                errors.append(
                    f"manifest.approved_scope.{key} does not match the canonical plan scope"
                )
        for key, target in (
            ("planned_phase_ids", plan_planned_ids),
            ("authorized_phase_ids", plan_authorized_ids),
        ):
            values = string_list(
                plan_scope.get(key), f"plan delivery-scope.{key}", errors
            )
            for phase_id in values:
                if not PHASE_ID_RE.fullmatch(phase_id):
                    errors.append(f"plan delivery-scope.{key} has invalid ID {phase_id!r}")
                else:
                    target.add(phase_id)
        if not plan_authorized_ids <= plan_planned_ids:
            errors.append("plan authorized_phase_ids must be a subset of planned_phase_ids")

    implementation_units_path = repo_root / PLAN_RELATIVE_PATH / "93-implementation-units.md"
    if (
        isinstance(planning_commit_for_scope, str)
        and COMMIT_RE.fullmatch(planning_commit_for_scope)
        and commit_exists(repo_root, planning_commit_for_scope)
    ):
        validate_immutable_planning_commit(repo_root, planning_commit_for_scope, errors)
        implementation_units = git_show_text(
            repo_root,
            planning_commit_for_scope,
            (PLAN_RELATIVE_PATH / "93-implementation-units.md").as_posix(),
        ) or ""
        decomposition_label = (
            f"{planning_commit_for_scope}:"
            f"{(PLAN_RELATIVE_PATH / '93-implementation-units.md').as_posix()}"
        )
    else:
        implementation_units = read_text(implementation_units_path, errors)
        decomposition_label = str(implementation_units_path)
    plan_decomposition = parse_json_block(
        implementation_units,
        DECOMPOSITION_BEGIN,
        DECOMPOSITION_END,
        DECOMPOSITION_KEYS,
        decomposition_label,
        errors,
        "decomposition-assessment",
    )
    plan_data_ownership = validate_plan_data_ownership(
        plan_decomposition, decomposition_label, errors
    )

    top_level_commands = string_list(
        manifest.get("validation_commands"), "manifest.validation_commands", errors
    )
    if not top_level_commands:
        errors.append("manifest.validation_commands must not be empty")
    if not isinstance(manifest.get("updated_at"), str) or not manifest.get("updated_at", "").strip():
        errors.append("manifest.updated_at must be a non-empty string")

    agent_profiles = manifest.get("agent_profiles", {})
    expected_profiles = {
        "main": ("gpt-5.6-sol", "ultra"),
        "implementor": ("gpt-5.6-terra", "xhigh"),
        "reviewer": ("gpt-5.6-sol", "xhigh"),
    }
    if not isinstance(agent_profiles, dict):
        errors.append("manifest.agent_profiles must be an object")
    else:
        for role, (expected_model, expected_effort) in expected_profiles.items():
            profile = agent_profiles.get(role)
            label = f"manifest.agent_profiles.{role}"
            if not isinstance(profile, dict):
                errors.append(f"{label} must be an object")
                continue
            required_profile_keys = (
                "requested_model",
                "requested_reasoning_effort",
                "actual_model",
                "actual_reasoning_effort",
                "selection_status",
                "substitution_approved",
                "notes",
            )
            check_required_keys(profile, required_profile_keys, label, errors)
            if profile.get("requested_model") != expected_model:
                errors.append(f"{label}.requested_model must equal {expected_model!r}")
            if profile.get("requested_reasoning_effort") != expected_effort:
                errors.append(
                    f"{label}.requested_reasoning_effort must equal {expected_effort!r}"
                )
            for key in ("actual_model", "actual_reasoning_effort"):
                if not isinstance(profile.get(key), str) or not profile.get(key, "").strip():
                    errors.append(f"{label}.{key} must be a non-empty string")
            status = profile.get("selection_status")
            if status not in ("confirmed", "host-unverifiable", "unavailable", "substituted"):
                errors.append(f"{label}.selection_status is invalid")
            approved = profile.get("substitution_approved")
            if not isinstance(approved, bool):
                errors.append(f"{label}.substitution_approved must be boolean")
            if status == "confirmed":
                if profile.get("actual_model") != expected_model:
                    errors.append(f"{label}.confirmed profile must report actual_model {expected_model!r}")
                if profile.get("actual_reasoning_effort") != expected_effort:
                    errors.append(f"{label}.confirmed profile must report actual_reasoning_effort {expected_effort!r}")
                if approved is True:
                    errors.append(f"{label}.confirmed profile must not claim substitution approval")
            if status == "unavailable" and approved is True:
                errors.append(f"{label}.unavailable profile cannot claim substitution approval")
            if status == "substituted" and approved is not True:
                errors.append(f"{label}.substituted profile requires explicit approval")
            notes = profile.get("notes")
            if not isinstance(notes, list) or any(not isinstance(item, str) for item in notes):
                errors.append(f"{label}.notes must be an array of strings")
            if role in {"main", "implementor"} and manifest_status in ("executing", "completed"):
                ready = status == "confirmed" or (
                    status in ("host-unverifiable", "substituted")
                    and approved is True
                )
                if not ready:
                    errors.append(
                        f"{label} must be confirmed or explicitly approved before execution"
                    )

    review_gate = manifest.get("review_gate")
    if not isinstance(review_gate, dict):
        errors.append("manifest.review_gate must be an object")
    else:
        for key in ("status", "authorization_record", "review_root"):
            if key not in review_gate:
                errors.append(f"manifest.review_gate missing {key}")
        if review_gate.get("status") not in (
            "not-offered", "offered", "declined", "approved", "running", "completed", "blocked"
        ):
            errors.append("manifest.review_gate.status is invalid")
        if not isinstance(review_gate.get("authorization_record"), str):
            errors.append("manifest.review_gate.authorization_record must be a string")
        if not isinstance(review_gate.get("review_root"), str) or not review_gate.get("review_root", "").strip():
            errors.append("manifest.review_gate.review_root must be a non-empty string")
        if review_gate.get("status") in ("running", "completed") and isinstance(agent_profiles, dict):
            reviewer = agent_profiles.get("reviewer")
            if isinstance(reviewer, dict):
                reviewer_status = reviewer.get("selection_status")
                reviewer_ready = reviewer_status == "confirmed" or (
                    reviewer_status in ("host-unverifiable", "substituted")
                    and reviewer.get("substitution_approved") is True
                )
                if not reviewer_ready:
                    errors.append(
                        "manifest.agent_profiles.reviewer must be confirmed or explicitly approved while review is running or completed"
                    )

    capabilities = manifest.get("capabilities", {})
    if isinstance(capabilities, dict):
        for key in ("git", "worktrees", "subagents", "true_parallel_execution"):
            if not isinstance(capabilities.get(key), bool):
                errors.append(f"manifest.capabilities.{key} must be boolean")
        if capabilities.get("true_parallel_execution") and not (
            capabilities.get("git") and capabilities.get("worktrees") and capabilities.get("subagents")
        ):
            errors.append(
                "manifest.capabilities.true_parallel_execution requires git, worktrees, and subagents"
            )
        if not capabilities.get("true_parallel_execution"):
            warnings.append("host does not declare true parallel execution capability")
    else:
        errors.append("manifest.capabilities must be an object")

    integration = manifest.get("integration", {})
    integration_commits: list[tuple[str, str]] = []
    baseline_commit: str | None = None
    planning_commit: str | None = None
    contract_baseline_commit: str | None = None
    current_checkpoint: str | None = None
    if isinstance(integration, dict):
        for key in (
            "branch",
            "worktree",
            "baseline_commit",
            "planning_commit",
            "contract_baseline_commit",
            "current_checkpoint",
        ):
            if key not in integration:
                errors.append(f"manifest.integration missing {key}")
        branch = integration.get("branch")
        worktree = integration.get("worktree")
        if not isinstance(branch, str) or not branch.strip():
            errors.append("manifest.integration.branch must be a non-empty string")
        if not isinstance(worktree, str) or not worktree.strip():
            errors.append("manifest.integration.worktree must be a non-empty path")
        else:
            integration_path = Path(worktree).expanduser()
            if not integration_path.is_absolute():
                integration_path = repo_root / integration_path
            if not integration_path.exists():
                warnings.append(
                    f"manifest.integration.worktree does not currently exist: {integration_path}"
                )

        for key in ("baseline_commit", "planning_commit", "current_checkpoint"):
            value = integration.get(key)
            if not isinstance(value, str) or value == "pending" or not COMMIT_RE.fullmatch(value):
                errors.append(f"manifest.integration.{key} must be an existing commit ID")
            else:
                integration_commits.append((f"manifest.integration.{key}", value))

        baseline_commit = integration.get("baseline_commit")
        planning_commit = integration.get("planning_commit")
        current_checkpoint = integration.get("current_checkpoint")

        contract_baseline_commit = integration.get("contract_baseline_commit")
        if contract_baseline_commit == "pending":
            if manifest_status in ("contract-baseline-frozen", "executing", "completed"):
                errors.append(
                    "manifest.integration.contract_baseline_commit cannot be pending "
                    f"for manifest status {manifest_status}"
                )
        elif not isinstance(contract_baseline_commit, str) or not COMMIT_RE.fullmatch(
            contract_baseline_commit
        ):
            errors.append(
                "manifest.integration.contract_baseline_commit must be pending or an existing commit ID"
            )
        else:
            integration_commits.append(
                ("manifest.integration.contract_baseline_commit", contract_baseline_commit)
            )
    else:
        errors.append("manifest.integration must be an object")

    shared_owners_raw = manifest.get("shared_path_owners", [])
    shared_owners: list[dict[str, Any]] = []
    shared_owner_paths: dict[str, str] = {}
    if not isinstance(shared_owners_raw, list):
        errors.append("manifest.shared_path_owners must be an array")
    else:
        for index, entry in enumerate(shared_owners_raw):
            label = f"manifest.shared_path_owners[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: expected an object")
                continue
            entry_error_count = len(errors)
            path = entry.get("path")
            owner = entry.get("owner")
            strategy = entry.get("strategy")
            if not isinstance(path, str) or not path:
                errors.append(f"{label}.path must be a non-empty string")
            else:
                validate_path_pattern(path, f"{label}.path", errors)
                normalized_path = canonical_path_pattern(path).casefold()
                if normalized_path in shared_owner_paths:
                    errors.append(
                        f"{label}.path duplicates shared-path registry entry "
                        f"{shared_owner_paths[normalized_path]}"
                    )
                else:
                    shared_owner_paths[normalized_path] = label
            if not isinstance(owner, str) or not (owner == "MAIN" or PHASE_ID_RE.fullmatch(owner)):
                errors.append(f"{label}.owner must be MAIN or a PH-###-## ID")
            if not isinstance(strategy, str) or not strategy:
                errors.append(f"{label}.strategy must be a non-empty string")
            if len(errors) == entry_error_count:
                shared_owners.append(entry)

    contracts_raw = manifest.get("contracts", [])
    contracts: dict[str, dict[str, Any]] = {}
    if not isinstance(contracts_raw, list):
        errors.append("manifest.contracts must be an array")
    else:
        for index, contract in enumerate(contracts_raw):
            label = f"manifest.contracts[{index}]"
            if not check_required_keys(contract, CONTRACT_REQUIRED_KEYS, label, errors):
                continue
            contract_id = contract.get("id")
            if not isinstance(contract_id, str) or not CONTRACT_ID_RE.fullmatch(contract_id):
                errors.append(f"{label}.id must match CTR-###")
                continue
            if contract_id in contracts:
                errors.append(f"duplicate contract ID: {contract_id}")
                continue
            contracts[contract_id] = contract
            if not isinstance(contract.get("status"), str) or contract.get("status") not in VALID_CONTRACT_STATUSES:
                errors.append(f"{label}.status is invalid")
            owner = contract.get("owner_phase")
            if not isinstance(owner, str) or not PHASE_ID_RE.fullmatch(owner):
                errors.append(f"{label}.owner_phase must be a PH-###-## ID")
            consumers = string_list(contract.get("consumer_phases"), f"{label}.consumer_phases", errors)
            for consumer in consumers:
                if not PHASE_ID_RE.fullmatch(consumer):
                    errors.append(f"{label}.consumer_phases contains invalid ID {consumer!r}")
            commands = string_list(contract.get("validation_commands"), f"{label}.validation_commands", errors)
            if not commands:
                errors.append(f"{label}.validation_commands must not be empty")
            canonical = repo_file(repo_root, contract.get("canonical_path"), f"{label}.canonical_path", errors)
            if canonical is not None and contract.get("status") in ("frozen", "implemented") and not canonical.exists():
                errors.append(f"{label}.canonical_path does not exist for frozen contract: {canonical}")

    units_raw = manifest.get("units", [])
    units: dict[str, dict[str, Any]] = {}
    component_plans: dict[str, Path] = {}
    boundary_text_cache: dict[Path, str] = {}
    branches: dict[str, str] = {}
    worktrees: dict[str, str] = {}

    if not isinstance(units_raw, list):
        errors.append("manifest.units must be an array")
    else:
        for index, unit in enumerate(units_raw):
            label = f"manifest.units[{index}]"
            if not check_required_keys(unit, UNIT_REQUIRED_KEYS, label, errors):
                continue
            phase_id = unit.get("id")
            component_id = unit.get("component_id")
            phase_match = PHASE_ID_RE.fullmatch(phase_id) if isinstance(phase_id, str) else None
            component_match = COMPONENT_ID_RE.fullmatch(component_id) if isinstance(component_id, str) else None
            if not phase_match:
                errors.append(f"{label}.id must match PH-###-##")
                continue
            if not component_match:
                errors.append(f"{label}.component_id must match CMP-###")
                continue
            if phase_match.group(1) != component_match.group(1):
                errors.append(f"{label}: {phase_id} does not belong to {component_id}")
            if phase_id in units:
                errors.append(f"duplicate unit ID: {phase_id}")
                continue
            units[phase_id] = unit

            classification = unit.get("classification")
            if not isinstance(classification, str) or classification not in VALID_CLASSIFICATIONS:
                errors.append(f"{label}.classification is invalid")
            if not isinstance(unit.get("title"), str) or not unit.get("title", "").strip():
                errors.append(f"{label}.title must be a non-empty string")
            decision_gates = string_list(unit.get("decision_gates"), f"{label}.decision_gates", errors)
            for decision in decision_gates:
                if not DECISION_ID_RE.fullmatch(decision):
                    errors.append(f"{label}.decision_gates contains invalid ID {decision!r}")
            if classification == "decision-gated" and not decision_gates:
                errors.append(f"{label}: decision-gated unit must name at least one DEC-### gate")
            if classification == "decision-gated" and unit.get("status") != "blocked":
                errors.append(f"{phase_id}: decision-gated unit must be marked blocked")
            if decision_gates and classification != "decision-gated":
                errors.append(
                    f"{phase_id}: open decision gates require decision-gated classification"
                )

            if not isinstance(unit.get("status"), str) or unit.get("status") not in VALID_UNIT_STATUSES:
                errors.append(f"{label}.status is invalid")
            if not isinstance(unit.get("wave"), int) or unit.get("wave") < 0:
                errors.append(f"{label}.wave must be a non-negative integer")
            if not isinstance(unit.get("integration_index"), int) or unit.get("integration_index") < 0:
                errors.append(f"{label}.integration_index must be a non-negative integer")

            branch = unit.get("branch")
            worktree = unit.get("worktree")
            if not isinstance(branch, str) or not branch:
                errors.append(f"{label}.branch must be a non-empty string")
            elif branch in branches:
                errors.append(f"duplicate worker branch {branch!r}: {branches[branch]} and {phase_id}")
            else:
                branches[branch] = phase_id
            if not isinstance(worktree, str) or not worktree:
                errors.append(f"{label}.worktree must be a non-empty string")
            elif worktree in worktrees:
                errors.append(f"duplicate worker worktree {worktree!r}: {worktrees[worktree]} and {phase_id}")
            else:
                worktrees[worktree] = phase_id

            base_commit = unit.get("base_commit")
            if base_commit == "pending":
                if unit.get("status") in (
                    "ready",
                    "running",
                    "worker-completed",
                    "integration-failed",
                    "integrated",
                    "verified",
                ):
                    errors.append(f"{label}.base_commit cannot be pending for status {unit.get('status')}")
            elif not isinstance(base_commit, str) or not COMMIT_RE.fullmatch(base_commit):
                errors.append(f"{label}.base_commit must be pending or an existing commit ID")
            else:
                integration_commits.append((f"{label}.base_commit", base_commit))

            plan_path = repo_file(repo_root, unit.get("plan_path"), f"{label}.plan_path", errors)
            boundary_path = repo_file(repo_root, unit.get("boundary_path"), f"{label}.boundary_path", errors)
            prompt_path = repo_file(repo_root, unit.get("worker_prompt_path"), f"{label}.worker_prompt_path", errors)
            for artifact_label, artifact_path in (
                ("plan", plan_path),
                ("boundary", boundary_path),
                ("worker prompt", prompt_path),
            ):
                if artifact_path is not None and not artifact_path.is_file():
                    errors.append(f"{label}: {artifact_label} file does not exist: {artifact_path}")

            if plan_path is not None and plan_path.is_file():
                component_plans[component_id] = plan_path
                plan_text = read_text(plan_path, errors)
                id_match = COMPONENT_DOC_ID_RE.search(plan_text[:2000])
                if not id_match or id_match.group(1).upper() != component_id:
                    errors.append(f"{plan_path}: component ID does not match manifest unit {component_id}")
                if phase_id not in plan_text:
                    errors.append(f"{plan_path}: phase ID {phase_id} not found")

            if plan_path is not None and boundary_path is not None and plan_path.name != boundary_path.name:
                errors.append(
                    f"{label}: boundary filename must match component plan filename "
                    f"({plan_path.name!r} != {boundary_path.name!r})"
                )

            if boundary_path is not None and boundary_path.is_file():
                if boundary_path not in boundary_text_cache:
                    boundary_text_cache[boundary_path] = validate_markdown(
                        boundary_path, BOUNDARY_HEADINGS, errors
                    )
                validate_phase_boundary(
                    boundary_path,
                    boundary_text_cache[boundary_path],
                    phase_id,
                    errors,
                )

            prompt_text = ""
            prompt_label = str(prompt_path)
            expected_prompt_path_policy: dict[str, Any] | None = {
                key: unit.get(key) for key in PROMPT_PATH_POLICY_KEYS
            }
            prompt_path_policy_is_immutable = False
            if prompt_path is not None and prompt_path.is_file():
                prompt_text = read_text(prompt_path, errors)
                working_prompt_text = prompt_text
                expected_prompt_scope = (
                    scope_projection(approved_scope) if scope_prompt_values_valid else None
                )
                prompt_relative = unit.get("worker_prompt_path")
                if (
                    isinstance(base_commit, str)
                    and base_commit != "pending"
                    and COMMIT_RE.fullmatch(base_commit)
                    and commit_exists(repo_root, base_commit)
                    and isinstance(prompt_relative, str)
                ):
                    committed_prompt = git_show_text(repo_root, base_commit, prompt_relative)
                    committed_manifest = git_show_json(
                        repo_root,
                        base_commit,
                        (PARALLEL_RELATIVE_PATH / "execution-manifest.json").as_posix(),
                    )
                    prompt_label = f"{base_commit}:{prompt_relative}"
                    if committed_prompt is None:
                        errors.append(f"{prompt_label}: immutable worker prompt is missing or unreadable")
                        prompt_text = ""
                    else:
                        prompt_text = committed_prompt
                        if committed_prompt != working_prompt_text:
                            errors.append(
                                f"{prompt_path}: working prompt differs from immutable base {prompt_label}"
                            )
                    if committed_manifest is None:
                        errors.append(
                            f"unit {phase_id}: base commit {base_commit} lacks a valid execution manifest"
                        )
                        expected_prompt_scope = None
                    else:
                        if committed_manifest.get("schema_version") != 2:
                            errors.append(
                                f"unit {phase_id}: base execution manifest schema_version must equal 2"
                            )
                        committed_scope = committed_manifest.get("approved_scope")
                        if not isinstance(committed_scope, dict) or not PROMPT_SCOPE_KEYS <= set(
                            committed_scope
                        ):
                            errors.append(
                                f"unit {phase_id}: base execution manifest has no complete approved_scope"
                            )
                            expected_prompt_scope = None
                        else:
                            expected_prompt_scope = scope_projection(committed_scope)
                            if scope_prompt_values_valid and expected_prompt_scope != scope_projection(
                                approved_scope
                            ):
                                errors.append(
                                    f"unit {phase_id}: immutable base approved_scope differs from the current manifest"
                                )
                        committed_units = committed_manifest.get("units")
                        base_unit_matches = (
                            [
                                record
                                for record in committed_units
                                if isinstance(record, dict) and record.get("id") == phase_id
                            ]
                            if isinstance(committed_units, list)
                            else []
                        )
                        if len(base_unit_matches) != 1:
                            errors.append(
                                f"unit {phase_id}: immutable base manifest must contain "
                                f"exactly one matching unit; found {len(base_unit_matches)}"
                            )
                            expected_prompt_path_policy = None
                        else:
                            expected_prompt_path_policy = {
                                key: base_unit_matches[0].get(key)
                                for key in PROMPT_PATH_POLICY_KEYS
                            }
                            prompt_path_policy_is_immutable = True
                prompt_expectations = (
                    phase_id,
                    component_id,
                    "gpt-5.6-terra",
                    "xhigh",
                    str(unit.get("plan_path")),
                    str(unit.get("boundary_path")),
                    str(branch),
                    str(worktree),
                )
                for expected in prompt_expectations:
                    if expected not in prompt_text:
                        errors.append(f"{prompt_label}: worker prompt missing {expected!r}")
                if expected_prompt_scope is not None:
                    validate_prompt_scope(
                        prompt_text, expected_prompt_scope, prompt_label, errors
                    )
                elif prompt_text:
                    parse_json_block(
                        prompt_text,
                        PROMPT_SCOPE_BEGIN,
                        PROMPT_SCOPE_END,
                        PROMPT_SCOPE_KEYS,
                        prompt_label,
                        errors,
                    )

            list_values: dict[str, list[str]] = {}
            for key in (
                "consumes_contracts",
                "produces_contracts",
                "owned_paths",
                "read_only_paths",
                "shared_paths",
                "generated_paths",
                "forbidden_paths",
                "validation_commands",
                "worker_commits",
                "limitations",
                "blockers",
            ):
                list_values[key] = string_list(unit.get(key), f"{label}.{key}", errors)

            current_path_policy = {
                key: list_values[key] for key in PROMPT_PATH_POLICY_KEYS
            }
            if (
                prompt_path_policy_is_immutable
                and path_policy_is_valid(expected_prompt_path_policy)
                and current_path_policy != expected_prompt_path_policy
            ):
                errors.append(
                    f"{label}: current path policy differs from the immutable base manifest"
                )

            if prompt_text:
                validate_prompt_path_policy(
                    prompt_text, expected_prompt_path_policy, prompt_label, errors
                )

            write_capable_paths = (
                list_values["owned_paths"]
                + list_values["shared_paths"]
                + list_values["generated_paths"]
            )
            if not write_capable_paths:
                errors.append(
                    f"{label}: at least one of owned_paths, shared_paths, or "
                    "generated_paths must not be empty"
                )

            for key in (
                "owned_paths",
                "read_only_paths",
                "shared_paths",
                "generated_paths",
                "forbidden_paths",
            ):
                for path_index, pattern in enumerate(list_values[key]):
                    validate_path_pattern(pattern, f"{label}.{key}[{path_index}]", errors)

            for path_kind in ("owned_paths", "shared_paths", "generated_paths"):
                singular_kind = path_kind.removesuffix("_paths").replace("_", "-")
                for write_path in list_values[path_kind]:
                    if patterns_may_overlap(write_path, DELIVERY_STATUS_PATH):
                        errors.append(
                            f"{label}: {singular_kind} path {write_path!r} overlaps "
                            f"orchestration-owned {DELIVERY_STATUS_PATH!r}"
                        )
                    for read_only in list_values["read_only_paths"]:
                        if patterns_may_overlap(write_path, read_only):
                            errors.append(
                                f"{label}: {singular_kind} path {write_path!r} overlaps "
                                f"read-only path {read_only!r}"
                            )
                    for forbidden in list_values["forbidden_paths"]:
                        if patterns_may_overlap(write_path, forbidden):
                            errors.append(
                                f"{label}: {singular_kind} path {write_path!r} overlaps "
                                f"forbidden path {forbidden!r}"
                            )

            for owned in list_values["owned_paths"]:
                for shared in list_values["shared_paths"]:
                    if patterns_may_overlap(owned, shared):
                        errors.append(
                            f"{label}: owned path {owned!r} overlaps its own shared path "
                            f"{shared!r}"
                        )
                for generated in list_values["generated_paths"]:
                    if patterns_may_overlap(owned, generated):
                        errors.append(
                            f"{label}: owned path {owned!r} overlaps its own generated path "
                            f"{generated!r}"
                        )
            for generated in list_values["generated_paths"]:
                for shared in list_values["shared_paths"]:
                    if patterns_may_overlap(generated, shared):
                        errors.append(
                            f"{label}: generated path {generated!r} overlaps its own shared path "
                            f"{shared!r}"
                        )

            if not list_values["validation_commands"]:
                errors.append(f"{label}.validation_commands must not be empty")

            if prompt_text:
                for contract_id in list_values["consumes_contracts"] + list_values["produces_contracts"]:
                    if contract_id not in prompt_text:
                        errors.append(f"{prompt_label}: worker prompt missing contract ID {contract_id}")
                    contract = contracts.get(contract_id)
                    canonical_path = contract.get("canonical_path") if isinstance(contract, dict) else None
                    if isinstance(canonical_path, str) and canonical_path not in prompt_text:
                        errors.append(
                            f"{prompt_label}: worker prompt missing canonical contract path {canonical_path!r}"
                        )

            integration_commit = unit.get("integration_commit")
            if integration_commit != "pending":
                if not isinstance(integration_commit, str) or not COMMIT_RE.fullmatch(integration_commit):
                    errors.append(f"{label}.integration_commit must be pending or a commit ID")
                elif unit.get("status") in ("integrated", "verified"):
                    integration_commits.append((f"{label}.integration_commit", integration_commit))
            if unit.get("status") in ("integrated", "verified") and integration_commit == "pending":
                errors.append(f"{label}: integrated or verified unit must record integration_commit")

    unit_ids = set(units)
    excluded_raw = manifest.get("excluded_units", [])
    excluded_ids: set[str] = set()
    if not isinstance(excluded_raw, list):
        errors.append("manifest.excluded_units must be an array")
    else:
        for index, entry in enumerate(excluded_raw):
            label = f"manifest.excluded_units[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"{label}: expected an object")
                continue
            phase_id = entry.get("phase_id")
            reason = entry.get("reason")
            if not isinstance(phase_id, str) or not PHASE_ID_RE.fullmatch(phase_id):
                errors.append(f"{label}.phase_id must match PH-###-##")
            else:
                if phase_id in excluded_ids:
                    errors.append(f"duplicate excluded phase ID: {phase_id}")
                excluded_ids.add(phase_id)
            if not isinstance(reason, str) or not reason:
                errors.append(f"{label}.reason must be non-empty")

    approved_ids: set[str] = set()
    if isinstance(approved_scope, dict):
        approved_values = string_list(
            approved_scope.get("phase_ids"), "manifest.approved_scope.phase_ids", errors
        )
        for phase_id in approved_values:
            if not PHASE_ID_RE.fullmatch(phase_id):
                errors.append(f"manifest.approved_scope contains invalid phase ID {phase_id!r}")
            approved_ids.add(phase_id)
    if approved_ids != unit_ids:
        errors.append(
            "manifest approved phase_ids must equal executable unit IDs; "
            f"missing={sorted(unit_ids - approved_ids)}, "
            f"extra={sorted(approved_ids - unit_ids)}"
        )
    if unit_ids & excluded_ids:
        errors.append(
            f"executable and excluded phase IDs must be disjoint: {sorted(unit_ids & excluded_ids)}"
        )
    if plan_scope is not None:
        if not unit_ids <= plan_authorized_ids:
            errors.append(
                "execution units are not authorized by the canonical plan scope: "
                f"{sorted(unit_ids - plan_authorized_ids)}"
            )
        if plan_planned_ids != unit_ids | excluded_ids:
            errors.append(
                "canonical planned phases must equal executable plus excluded phases; "
                f"missing={sorted(plan_planned_ids - (unit_ids | excluded_ids))}, "
                f"extra={sorted((unit_ids | excluded_ids) - plan_planned_ids)}"
            )

    validate_unit_data_ownership(units, plan_data_ownership, shared_owners, errors)

    # Validate contract references now that units are known.
    known_phase_ids = unit_ids | excluded_ids
    for index, entry in enumerate(shared_owners):
        owner = entry.get("owner")
        if isinstance(owner, str) and owner != "MAIN" and owner not in unit_ids:
            errors.append(
                f"manifest.shared_path_owners[{index}].owner {owner} is not an executable unit; "
                "use MAIN when reconciliation is outside the approved worker scope"
            )

    for phase_id, unit in units.items():
        for shared_path in usable_string_list(unit.get("shared_paths")):
            matches = [
                entry
                for entry in shared_owners
                if isinstance(entry.get("path"), str)
                and registry_pattern_covers(entry["path"], shared_path)
            ]
            if not matches:
                errors.append(
                    f"unit {phase_id}: shared path {shared_path!r} has no shared_path_owners entry"
                )
                continue
            owners = {entry.get("owner") for entry in matches}
            if len(owners) > 1:
                errors.append(
                    f"unit {phase_id}: shared path {shared_path!r} matches conflicting owners "
                    f"{sorted(str(owner) for owner in owners)}"
                )

        exclusive_paths = usable_string_list(unit.get("owned_paths")) + usable_string_list(
            unit.get("generated_paths")
        )
        for owned_path in exclusive_paths:
            for entry in shared_owners:
                registry_path = entry.get("path")
                registry_owner = entry.get("owner")
                if (
                    isinstance(registry_path, str)
                    and patterns_may_overlap(owned_path, registry_path)
                    and registry_owner != phase_id
                ):
                    errors.append(
                        f"unit {phase_id}: exclusive or generated path {owned_path!r} overlaps "
                        "shared registry path "
                        f"{registry_path!r} owned by {registry_owner}; list it as shared or assign "
                        "this unit as the reconciliation owner"
                    )

    unit_consumes = {
        phase_id: set(usable_string_list(unit.get("consumes_contracts")))
        for phase_id, unit in units.items()
    }
    unit_produces = {
        phase_id: set(usable_string_list(unit.get("produces_contracts")))
        for phase_id, unit in units.items()
    }

    for contract_id, contract in contracts.items():
        owner = contract.get("owner_phase")
        if isinstance(owner, str) and owner not in known_phase_ids:
            warnings.append(f"{contract_id}: owner phase {owner} is outside approved or excluded scope")
        elif owner in units and contract_id not in unit_produces[owner]:
            errors.append(
                f"{contract_id}: owner phase {owner} does not list the contract in produces_contracts"
            )
        for consumer in contract.get("consumer_phases", []):
            if consumer not in known_phase_ids:
                warnings.append(f"{contract_id}: consumer phase {consumer} is outside scope")
            elif consumer in units and contract_id not in unit_consumes[consumer]:
                errors.append(
                    f"{contract_id}: consumer phase {consumer} does not list the contract in consumes_contracts"
                )

    for phase_id, contract_ids in unit_produces.items():
        for contract_id in contract_ids:
            contract = contracts.get(contract_id)
            if contract is not None and contract.get("owner_phase") != phase_id:
                errors.append(
                    f"unit {phase_id}: produces {contract_id}, but its registered owner is "
                    f"{contract.get('owner_phase')}"
                )
    for phase_id, contract_ids in unit_consumes.items():
        for contract_id in contract_ids:
            contract = contracts.get(contract_id)
            if contract is not None and phase_id not in contract.get("consumer_phases", []):
                errors.append(
                    f"unit {phase_id}: consumes {contract_id}, but it is absent from consumer_phases"
                )

    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse_dependencies: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for phase_id, unit in units.items():
        label = f"unit {phase_id}"
        consumed = unit_consumes[phase_id]
        produced = unit_produces[phase_id]
        dependencies = unit.get("dependencies")
        if not isinstance(dependencies, list):
            errors.append(f"{label}.dependencies must be an array")
            continue
        dependency_types: set[str] = set()
        seen_providers: set[str] = set()
        for index, dependency in enumerate(dependencies):
            dep_label = f"{label}.dependencies[{index}]"
            if not isinstance(dependency, dict):
                errors.append(f"{dep_label}: expected an object")
                continue
            provider = dependency.get("phase_id")
            dep_type = dependency.get("type")
            reason = dependency.get("reason")
            contract_ids = string_list(
                dependency.get("contract_ids"), f"{dep_label}.contract_ids", errors
            )
            if not isinstance(provider, str) or not PHASE_ID_RE.fullmatch(provider):
                errors.append(f"{dep_label}.phase_id must match PH-###-##")
                continue
            if provider not in unit_ids:
                errors.append(f"{dep_label}: provider {provider} is not an executable manifest unit")
                continue
            if provider == phase_id:
                errors.append(f"{dep_label}: a unit cannot depend on itself")
            if provider in seen_providers:
                errors.append(f"{dep_label}: duplicate predecessor {provider}")
            seen_providers.add(provider)
            if not isinstance(dep_type, str) or dep_type not in VALID_DEPENDENCY_TYPES:
                errors.append(f"{dep_label}.type must be contract-bound or implementation-bound")
                continue
            dependency_types.add(dep_type)
            if not isinstance(reason, str) or not reason:
                errors.append(f"{dep_label}.reason must be non-empty")
            if dep_type == "contract-bound" and not contract_ids:
                errors.append(f"{dep_label}: contract-bound edge must name at least one CTR-###")
            if dep_type == "implementation-bound" and contract_ids:
                warnings.append(
                    f"{dep_label}: implementation-bound edge names contracts; ensure they do not imply safe parallelism"
                )
            for contract_id in contract_ids:
                contract = contracts.get(contract_id)
                if contract is None:
                    errors.append(f"{dep_label}: unknown contract ID {contract_id}")
                elif contract.get("status") not in ("frozen", "implemented"):
                    errors.append(
                        f"{dep_label}: consumed contract {contract_id} is not frozen or implemented"
                    )
                else:
                    if contract.get("owner_phase") != provider:
                        errors.append(
                            f"{dep_label}: contract {contract_id} is owned by "
                            f"{contract.get('owner_phase')}, not provider {provider}"
                        )
                    if contract_id not in consumed:
                        errors.append(
                            f"{dep_label}: contract {contract_id} is absent from {phase_id}.consumes_contracts"
                        )
            adjacency[provider].add(phase_id)
            reverse_dependencies[phase_id].append((provider, dep_type))

        for contract_id in consumed | produced:
            if not CONTRACT_ID_RE.fullmatch(contract_id):
                errors.append(f"{label}: invalid contract ID {contract_id!r}")
            elif contract_id not in contracts:
                errors.append(f"{label}: unknown contract ID {contract_id}")

        if usable_string_list(unit.get("decision_gates")):
            expected_classification = "decision-gated"
        elif "implementation-bound" in dependency_types:
            expected_classification = "implementation-bound"
        elif "contract-bound" in dependency_types:
            expected_classification = "contract-bound"
        else:
            expected_classification = "independent"
        if unit.get("classification") != expected_classification:
            errors.append(
                f"{label}: classification must be {expected_classification!r} from its active gates "
                f"and dependency edges, got {unit.get('classification')!r}"
            )
        if expected_classification == "contract-bound" and not consumed:
            errors.append(f"{label}: contract-bound classification requires consumed contracts")

    cycle = find_cycle(unit_ids, adjacency)
    if cycle:
        errors.append(f"dependency graph contains a cycle: {' -> '.join(cycle)}")

    waves_raw = manifest.get("waves", [])
    waves: dict[int, dict[str, Any]] = {}
    unit_wave_membership: dict[str, int] = {}
    if not isinstance(waves_raw, list):
        errors.append("manifest.waves must be an array")
    else:
        for index, wave in enumerate(waves_raw):
            label = f"manifest.waves[{index}]"
            if not isinstance(wave, dict):
                errors.append(f"{label}: expected an object")
                continue
            number = wave.get("number")
            base_commit = wave.get("base_commit")
            phase_ids = string_list(wave.get("phase_ids"), f"{label}.phase_ids", errors)
            status = wave.get("status")
            if not isinstance(number, int) or number < 0:
                errors.append(f"{label}.number must be a non-negative integer")
                continue
            if number in waves:
                errors.append(f"duplicate wave number: {number}")
                continue
            waves[number] = wave
            if not isinstance(status, str) or status not in VALID_WAVE_STATUSES:
                errors.append(f"{label}.status is invalid")
            if base_commit == "pending":
                if status in ("ready", "running", "integrating", "completed"):
                    errors.append(f"{label}.base_commit cannot be pending for status {status}")
            elif not isinstance(base_commit, str) or not COMMIT_RE.fullmatch(base_commit):
                errors.append(f"{label}.base_commit must be pending or an existing commit ID")
            else:
                integration_commits.append((f"{label}.base_commit", base_commit))
            for phase_id in phase_ids:
                if phase_id not in unit_ids:
                    errors.append(f"{label}: unknown unit {phase_id}")
                    continue
                if phase_id in unit_wave_membership:
                    errors.append(
                        f"unit {phase_id} appears in waves {unit_wave_membership[phase_id]} and {number}"
                    )
                unit_wave_membership[phase_id] = number
                unit = units[phase_id]
                if unit.get("wave") != number:
                    errors.append(f"{label}: {phase_id} has unit.wave={unit.get('wave')}")
                if unit.get("base_commit") != base_commit:
                    errors.append(f"{label}: {phase_id} base commit differs from wave base commit")

    if set(unit_wave_membership) != unit_ids:
        errors.append(
            "every executable unit must appear in exactly one wave; "
            f"missing={sorted(unit_ids - set(unit_wave_membership))}"
        )

    for consumer, dependencies in reverse_dependencies.items():
        consumer_wave = units[consumer].get("wave")
        for provider, dep_type in dependencies:
            provider_wave = units[provider].get("wave")
            if not isinstance(provider_wave, int) or not isinstance(consumer_wave, int):
                continue
            if dep_type == "implementation-bound" and provider_wave >= consumer_wave:
                errors.append(
                    f"implementation-bound edge {provider} -> {consumer} requires provider wave < consumer wave"
                )
            if dep_type == "contract-bound" and provider_wave > consumer_wave:
                warnings.append(
                    f"contract-bound provider {provider} is scheduled after consumer {consumer}; "
                    "ensure the frozen contract baseline is sufficient"
                )

    integration_order_values = string_list(
        manifest.get("integration_order"), "manifest.integration_order", errors
    )
    integration_order = [value for value in integration_order_values if PHASE_ID_RE.fullmatch(value)]
    if set(integration_order) != unit_ids or len(integration_order) != len(unit_ids):
        errors.append(
            "integration_order must contain every executable unit exactly once; "
            f"missing={sorted(unit_ids - set(integration_order))}, "
            f"extra={sorted(set(integration_order) - unit_ids)}"
        )
    order_index = {phase_id: index for index, phase_id in enumerate(integration_order)}
    for provider, consumers in adjacency.items():
        for consumer in consumers:
            if provider in order_index and consumer in order_index and order_index[provider] >= order_index[consumer]:
                errors.append(f"integration_order violates dependency {provider} -> {consumer}")
    for phase_id, unit in units.items():
        if phase_id in order_index and unit.get("integration_index") != order_index[phase_id]:
            errors.append(
                f"{phase_id}: integration_index={unit.get('integration_index')} "
                f"but order position is {order_index[phase_id]}"
            )

    # A resolved contract baseline must actually contain every frozen artifact that workers use.
    if (
        isinstance(contract_baseline_commit, str)
        and contract_baseline_commit != "pending"
        and COMMIT_RE.fullmatch(contract_baseline_commit)
        and commit_exists(repo_root, contract_baseline_commit)
    ):
        for filename in REQUIRED_FILES:
            relative = (PARALLEL_RELATIVE_PATH / filename).as_posix()
            if not commit_contains_path(repo_root, contract_baseline_commit, relative):
                errors.append(
                    f"contract baseline {contract_baseline_commit} does not contain {relative}"
                )
        for contract_id, contract in contracts.items():
            canonical_path = contract.get("canonical_path")
            if (
                contract.get("status") in ("frozen", "implemented")
                and isinstance(canonical_path, str)
                and not commit_contains_path(repo_root, contract_baseline_commit, canonical_path)
            ):
                errors.append(
                    f"contract baseline {contract_baseline_commit} does not contain "
                    f"{contract_id} canonical path {canonical_path}"
                )

    # Every resolved worker base must contain its packet and consumed contracts.
    for phase_id, unit in units.items():
        unit_base = unit.get("base_commit")
        if (
            not isinstance(unit_base, str)
            or unit_base == "pending"
            or not COMMIT_RE.fullmatch(unit_base)
            or not commit_exists(repo_root, unit_base)
        ):
            continue

        for field in ("plan_path", "boundary_path", "worker_prompt_path"):
            relative = unit.get(field)
            if isinstance(relative, str) and not commit_contains_path(repo_root, unit_base, relative):
                errors.append(
                    f"unit {phase_id}: base commit {unit_base} does not contain {field} {relative}"
                )
        for contract_id in unit_consumes[phase_id]:
            contract = contracts.get(contract_id)
            canonical_path = contract.get("canonical_path") if contract else None
            if isinstance(canonical_path, str) and not commit_contains_path(
                repo_root, unit_base, canonical_path
            ):
                errors.append(
                    f"unit {phase_id}: base commit {unit_base} does not contain consumed "
                    f"contract {contract_id} at {canonical_path}"
                )

        for provider, dep_type in reverse_dependencies.get(phase_id, []):
            if dep_type != "implementation-bound":
                continue
            provider_unit = units[provider]
            provider_integration = provider_unit.get("integration_commit")
            if provider_unit.get("status") not in ("integrated", "verified"):
                errors.append(
                    f"unit {phase_id}: resolved base requires implementation-bound predecessor "
                    f"{provider} to be integrated or verified"
                )
                continue
            if (
                not isinstance(provider_integration, str)
                or provider_integration == "pending"
                or not COMMIT_RE.fullmatch(provider_integration)
                or not commit_exists(repo_root, provider_integration)
            ):
                errors.append(
                    f"unit {phase_id}: predecessor {provider} lacks an existing integration commit"
                )
                continue
            if not is_ancestor(repo_root, provider_integration, unit_base):
                errors.append(
                    f"unit {phase_id}: base commit {unit_base} does not contain implementation "
                    f"predecessor {provider} commit {provider_integration}"
                )

    validate_same_wave_write_ownership(units, shared_owners, errors)

    # Boundary count and mapping: one boundary per included component plan.
    boundary_dir = parallel_root / "boundaries"
    boundary_files = sorted(boundary_dir.glob("*.md")) if boundary_dir.is_dir() else []
    expected_boundary_names = {path.name for path in component_plans.values()}
    actual_boundary_names = {path.name for path in boundary_files}
    if expected_boundary_names != actual_boundary_names:
        errors.append(
            "boundary documents must map one-to-one to included component plans; "
            f"missing={sorted(expected_boundary_names - actual_boundary_names)}, "
            f"extra={sorted(actual_boundary_names - expected_boundary_names)}"
        )

    # Verify referenced commit IDs exist.
    seen_commit_labels: set[tuple[str, str]] = set()
    for label, commit in integration_commits:
        pair = (label, commit)
        if pair in seen_commit_labels:
            continue
        seen_commit_labels.add(pair)
        if not commit_exists(repo_root, commit):
            errors.append(f"{label}: commit does not exist in repository: {commit}")

    def existing_commit(value: str | None) -> bool:
        return bool(
            isinstance(value, str)
            and value != "pending"
            and COMMIT_RE.fullmatch(value)
            and commit_exists(repo_root, value)
        )

    if existing_commit(baseline_commit) and existing_commit(planning_commit):
        assert baseline_commit is not None and planning_commit is not None
        if not is_ancestor(repo_root, baseline_commit, planning_commit):
            errors.append(
                "manifest.integration.planning_commit must descend from baseline_commit"
            )
    if existing_commit(planning_commit) and existing_commit(current_checkpoint):
        assert planning_commit is not None and current_checkpoint is not None
        if not is_ancestor(repo_root, planning_commit, current_checkpoint):
            errors.append(
                "manifest.integration.current_checkpoint must descend from planning_commit"
            )
    if existing_commit(contract_baseline_commit):
        assert contract_baseline_commit is not None
        if existing_commit(planning_commit):
            assert planning_commit is not None
            if not is_ancestor(repo_root, planning_commit, contract_baseline_commit):
                errors.append(
                    "manifest.integration.contract_baseline_commit must descend from planning_commit"
                )
        if existing_commit(current_checkpoint):
            assert current_checkpoint is not None
            if not is_ancestor(repo_root, contract_baseline_commit, current_checkpoint):
                errors.append(
                    "manifest.integration.current_checkpoint must contain contract_baseline_commit"
                )

    if existing_commit(current_checkpoint):
        assert current_checkpoint is not None
        for phase_id, unit in units.items():
            unit_base = unit.get("base_commit")
            if existing_commit(unit_base) and not is_ancestor(repo_root, unit_base, current_checkpoint):
                errors.append(
                    f"unit {phase_id}: base commit {unit_base} is not contained in current checkpoint "
                    f"{current_checkpoint}"
                )

    print(f"Parallel root: {parallel_root}")
    print(f"Contracts: {len(contracts)}")
    print(f"Units: {len(units)}")
    print(f"Waves: {len(waves)}")
    print(f"Boundary documents: {len(boundary_files)}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  - {warning}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  - {error}")
        print(f"\nValidation failed with {len(errors)} error(s) and {len(warnings)} warning(s).")
        return 1

    print(f"\nValidation passed with 0 errors and {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
