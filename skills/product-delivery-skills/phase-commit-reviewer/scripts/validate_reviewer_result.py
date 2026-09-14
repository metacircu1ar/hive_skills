#!/usr/bin/env python3
"""Validate one phase-commit reviewer JSON result using only the standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PHASE_RE = re.compile(r"^PH-\d{3,}-\d{2,}$")
COMPONENT_RE = re.compile(r"^CMP-\d{3,}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
FINDING_RE = re.compile(r"^RVW-(PH-\d{3,}-\d{2,})-\d{3,}$")
STATUSES = {"COMPLETED", "COMPLETED_WITH_LIMITATIONS", "MODEL_BLOCKER", "SCOPE_BLOCKER", "FAILED"}
VERDICTS = {"CONFIRMED", "PLAUSIBLE"}
SEVERITIES = {"critical", "high", "medium", "low"}
CATEGORIES = {
    "correctness", "security", "authorization", "tenant-isolation", "data-integrity",
    "migration", "contract", "compatibility", "concurrency", "reliability",
    "performance", "resource-lifecycle", "observability", "test-gap",
    "plan-compliance", "boundary-compliance", "reuse", "simplification",
    "conventions", "other",
}
REFERENCE_KINDS = {"plan", "boundary", "contract", "architecture", "repository-rule", "test", "code", "other"}
LATER_STATUSES = {"not-fixed", "fixed", "superseded", "unknown"}
COMMAND_STATUSES = {"passed", "failed", "not-run"}
PROFILE_STATUSES = {"confirmed", "host-unverifiable", "unavailable", "substituted"}


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def exact_keys(value: Any, required: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return False
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required)
    if missing:
        errors.append(f"{label} missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"{label} has unexpected keys: {', '.join(extra)}")
    return not missing


def validate_location(value: Any, label: str, errors: list[str]) -> None:
    required = {"file", "line"}
    if not exact_keys(value, required, label, errors):
        return
    if not nonempty(value.get("file")):
        errors.append(f"{label}.file must be non-empty")
    line = value.get("line")
    if line is not None and (not isinstance(line, int) or line < 1):
        errors.append(f"{label}.line must be null or a positive integer")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--component")
    parser.add_argument("--target")
    parser.add_argument("--parent")
    parser.add_argument("--baseline")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        data = json.loads(args.result.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    top_keys = {
        "schema_version", "status", "reviewer_profile", "phase_id", "component_id",
        "target_commit", "target_parent", "review_baseline_commit", "reviewed_at",
        "commands_run", "limitations", "findings",
    }
    if not exact_keys(data, top_keys, "result", errors):
        data = data if isinstance(data, dict) else {}

    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    status = data.get("status")
    if status not in STATUSES:
        errors.append("status is invalid")

    phase = data.get("phase_id")
    component = data.get("component_id")
    if not isinstance(phase, str) or not PHASE_RE.fullmatch(phase):
        errors.append("phase_id must match PH-###-##")
    if not isinstance(component, str) or not COMPONENT_RE.fullmatch(component):
        errors.append("component_id must match CMP-###")
    if isinstance(phase, str) and isinstance(component, str):
        if phase.split("-")[1] != component.split("-")[1]:
            errors.append("phase_id must belong to component_id")

    for key in ("target_commit", "target_parent", "review_baseline_commit"):
        value = data.get(key)
        if not isinstance(value, str) or not COMMIT_RE.fullmatch(value):
            errors.append(f"{key} must be a 7-64 character hexadecimal commit ID")

    expected = {
        "phase_id": args.phase,
        "component_id": args.component,
        "target_commit": args.target,
        "target_parent": args.parent,
        "review_baseline_commit": args.baseline,
    }
    for key, supplied in expected.items():
        if supplied is not None and data.get(key) != supplied:
            errors.append(f"{key} does not match the expected value")

    profile_keys = {
        "requested_model", "requested_reasoning_effort", "actual_model",
        "actual_reasoning_effort", "selection_status", "substitution_approved",
    }
    profile = data.get("reviewer_profile")
    if exact_keys(profile, profile_keys, "reviewer_profile", errors):
        if profile.get("requested_model") != "gpt-5.6-sol":
            errors.append("reviewer_profile.requested_model must equal 'gpt-5.6-sol'")
        if profile.get("requested_reasoning_effort") != "xhigh":
            errors.append("reviewer_profile.requested_reasoning_effort must equal 'xhigh'")
        if not nonempty(profile.get("actual_model")):
            errors.append("reviewer_profile.actual_model must be non-empty")
        if not nonempty(profile.get("actual_reasoning_effort")):
            errors.append("reviewer_profile.actual_reasoning_effort must be non-empty")
        selection = profile.get("selection_status")
        if selection not in PROFILE_STATUSES:
            errors.append("reviewer_profile.selection_status is invalid")
        approved = profile.get("substitution_approved")
        if not isinstance(approved, bool):
            errors.append("reviewer_profile.substitution_approved must be boolean")
        if selection == "confirmed":
            if profile.get("actual_model") != "gpt-5.6-sol":
                errors.append("confirmed reviewer profile must report actual_model 'gpt-5.6-sol'")
            if profile.get("actual_reasoning_effort") != "xhigh":
                errors.append("confirmed reviewer profile must report actual_reasoning_effort 'xhigh'")
            if approved is True:
                errors.append("confirmed reviewer profile must not claim substitution approval")
        if selection == "unavailable":
            if status != "MODEL_BLOCKER":
                errors.append("unavailable reviewer profile requires MODEL_BLOCKER status")
            if approved is True:
                errors.append("unavailable reviewer profile cannot claim substitution approval")
        if status == "MODEL_BLOCKER" and selection != "unavailable":
            errors.append("MODEL_BLOCKER status requires selection_status 'unavailable'")
        ready = selection == "confirmed" or (
            selection in {"host-unverifiable", "substituted"}
            and approved is True
        )
        if status in {"COMPLETED", "COMPLETED_WITH_LIMITATIONS"} and not ready:
            errors.append("completed review requires a confirmed or explicitly approved reviewer profile")

    if not nonempty(data.get("reviewed_at")):
        errors.append("reviewed_at must be non-empty")

    commands = data.get("commands_run")
    if not isinstance(commands, list):
        errors.append("commands_run must be an array")
    else:
        for index, command in enumerate(commands):
            label = f"commands_run[{index}]"
            if exact_keys(command, {"command", "status", "summary"}, label, errors):
                if not nonempty(command.get("command")):
                    errors.append(f"{label}.command must be non-empty")
                if command.get("status") not in COMMAND_STATUSES:
                    errors.append(f"{label}.status is invalid")
                if not nonempty(command.get("summary")):
                    errors.append(f"{label}.summary must be non-empty")

    limitations = data.get("limitations")
    if not isinstance(limitations, list) or any(not isinstance(item, str) for item in limitations):
        errors.append("limitations must be an array of strings")

    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    if len(findings) > 15:
        errors.append("findings may contain at most 15 entries")
    if status in {"MODEL_BLOCKER", "SCOPE_BLOCKER", "FAILED"} and findings:
        errors.append("blocked or failed result must not contain findings")

    finding_keys = {
        "id", "verdict", "severity", "category", "target_location", "final_location",
        "summary", "failure_scenario", "evidence", "references",
        "introduced_by_target_commit", "present_at_review_baseline",
        "later_commit_status", "recommended_owner_phase", "recommended_fix",
        "recommended_test", "confidence_notes",
    }
    seen: set[str] = set()
    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not exact_keys(finding, finding_keys, label, errors):
            continue
        finding_id = finding.get("id")
        match = FINDING_RE.fullmatch(finding_id or "") if isinstance(finding_id, str) else None
        if not match or match.group(1) != phase:
            errors.append(f"{label}.id must be namespaced to result phase")
        elif finding_id in seen:
            errors.append(f"duplicate finding ID: {finding_id}")
        else:
            seen.add(finding_id)
        if finding.get("verdict") not in VERDICTS:
            errors.append(f"{label}.verdict is invalid")
        if finding.get("severity") not in SEVERITIES:
            errors.append(f"{label}.severity is invalid")
        if finding.get("category") not in CATEGORIES:
            errors.append(f"{label}.category is invalid")
        validate_location(finding.get("target_location"), f"{label}.target_location", errors)
        final_location = finding.get("final_location")
        if final_location is not None:
            validate_location(final_location, f"{label}.final_location", errors)
        for key in ("summary", "failure_scenario", "evidence", "recommended_fix", "recommended_test", "confidence_notes"):
            if not nonempty(finding.get(key)):
                errors.append(f"{label}.{key} must be non-empty")
        references = finding.get("references")
        if not isinstance(references, list):
            errors.append(f"{label}.references must be an array")
        else:
            for ref_index, reference in enumerate(references):
                ref_label = f"{label}.references[{ref_index}]"
                if exact_keys(reference, {"kind", "path", "detail"}, ref_label, errors):
                    if reference.get("kind") not in REFERENCE_KINDS:
                        errors.append(f"{ref_label}.kind is invalid")
                    if not nonempty(reference.get("path")) or not nonempty(reference.get("detail")):
                        errors.append(f"{ref_label}.path and detail must be non-empty")
        for key in ("introduced_by_target_commit", "present_at_review_baseline"):
            if not isinstance(finding.get(key), bool):
                errors.append(f"{label}.{key} must be boolean")
        if finding.get("later_commit_status") not in LATER_STATUSES:
            errors.append(f"{label}.later_commit_status is invalid")
        owner = finding.get("recommended_owner_phase")
        if not isinstance(owner, str) or not PHASE_RE.fullmatch(owner):
            errors.append(f"{label}.recommended_owner_phase must match PH-###-##")

    for error in errors:
        print(f"ERROR: {error}")
    print(f"Validated reviewer result with {len(errors)} error(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
