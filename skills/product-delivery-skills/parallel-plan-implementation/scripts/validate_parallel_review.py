#!/usr/bin/env python3
"""Validate the parallel phase-commit review package and its Git mappings."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

PLAN_ROOT = Path("docs") / "implementation-plan"
PARALLEL_ROOT = PLAN_ROOT / "parallel-implementation"
REVIEW_ROOT = PARALLEL_ROOT / "parallel-review"
PHASE_RE = re.compile(r"^PH-(\d{3,})-(\d{2,})$")
COMPONENT_RE = re.compile(r"^CMP-(\d{3,})$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
FINDING_RE = re.compile(r"^RVW-(PH-\d{3,}-\d{2,})-(\d{3,})$")
BATCH_RE = re.compile(r"^RB-\d{3,}$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

REQUIRED_FILES = (
    "README.md", "review-manifest.json", "review-ledger.md", "commit-map.md"
)
REQUIRED_DIRS = ("findings", "reviewer-prompts")
README_HEADINGS = (
    "review status and authorization", "frozen review baseline",
    "requested and actual reviewer profile", "phase commit scope",
    "review execution", "finding adjudication", "history reconstruction",
    "final validation", "document index", "remaining risks and publication gates",
)
LEDGER_HEADINGS = (
    "ledger status", "review authorization and baseline", "reviewer dispatch records",
    "raw finding registry", "main-agent dispositions", "fixes and regression tests",
    "contract changes", "history reconstruction records",
    "conflict resolutions during replay", "original-to-current phase commit map",
    "validation summary", "pre-existing failures and environmental limitations",
    "retained refs, branches, and worktrees", "remaining blockers and publication gates",
)
MAP_HEADINGS = (
    "map status", "pre-phase base commit", "frozen original review baseline",
    "phase order", "non-phase orchestration commits", "original-to-current mapping",
    "findings amended per phase", "test-only amendments per phase",
    "conflict resolutions during replay", "final code checkpoint", "metadata commit",
    "remote publication status",
)
RESULT_STATUSES = {"COMPLETED", "COMPLETED_WITH_LIMITATIONS", "MODEL_BLOCKER", "SCOPE_BLOCKER", "FAILED"}
REVIEW_STATUSES = {"preparing", "reviewing", "findings-received", "verifying-findings", "rewriting", "validating", "blocked", "completed"}
PHASE_STATUSES = {"planned", "running", "completed", "completed-with-limitations", "model-blocked", "scope-blocked", "failed", "verified", "fixed", "blocked"}
DISPOSITIONS = {"confirmed", "rejected", "duplicate", "already-fixed", "reassigned"}
DISPOSITION_STATUSES = {"pending", "fixed", "blocked", "not-applicable"}
FINDING_VERDICTS = {"CONFIRMED", "PLAUSIBLE"}
PROFILE_STATUSES = {"confirmed", "host-unverifiable", "unavailable", "substituted"}
COUNT_KEYS = {"reported", "confirmed", "rejected", "duplicate", "already_fixed", "reassigned", "fixed", "blocked", "tests_added"}
DELIVERY_SCOPE_MODES = {
    "full product", "scoped change", "modernization or migration", "remediation or reliability"
}
PROMPT_SCOPE_BEGIN = "<!-- approved-scope:begin -->"
PROMPT_SCOPE_END = "<!-- approved-scope:end -->"
PROMPT_SCOPE_KEYS = {
    "delivery_scope_mode", "requested_outcome", "impact_cone",
    "preserved_behavior", "non_goals",
}


def normalize_heading(value: str) -> str:
    value = re.sub(r"[`*_]", "", value)
    return re.sub(r"\s+", " ", value.strip().lower())


def parse_datetime(value: Any, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty date-time")
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{label} is not a valid ISO-8601 date-time")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} must include a timezone offset")
        return None
    return parsed


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except OSError as exc:
        errors.append(f"{path}: cannot read: {exc}")
        return {}
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path}: top-level value must be an object")
        return {}
    return value


def required_keys(value: Any, required: Iterable[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: expected an object")
        return False
    missing = [key for key in required if key not in value]
    if missing:
        errors.append(f"{label}: missing keys: {', '.join(missing)}")
        return False
    return True


def parse_prompt_scope(text: str, label: str, errors: list[str]) -> dict[str, Any] | None:
    if text.count(PROMPT_SCOPE_BEGIN) != 1 or text.count(PROMPT_SCOPE_END) != 1:
        errors.append(f"{label}: expected exactly one approved-scope block")
        return None
    start = text.find(PROMPT_SCOPE_BEGIN) + len(PROMPT_SCOPE_BEGIN)
    end = text.find(PROMPT_SCOPE_END, start)
    if end < start:
        errors.append(f"{label}: approved-scope markers are out of order")
        return None
    try:
        value = json.loads(
            text[start:end].strip(), object_pairs_hook=reject_duplicate_keys
        )
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{label}: invalid approved-scope JSON: {exc}")
        return None
    if not isinstance(value, dict) or set(value) != PROMPT_SCOPE_KEYS:
        actual = set(value) if isinstance(value, dict) else set()
        errors.append(
            f"{label}: approved-scope keys differ; "
            f"missing={sorted(PROMPT_SCOPE_KEYS - actual)}, "
            f"extra={sorted(actual - PROMPT_SCOPE_KEYS)}"
        )
        return None
    return value


def validate_markdown(path: Path, headings: Iterable[str], errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path}: cannot read: {exc}")
        return
    available = {normalize_heading(m.group(2)) for m in HEADING_RE.finditer(text)}
    for heading in headings:
        if normalize_heading(heading) not in available:
            errors.append(f"{path}: missing required section {heading!r}")


def commit_exists(repo: Path, commit: Any) -> bool:
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        return False
    return subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def git_show_json(repo: Path, commit: Any, relative_path: str) -> dict[str, Any] | None:
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        return None
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{relative_path}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode != 0:
        return None
    try:
        value = json.loads(
            result.stdout.decode("utf-8"), object_pairs_hook=reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def resolve_ref(repo: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def last_commit_for_path(repo: Path, relative_path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%H", "HEAD", "--", relative_path],
        capture_output=True,
        text=True,
        check=False,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and COMMIT_RE.fullmatch(value) else None


def parent_of(repo: Path, commit: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", f"{commit}^1"],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def commit_message(repo: Path, commit: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", "-s", "--format=%B", commit],
        capture_output=True, text=True, check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def repo_path(repo: Path, value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty repository-relative path")
        return None
    raw = Path(value)
    if raw.is_absolute():
        errors.append(f"{label}: must be repository-relative")
        return None
    candidate = (repo / raw).resolve()
    try:
        candidate.relative_to(repo)
    except ValueError:
        errors.append(f"{label}: path escapes repository root")
        return None
    return candidate


def validate_profile(value: Any, errors: list[str], *, active: bool) -> None:
    keys = (
        "requested_model", "requested_reasoning_effort", "actual_model",
        "actual_reasoning_effort", "selection_status", "substitution_approved",
    )
    if not required_keys(value, keys, "reviewer_profile", errors):
        return
    assert isinstance(value, dict)
    if value.get("requested_model") != "gpt-5.6-sol":
        errors.append("reviewer_profile.requested_model must equal 'gpt-5.6-sol'")
    if value.get("requested_reasoning_effort") != "xhigh":
        errors.append("reviewer_profile.requested_reasoning_effort must equal 'xhigh'")
    for key in ("actual_model", "actual_reasoning_effort"):
        if not isinstance(value.get(key), str) or not value.get(key, "").strip():
            errors.append(f"reviewer_profile.{key} must be non-empty")
    status = value.get("selection_status")
    if not isinstance(status, str) or status not in PROFILE_STATUSES:
        errors.append("reviewer_profile.selection_status is invalid")
    approved = value.get("substitution_approved")
    if not isinstance(approved, bool):
        errors.append("reviewer_profile.substitution_approved must be boolean")
    if status == "confirmed":
        if value.get("actual_model") != "gpt-5.6-sol":
            errors.append("confirmed reviewer profile must report actual_model 'gpt-5.6-sol'")
        if value.get("actual_reasoning_effort") != "xhigh":
            errors.append("confirmed reviewer profile must report actual_reasoning_effort 'xhigh'")
        if approved is True:
            errors.append("confirmed reviewer profile must not claim substitution approval")
    if status == "unavailable" and approved is True:
        errors.append("unavailable reviewer profile cannot claim substitution approval")
    ready = status == "confirmed" or (
        status in ("host-unverifiable", "substituted")
        and approved is True
    )
    if active and not ready:
        errors.append("active review requires a confirmed or explicitly approved reviewer profile")


def validate_findings(path: Path, phase: dict[str, Any], profile: dict[str, Any], baseline: str, errors: list[str]) -> list[dict[str, Any]]:
    data = read_json(path, errors)
    required = (
        "schema_version", "status", "reviewer_profile", "phase_id", "component_id",
        "target_commit", "target_parent", "review_baseline_commit", "reviewed_at",
        "commands_run", "limitations", "findings",
    )
    if not required_keys(data, required, str(path), errors):
        return []
    if data.get("schema_version") != 1:
        errors.append(f"{path}: schema_version must equal 1")
    if not isinstance(data.get("status"), str) or data.get("status") not in RESULT_STATUSES:
        errors.append(f"{path}: invalid status")
    comparisons = {
        "phase_id": phase.get("phase_id"),
        "component_id": phase.get("component_id"),
        "target_commit": phase.get("original_commit"),
        "target_parent": phase.get("original_parent"),
        "review_baseline_commit": baseline,
    }
    for key, expected in comparisons.items():
        if data.get(key) != expected:
            errors.append(f"{path}: {key} does not match review manifest")
    if data.get("reviewer_profile") != profile:
        errors.append(f"{path}: reviewer_profile does not match review manifest")
    if not isinstance(data.get("commands_run"), list):
        errors.append(f"{path}: commands_run must be an array")
    if not isinstance(data.get("limitations"), list) or any(not isinstance(x, str) for x in data.get("limitations", [])):
        errors.append(f"{path}: limitations must be an array of strings")
    findings = data.get("findings")
    if not isinstance(findings, list):
        errors.append(f"{path}: findings must be an array")
        return []
    if len(findings) > 15:
        errors.append(f"{path}: findings exceeds cap of 15")
    result_status = data.get("status")
    if result_status in ("MODEL_BLOCKER", "SCOPE_BLOCKER", "FAILED") and findings:
        errors.append(f"{path}: blocked or failed result must not contain findings")
    if result_status == "MODEL_BLOCKER" and profile.get("selection_status") != "unavailable":
        errors.append(f"{path}: MODEL_BLOCKER requires an unavailable reviewer profile")
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for index, finding in enumerate(findings):
        label = f"{path}: findings[{index}]"
        required_finding = (
            "id", "verdict", "severity", "category", "target_location", "final_location",
            "summary", "failure_scenario", "evidence", "references",
            "introduced_by_target_commit", "present_at_review_baseline",
            "later_commit_status", "recommended_owner_phase", "recommended_fix",
            "recommended_test", "confidence_notes",
        )
        if not required_keys(finding, required_finding, label, errors):
            continue
        finding_id = finding.get("id")
        match = FINDING_RE.fullmatch(finding_id) if isinstance(finding_id, str) else None
        if not match or match.group(1) != phase.get("phase_id"):
            errors.append(f"{label}: finding ID must be namespaced to the phase")
        elif finding_id in seen:
            errors.append(f"{label}: duplicate finding ID")
        else:
            seen.add(finding_id)
        if not isinstance(finding.get("verdict"), str) or finding.get("verdict") not in FINDING_VERDICTS:
            errors.append(f"{label}: invalid verdict")
        owner = finding.get("recommended_owner_phase")
        if not isinstance(owner, str) or not PHASE_RE.fullmatch(owner):
            errors.append(f"{label}: invalid recommended_owner_phase")
        valid.append(finding)
    return valid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository_root", nargs="?", default=".")
    args = parser.parse_args()
    repo = Path(args.repository_root).expanduser().resolve()
    review_root = repo / REVIEW_ROOT
    errors: list[str] = []
    warnings: list[str] = []

    if subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        errors.append(f"{repo}: not a Git repository")
    if not review_root.is_dir():
        print(f"ERROR: review directory does not exist: {review_root}")
        return 1
    for name in REQUIRED_FILES:
        if not (review_root / name).is_file():
            errors.append(f"missing required file: {review_root / name}")
    for name in REQUIRED_DIRS:
        if not (review_root / name).is_dir():
            errors.append(f"missing required directory: {review_root / name}")
    for name, headings in (
        ("README.md", README_HEADINGS), ("review-ledger.md", LEDGER_HEADINGS), ("commit-map.md", MAP_HEADINGS),
    ):
        if (review_root / name).is_file():
            validate_markdown(review_root / name, headings, errors)

    manifest_path = review_root / "review-manifest.json"
    manifest = read_json(manifest_path, errors)
    top_required = (
        "schema_version", "status", "repository_root", "parallel_root", "review_root",
        "authorization_record", "review_baseline_commit", "pre_phase_base_commit",
        "backup_ref", "rewrite_branch", "publication_status", "force_push_authorized",
        "history_strategy", "reviewer_profile", "review_execution", "phase_order", "phase_reviews",
        "finding_dispositions", "findings_summary", "validation_commands",
        "final_code_checkpoint", "metadata_commit", "updated_at",
    )
    required_keys(manifest, top_required, "manifest", errors)
    if manifest.get("schema_version") != 2:
        errors.append("manifest.schema_version must equal 2")
    status = manifest.get("status")
    if not isinstance(status, str) or status not in REVIEW_STATUSES:
        errors.append("manifest.status is invalid")
    active = status not in ("preparing", "blocked")
    validate_profile(manifest.get("reviewer_profile"), errors, active=active)
    profile = manifest.get("reviewer_profile") if isinstance(manifest.get("reviewer_profile"), dict) else {}

    expected_paths = {
        "parallel_root": PARALLEL_ROOT.as_posix(), "review_root": REVIEW_ROOT.as_posix()
    }
    for key, expected in expected_paths.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest.{key} must equal {expected!r}")
    recorded_root = manifest.get("repository_root")
    if isinstance(recorded_root, str):
        candidate = Path(recorded_root).expanduser()
        if not candidate.is_absolute():
            candidate = repo / candidate
        if candidate.resolve() != repo:
            errors.append("manifest.repository_root does not resolve to validated repository")
    else:
        errors.append("manifest.repository_root must be a path")

    baseline = manifest.get("review_baseline_commit")
    pre_base = manifest.get("pre_phase_base_commit")
    for label, value in (("review_baseline_commit", baseline), ("pre_phase_base_commit", pre_base)):
        if not commit_exists(repo, value):
            errors.append(f"manifest.{label} must identify an existing commit")
    backup_ref = manifest.get("backup_ref")
    if not isinstance(backup_ref, str) or not backup_ref.strip():
        errors.append("manifest.backup_ref must be non-empty")
    else:
        resolved = resolve_ref(repo, backup_ref)
        if status in ("rewriting", "validating", "completed") and resolved != baseline:
            errors.append("backup_ref must resolve to the original review baseline")

    publication = manifest.get("publication_status")
    if publication not in ("unpublished", "published", "protected", "unknown"):
        errors.append("manifest.publication_status is invalid")
    if not isinstance(manifest.get("force_push_authorized"), bool):
        errors.append("manifest.force_push_authorized must be boolean")
    if publication in ("published", "protected", "unknown") and manifest.get("history_strategy") != "linearized-review-branch":
        errors.append("published, protected, or unknown history requires linearized-review-branch")
    if publication in ("published", "protected") and manifest.get("force_push_authorized") is False:
        warnings.append("remote history remains intentionally unchanged")

    phase_order = manifest.get("phase_order")
    if not isinstance(phase_order, list) or not phase_order or any(not isinstance(x, str) or not PHASE_RE.fullmatch(x) for x in phase_order):
        errors.append("manifest.phase_order must be a non-empty array of phase IDs")
        phase_order = []
    if len(phase_order) != len(set(phase_order)):
        errors.append("manifest.phase_order contains duplicates")

    review_execution = manifest.get("review_execution")
    batch_by_id: dict[str, list[str]] = {}
    phase_to_batch: dict[str, str] = {}
    execution_mode: Any = None
    max_parallel_reviewers: Any = None
    if required_keys(
        review_execution,
        ("mode", "max_parallel_reviewers", "batches"),
        "manifest.review_execution",
        errors,
    ):
        assert isinstance(review_execution, dict)
        execution_mode = review_execution.get("mode")
        if execution_mode not in ("pending", "single-phase", "parallel", "bounded-parallel", "blocked"):
            errors.append("manifest.review_execution.mode is invalid")
        max_parallel_reviewers = review_execution.get("max_parallel_reviewers")
        if not isinstance(max_parallel_reviewers, int) or max_parallel_reviewers < 0:
            errors.append("manifest.review_execution.max_parallel_reviewers must be a non-negative integer")
        batches = review_execution.get("batches")
        if not isinstance(batches, list):
            errors.append("manifest.review_execution.batches must be an array")
            batches = []
        for index, batch in enumerate(batches):
            label = f"manifest.review_execution.batches[{index}]"
            if not required_keys(batch, ("batch_id", "phase_ids"), label, errors):
                continue
            assert isinstance(batch, dict)
            batch_id = batch.get("batch_id")
            phase_ids = batch.get("phase_ids")
            if not isinstance(batch_id, str) or not BATCH_RE.fullmatch(batch_id):
                errors.append(f"{label}.batch_id must match RB-###")
                continue
            if batch_id in batch_by_id:
                errors.append(f"duplicate review batch: {batch_id}")
                continue
            if not isinstance(phase_ids, list) or not phase_ids:
                errors.append(f"{label}.phase_ids must be a non-empty array")
                continue
            valid_phases: list[str] = []
            for phase_id in phase_ids:
                if not isinstance(phase_id, str) or not PHASE_RE.fullmatch(phase_id):
                    errors.append(f"{label}.phase_ids contains an invalid phase ID")
                    continue
                valid_phases.append(phase_id)
                if phase_id in phase_to_batch:
                    errors.append(f"phase {phase_id} appears in multiple review batches")
                else:
                    phase_to_batch[phase_id] = batch_id
            if len(valid_phases) != len(set(valid_phases)):
                errors.append(f"{label}.phase_ids contains duplicates")
            batch_by_id[batch_id] = valid_phases
            if isinstance(max_parallel_reviewers, int) and max_parallel_reviewers >= 0 and len(valid_phases) > max_parallel_reviewers:
                errors.append(f"{label} exceeds max_parallel_reviewers")

    if status not in ("preparing", "blocked") and set(phase_to_batch) != set(phase_order):
        errors.append(
            "review batches must cover phase_order exactly; "
            f"missing={sorted(set(phase_order)-set(phase_to_batch))}, "
            f"extra={sorted(set(phase_to_batch)-set(phase_order))}"
        )

    execution = git_show_json(
        repo, baseline, (PARALLEL_ROOT / "execution-manifest.json").as_posix()
    )
    if execution is None:
        errors.append(
            "review_baseline_commit must contain a valid immutable execution-manifest.json"
        )
        execution = {}
    elif execution.get("schema_version") != 2:
        errors.append("review baseline execution manifest schema_version must equal 2")
    execution_scope = execution.get("approved_scope")
    delivery_scope_mode: Any = None
    requested_outcome: Any = None
    impact_cone: Any = None
    preserved_behavior: Any = None
    non_goals: Any = None
    scope_error_count = len(errors)
    if required_keys(
        execution_scope,
        (
            "delivery_scope_mode", "requested_outcome", "impact_cone",
            "preserved_behavior", "non_goals",
        ),
        "execution.approved_scope",
        errors,
    ):
        assert isinstance(execution_scope, dict)
        delivery_scope_mode = execution_scope.get("delivery_scope_mode")
        requested_outcome = execution_scope.get("requested_outcome")
        impact_cone = execution_scope.get("impact_cone")
        preserved_behavior = execution_scope.get("preserved_behavior")
        non_goals = execution_scope.get("non_goals")
        if not isinstance(delivery_scope_mode, str) or delivery_scope_mode not in DELIVERY_SCOPE_MODES:
            errors.append("execution.approved_scope.delivery_scope_mode is invalid")
        for key, value in (("requested_outcome", requested_outcome), ("impact_cone", impact_cone)):
            if not isinstance(value, str) or not value.strip():
                errors.append(f"execution.approved_scope.{key} must be a non-empty string")
        for key, value in (("preserved_behavior", preserved_behavior), ("non_goals", non_goals)):
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not item.strip() for item in value
            ):
                errors.append(f"execution.approved_scope.{key} must be an array of non-empty strings")
            elif len(value) != len(set(value)):
                errors.append(f"execution.approved_scope.{key} must not contain duplicates")
        if non_goals == []:
            errors.append("execution.approved_scope.non_goals must not be empty")
    scope_prompt_values_valid = len(errors) == scope_error_count
    units = execution.get("units") if isinstance(execution.get("units"), list) else []
    unit_by_id = {u.get("id"): u for u in units if isinstance(u, dict) and isinstance(u.get("id"), str)}
    execution_contracts = execution.get("contracts") if isinstance(execution.get("contracts"), list) else []
    contract_by_id = {
        contract.get("id"): contract
        for contract in execution_contracts
        if isinstance(contract, dict) and isinstance(contract.get("id"), str)
    }
    execution_order = execution.get("integration_order") if isinstance(execution.get("integration_order"), list) else []
    expected_phase_order = [phase for phase in execution_order if phase in phase_order]
    if phase_order and expected_phase_order != phase_order:
        errors.append("manifest.phase_order must follow execution-manifest integration_order")

    reviews = manifest.get("phase_reviews")
    if not isinstance(reviews, list):
        errors.append("manifest.phase_reviews must be an array")
        reviews = []
    review_by_phase: dict[str, dict[str, Any]] = {}
    all_findings: dict[str, dict[str, Any]] = {}
    reviewer_instances: set[str] = set()
    intervals_by_batch: dict[str, list[tuple[str, datetime, datetime]]] = {}
    for index, review in enumerate(reviews):
        label = f"manifest.phase_reviews[{index}]"
        required_phase = (
            "phase_id", "component_id", "original_commit", "original_parent",
            "current_commit", "review_baseline_commit", "plan_path", "plan_section",
            "boundary_path", "boundary_section", "contract_ids",
            "external_fidelity_required", "prompt_path", "prompt_sha256",
            "findings_path", "reviewer_instance_id", "review_batch_id",
            "started_at", "completed_at", "status", "limitations",
        )
        if not required_keys(review, required_phase, label, errors):
            continue
        phase_id = review.get("phase_id")
        if not isinstance(phase_id, str) or not PHASE_RE.fullmatch(phase_id):
            errors.append(f"{label}.phase_id is invalid")
            continue
        if phase_id in review_by_phase:
            errors.append(f"duplicate phase review: {phase_id}")
            continue
        review_by_phase[phase_id] = review
        contract_ids = review.get("contract_ids")
        if not isinstance(contract_ids, list) or any(
            not isinstance(value, str) or not re.fullmatch(r"CTR-\d{3,}", value)
            for value in contract_ids
        ):
            errors.append(f"{label}.contract_ids must be an array of CTR-### IDs")
            contract_ids = []
        elif len(contract_ids) != len(set(contract_ids)):
            errors.append(f"{label}.contract_ids contains duplicates")
        external_fidelity_required = review.get("external_fidelity_required")
        if not isinstance(external_fidelity_required, bool):
            errors.append(f"{label}.external_fidelity_required must be boolean")
        prompt_sha256 = review.get("prompt_sha256")
        if not isinstance(prompt_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", prompt_sha256
        ):
            errors.append(f"{label}.prompt_sha256 must be 64 lower-case hex characters")
        if not isinstance(review.get("status"), str) or review.get("status") not in PHASE_STATUSES:
            errors.append(f"{label}.status is invalid")
        reviewer_instance = review.get("reviewer_instance_id")
        if not isinstance(reviewer_instance, str) or not reviewer_instance.strip():
            errors.append(f"{label}.reviewer_instance_id must be non-empty")
        elif reviewer_instance in reviewer_instances:
            errors.append(f"{label}.reviewer_instance_id must be unique")
        else:
            reviewer_instances.add(reviewer_instance)
        review_batch_id = review.get("review_batch_id")
        if not isinstance(review_batch_id, str) or not BATCH_RE.fullmatch(review_batch_id):
            errors.append(f"{label}.review_batch_id must match RB-###")
        elif review_batch_id not in batch_by_id:
            errors.append(f"{label}.review_batch_id is not declared in review_execution")
        elif phase_id not in batch_by_id[review_batch_id]:
            errors.append(f"{label}.phase_id is not a member of its review batch")
        elif phase_to_batch.get(phase_id) != review_batch_id:
            errors.append(f"{label}.review_batch_id disagrees with review_execution")
        started_value = review.get("started_at")
        completed_value = review.get("completed_at")
        started = completed = None
        if status == "completed" or started_value is not None:
            started = parse_datetime(started_value, f"{label}.started_at", errors)
        if status == "completed" or completed_value is not None:
            completed = parse_datetime(completed_value, f"{label}.completed_at", errors)
        if started is not None and completed is not None:
            if started >= completed:
                errors.append(f"{label}: started_at must be earlier than completed_at")
            elif isinstance(review_batch_id, str):
                intervals_by_batch.setdefault(review_batch_id, []).append((phase_id, started, completed))
        unit = unit_by_id.get(phase_id)
        if not unit:
            errors.append(f"{label}: phase does not exist in execution manifest")
        else:
            for review_key, unit_key in (("component_id", "component_id"), ("original_commit", "integration_commit"), ("plan_path", "plan_path"), ("boundary_path", "boundary_path")):
                if review.get(review_key) != unit.get(unit_key):
                    errors.append(f"{label}.{review_key} does not match execution unit")
        original = review.get("original_commit")
        parent = review.get("original_parent")
        if not commit_exists(repo, original) or not commit_exists(repo, parent):
            errors.append(f"{label}: original commit and parent must exist")
        elif parent_of(repo, original) != parent:
            errors.append(f"{label}.original_parent is not target first parent")
        if isinstance(baseline, str) and isinstance(original, str) and commit_exists(repo, original) and commit_exists(repo, baseline) and not is_ancestor(repo, original, baseline):
            errors.append(f"{label}: original commit is not reachable from review baseline")
        if review.get("review_baseline_commit") != baseline:
            errors.append(f"{label}.review_baseline_commit does not match manifest")
        current = review.get("current_commit")
        if status == "completed":
            if not commit_exists(repo, current):
                errors.append(f"{label}.current_commit must exist at completion")
            elif phase_id not in commit_message(repo, current):
                errors.append(f"{label}.current_commit message must contain phase ID")
        elif current != "pending" and not commit_exists(repo, current):
            errors.append(f"{label}.current_commit must be pending or an existing commit")
        prompt_path = repo_path(repo, review.get("prompt_path"), f"{label}.prompt_path", errors)
        if prompt_path is not None:
            if not prompt_path.is_file():
                errors.append(f"{label}.prompt_path does not exist")
            else:
                prompt_bytes = prompt_path.read_bytes()
                text = prompt_bytes.decode("utf-8", errors="replace")
                actual_prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
                if isinstance(prompt_sha256, str) and actual_prompt_sha256 != prompt_sha256:
                    errors.append(
                        f"{label}.prompt_sha256 does not match the exact prompt bytes"
                    )
                prompt_expectations = (
                    phase_id,
                    str(review.get("component_id")),
                    str(original),
                    str(parent),
                    str(baseline),
                    "gpt-5.6-sol",
                    "xhigh",
                    "phase-commit-reviewer",
                    str(review.get("plan_path")),
                    str(review.get("boundary_path")),
                )
                for expected in prompt_expectations:
                    if expected not in text:
                        errors.append(f"{label}.prompt_path missing {expected!r}")
                if isinstance(external_fidelity_required, bool):
                    expected_flag = (
                        "**External fidelity required:** `"
                        f"{'true' if external_fidelity_required else 'false'}`"
                    )
                    if expected_flag not in text:
                        errors.append(
                            f"{label}.prompt_path missing {expected_flag!r}"
                        )
                actual_scope = parse_prompt_scope(text, f"{label}.prompt_path", errors)
                if scope_prompt_values_valid:
                    expected_scope = {
                        "delivery_scope_mode": delivery_scope_mode,
                        "requested_outcome": requested_outcome,
                        "impact_cone": impact_cone,
                        "preserved_behavior": preserved_behavior,
                        "non_goals": non_goals,
                    }
                    if actual_scope is not None and actual_scope != expected_scope:
                        errors.append(
                            f"{label}.prompt_path approved-scope block does not match "
                            "the review-baseline execution manifest"
                        )
                for contract_id in contract_ids:
                    if contract_id not in text:
                        errors.append(f"{label}.prompt_path missing contract ID {contract_id}")
                    contract = contract_by_id.get(contract_id)
                    canonical_path = contract.get("canonical_path") if isinstance(contract, dict) else None
                    if isinstance(canonical_path, str) and canonical_path not in text:
                        errors.append(
                            f"{label}.prompt_path missing canonical contract path {canonical_path!r}"
                        )
        findings_path = repo_path(repo, review.get("findings_path"), f"{label}.findings_path", errors)
        if review.get("status") not in ("planned", "running", "model-blocked", "scope-blocked", "failed", "blocked") or status in ("findings-received", "verifying-findings", "rewriting", "validating", "completed"):
            if findings_path is None or not findings_path.is_file():
                errors.append(f"{label}.findings_path does not exist")
            else:
                for finding in validate_findings(findings_path, review, profile, str(baseline), errors):
                    finding_id = finding.get("id")
                    if finding_id in all_findings:
                        errors.append(f"duplicate finding across reports: {finding_id}")
                    else:
                        all_findings[finding_id] = finding

    if set(review_by_phase) != set(phase_order):
        errors.append(f"phase_reviews must cover phase_order exactly; missing={sorted(set(phase_order)-set(review_by_phase))}, extra={sorted(set(review_by_phase)-set(phase_order))}")

    if status == "completed":
        if len(reviewer_instances) != len(phase_order):
            errors.append("completed review requires one distinct reviewer instance per phase")
        if len(phase_order) == 1:
            if execution_mode != "single-phase":
                errors.append("a one-phase completed review must use review_execution.mode 'single-phase'")
            if max_parallel_reviewers != 1:
                errors.append("a one-phase completed review must record max_parallel_reviewers = 1")
        elif len(phase_order) > 1:
            if execution_mode not in ("parallel", "bounded-parallel"):
                errors.append("multi-phase completed review must use parallel or bounded-parallel mode")
            if not isinstance(max_parallel_reviewers, int) or max_parallel_reviewers < 2:
                errors.append("multi-phase completed review requires max_parallel_reviewers >= 2")
            if execution_mode == "parallel" and len(batch_by_id) != 1:
                errors.append("parallel mode requires one batch containing every phase")
            if not any(len(phases) > 1 for phases in batch_by_id.values()):
                errors.append("multi-phase completed review has no batch with concurrent reviewers")
            overlap_observed = False
            for batch_id, phases in batch_by_id.items():
                intervals = intervals_by_batch.get(batch_id, [])
                if len(phases) > 1:
                    if len(intervals) != len(phases):
                        errors.append(f"review batch {batch_id} lacks complete timing evidence")
                        continue
                    batch_overlap = any(
                        first[1] < second[2] and second[1] < first[2]
                        for index, first in enumerate(intervals)
                        for second in intervals[index + 1:]
                    )
                    if not batch_overlap:
                        errors.append(f"review batch {batch_id} has no overlapping reviewer execution")
                    overlap_observed = overlap_observed or batch_overlap
            if not overlap_observed:
                errors.append("multi-phase completed review lacks evidence of actual parallel execution")
        if execution_mode in ("pending", "blocked"):
            errors.append("completed review cannot use pending or blocked execution mode")

    dispositions = manifest.get("finding_dispositions")
    if not isinstance(dispositions, list):
        errors.append("manifest.finding_dispositions must be an array")
        dispositions = []
    disposition_by_finding: dict[str, dict[str, Any]] = {}
    for index, disposition in enumerate(dispositions):
        label = f"manifest.finding_dispositions[{index}]"
        required_disposition = (
            "finding_id", "reported_phase", "disposition", "assigned_phase", "status",
            "rationale", "fix_summary", "test_summary", "evidence",
        )
        if not required_keys(disposition, required_disposition, label, errors):
            continue
        fid = disposition.get("finding_id")
        if fid in disposition_by_finding:
            errors.append(f"duplicate disposition: {fid}")
        else:
            disposition_by_finding[fid] = disposition
        if fid not in all_findings:
            errors.append(f"{label}: finding_id is not present in reviewer reports")
        if not isinstance(disposition.get("disposition"), str) or disposition.get("disposition") not in DISPOSITIONS:
            errors.append(f"{label}.disposition is invalid")
        if not isinstance(disposition.get("status"), str) or disposition.get("status") not in DISPOSITION_STATUSES:
            errors.append(f"{label}.status is invalid")
        assigned = disposition.get("assigned_phase")
        if assigned is not None and assigned not in phase_order:
            errors.append(f"{label}.assigned_phase is not in phase_order")
        if not isinstance(disposition.get("rationale"), str) or not disposition.get("rationale", "").strip():
            errors.append(f"{label}.rationale must be non-empty")
    if status == "completed" and set(disposition_by_finding) != set(all_findings):
        errors.append("completed review requires exactly one disposition per reported finding")

    summary = manifest.get("findings_summary")
    if not isinstance(summary, dict) or any(key not in summary for key in COUNT_KEYS):
        errors.append("manifest.findings_summary must contain all count fields")
        summary = {}
    else:
        for key in COUNT_KEYS:
            if not isinstance(summary.get(key), int) or summary.get(key) < 0:
                errors.append(f"manifest.findings_summary.{key} must be a non-negative integer")
        if summary.get("reported") != len(all_findings):
            errors.append("manifest.findings_summary.reported does not match reports")
        if summary.get("confirmed") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("disposition") == "confirmed"):
            errors.append("manifest.findings_summary.confirmed does not match dispositions")
        if summary.get("rejected") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("disposition") == "rejected"):
            errors.append("manifest.findings_summary.rejected does not match dispositions")
        if summary.get("duplicate") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("disposition") == "duplicate"):
            errors.append("manifest.findings_summary.duplicate does not match dispositions")
        if summary.get("already_fixed") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("disposition") == "already-fixed"):
            errors.append("manifest.findings_summary.already_fixed does not match dispositions")
        if summary.get("reassigned") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("disposition") == "reassigned"):
            errors.append("manifest.findings_summary.reassigned does not match dispositions")
        if summary.get("fixed") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("status") == "fixed"):
            errors.append("manifest.findings_summary.fixed does not match dispositions")
        if summary.get("blocked") != sum(1 for d in dispositions if isinstance(d, dict) and d.get("status") == "blocked"):
            errors.append("manifest.findings_summary.blocked does not match dispositions")

    validations = manifest.get("validation_commands")
    if not isinstance(validations, list):
        errors.append("manifest.validation_commands must be an array")
        validations = []
    if status == "completed":
        if not validations:
            errors.append("completed review requires validation commands")
        for index, result in enumerate(validations):
            if not isinstance(result, dict) or result.get("status") != "passed":
                errors.append(f"manifest.validation_commands[{index}] must be passed at completion")

    final_checkpoint = manifest.get("final_code_checkpoint")
    metadata_commit = manifest.get("metadata_commit")
    if status == "completed":
        if not commit_exists(repo, final_checkpoint):
            errors.append("completed review requires an existing final_code_checkpoint")
        resolved_metadata_commit: str | None = None
        if metadata_commit == "self":
            resolved_metadata_commit = last_commit_for_path(
                repo, (REVIEW_ROOT / "review-manifest.json").as_posix()
            )
            if resolved_metadata_commit is None:
                errors.append(
                    "completed review metadata_commit='self' requires a committed review manifest"
                )
            else:
                committed_manifest = git_show_json(
                    repo,
                    resolved_metadata_commit,
                    (REVIEW_ROOT / "review-manifest.json").as_posix(),
                )
                if committed_manifest != manifest:
                    errors.append(
                        "metadata_commit='self' requires the current review manifest to "
                        "match its latest committed version"
                    )
        elif commit_exists(repo, metadata_commit):
            assert isinstance(metadata_commit, str)
            resolved_metadata_commit = metadata_commit
        else:
            errors.append(
                "completed review requires metadata_commit='self' or an existing metadata commit"
            )
        if (
            isinstance(final_checkpoint, str)
            and resolved_metadata_commit is not None
            and not is_ancestor(repo, final_checkpoint, resolved_metadata_commit)
        ):
            errors.append("metadata_commit must descend from final_code_checkpoint")
        current_chain = [review_by_phase[p].get("current_commit") for p in phase_order if p in review_by_phase]
        for earlier, later in zip(current_chain, current_chain[1:]):
            if isinstance(earlier, str) and isinstance(later, str) and commit_exists(repo, earlier) and commit_exists(repo, later) and not is_ancestor(repo, earlier, later):
                errors.append("current phase commits must preserve phase order by ancestry")
        if current_chain and isinstance(final_checkpoint, str) and commit_exists(repo, final_checkpoint):
            last = current_chain[-1]
            if isinstance(last, str) and commit_exists(repo, last) and not is_ancestor(repo, last, final_checkpoint):
                errors.append("final_code_checkpoint must contain the last phase commit")
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True, check=False)
        if dirty.returncode == 0 and dirty.stdout.strip():
            warnings.append("validated checkout is not clean; this may be acceptable when review metadata is not committed yet")

    if not isinstance(manifest.get("updated_at"), str) or not manifest.get("updated_at", "").strip():
        errors.append("manifest.updated_at must be non-empty")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"Validated parallel review with {len(errors)} error(s) and {len(warnings)} warning(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
