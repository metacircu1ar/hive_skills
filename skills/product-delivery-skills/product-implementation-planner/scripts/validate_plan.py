#!/usr/bin/env python3
"""Validate the scope-relative structural completeness of a selected planning root.

The validator checks document structure, stable IDs, phase metadata, and implementation
handoff coverage. It cannot prove architectural correctness or safe parallelism; the agent
must still perform the semantic review defined in SKILL.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

PLAN_RELATIVE_PATH = Path("docs") / "implementation-plan"

CORE_REQUIRED_FILES = (
    "00-product-description.md",
    "README.md",
    "delivery-status.md",
    "92-delivery-roadmap.md",
    "93-implementation-units.md",
    "99-open-questions.md",
)

FULL_PRODUCT_FILES = (
    "01-system-architecture.md",
    "02-domain-and-data.md",
    "03-interfaces-and-integrations.md",
    "90-security-reliability-and-operations.md",
    "91-testing-and-quality.md",
)

DELIVERY_SCOPE_MODES = {
    "full product",
    "scoped change",
    "modernization or migration",
    "remediation or reliability",
}

GLOBAL_METADATA_MARKERS = (
    "status",
    "last updated",
    "source requirement",
    "related document",
)

README_HEADINGS = (
    "planning status and phase-readiness statement",
    "source documents and repository evidence",
    "product summary",
    "delivery scope and impact cone",
    "goals and non-goals",
    "architecture summary",
    "major components and ownership table",
    "system-wide delivery-phase summary",
    "component and phase identifier registry",
    "document index",
    "requirement-to-component-to-phase traceability summary",
    "blocking decisions, deferred gates, and highest risks",
    "implementation handoff readiness",
    "how to use and maintain the plan",
)

DELIVERY_STATUS_HEADINGS = (
    "scope at a glance",
    "stage status",
    "what changed",
    "decisions and operator actions",
    "verification, implementation, and review summary",
    "risks and blockers",
    "evidence links",
)

DELIVERY_STATUS_METADATA_FIELDS = (
    "Summary type",
    "Authority",
    "Current stage",
    "Current status",
    "Last updated",
    "Operator action required",
    "Related documents",
)

DELIVERY_STATUS_STAGES = (
    "Planning",
    "Formal verification",
    "Implementation",
    "Review",
)

DELIVERY_STATUS_CURRENT_STAGES = {
    "planning",
    "formal verification",
    "implementation",
    "review",
    "delivery complete",
}

DELIVERY_STATUS_STAGE_STATUSES = {
    "not started",
    "not requested",
    "in progress",
    "blocked",
    "completed",
    "completed with limitations",
    "declined",
    "skipped",
}

PLANNING_STATUS_TO_STAGE_STATUS = {
    "draft": "in progress",
    "blocked": "blocked",
    "ready for implementation": "completed",
}

PRODUCT_DESCRIPTION_HEADINGS = (
    "document purpose and source",
    "product vision and problem",
    "outcomes and success measures",
    "users, actors, and roles",
    "product surfaces and operating model",
    "delivery scope and release boundary",
    "primary and exceptional workflows",
    "functional requirements",
    "non-functional requirements",
    "business rules and invariants",
    "constraints and dependencies",
    "principal decision register",
    "assumptions and deferred decisions",
    "explicit non-goals",
    "acceptance model",
    "change history",
)

ROADMAP_HEADINGS = (
    "delivery principles",
    "system-wide phases",
    "component and phase identifier registry",
    "cross-component dependency matrix",
    "component-phase dependency dag",
    "dependency-type legend and rationale",
    "decision-gate schedule",
    "critical path",
    "candidate parallel waves",
    "hard sequential constraints",
    "milestones and objective exit gates",
    "environment and infrastructure sequencing",
    "data and integration migration sequencing",
    "release, rollout, rollback, and launch plan",
    "post-launch stabilization and ownership transfer",
    "decommissioning and cleanup",
    "risks, contingency paths, and decision deadlines",
)

IMPLEMENTATION_UNITS_HEADINGS = (
    "handoff status and authorized phases",
    "stable component and phase catalog",
    "decomposition decision and change-scenario analysis",
    "candidate execution units",
    "dependency edges",
    "provider-consumer boundary candidates",
    "expected write-domain ownership",
    "shared artifacts and conflict hotspots",
    "contract artifacts likely to be materialized",
    "parallelization candidates",
    "mandatory serialization constraints",
    "decision gates and excluded units",
    "suggested integration order",
    "handoff validation checklist",
)

COMPONENT_HEADINGS = (
    "purpose and scope",
    "responsibilities",
    "explicit non-responsibilities",
    "architecture and internal modules",
    "dependencies and public contracts",
    "data and state ownership",
    "security and privacy",
    "reliability and failure modes",
    "observability and operational controls",
    "test strategy",
    "rollout, migration, rollback, and decommissioning",
    "phased implementation",
    "risks and open decisions",
)

PHASE_SUBHEADINGS = (
    "objective",
    "prerequisites",
    "in scope",
    "out of scope",
    "work",
    "deliverables",
    "dependencies",
    "boundary inputs",
    "boundary outputs",
    "expected write domains",
    "preliminary parallelization",
    "validation",
    "operational and migration work",
    "exit criteria",
    "risks and deferred work",
)

DEPENDENCY_CLASSIFICATIONS = (
    "independent",
    "contract-bound",
    "implementation-bound",
    "decision-gated",
)

VAGUE_PATTERNS = (
    re.compile(r"\buse best practices\b", re.IGNORECASE),
    re.compile(r"\badd security\b", re.IGNORECASE),
    re.compile(r"\bhandle errors\b", re.IGNORECASE),
    re.compile(r"\bscale later\b", re.IGNORECASE),
)

UNRESOLVED_PATTERNS = (
    re.compile(r"\bTBD\b", re.IGNORECASE),
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"\bto be decided\b", re.IGNORECASE),
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
COMPONENT_ID_RE = re.compile(r"\bComponent\s+ID\s*:\s*`?(CMP-(\d{3,}))`?\b", re.IGNORECASE)
PHASE_RE = re.compile(
    r"^###\s+(PH-(\d{3,})-(\d{2,}))\s+(?:—|-)\s+[^\n]+$",
    re.IGNORECASE | re.MULTILINE,
)
EXPECTED_WRITE_PATH_RE = re.compile(
    r"^ {0,3}[-*+]\s+`([^`\n]+)`(?:\s+.*)?$"
)
FENCE_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
REQUIREMENT_ID_RE = re.compile(r"\b(?:FR|NFR|CON)-\d{3,}\b")
DEFERRED_DECISION_RE = re.compile(r"\bDEC-\d{3,}\b")
SCOPE_BEGIN = "<!-- delivery-scope:begin -->"
SCOPE_END = "<!-- delivery-scope:end -->"
SCOPE_REQUIRED_KEYS = {
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
DECOMPOSITION_BEGIN = "<!-- decomposition-assessment:begin -->"
DECOMPOSITION_END = "<!-- decomposition-assessment:end -->"
DECOMPOSITION_REQUIRED_KEYS = {
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
DECOMPOSITION_AXES = {
    "domain_partitioning",
    "dependency_topology",
    "state_and_consistency",
    "code_organization",
    "deployment_topology",
    "internal_programming_model",
}
DECOMPOSITION_CONTEXTS = {"existing", "greenfield"}
DECOMPOSITION_DECISIONS = {"reuse", "local-extension", "boundary-change", "greenfield"}
SUBSYSTEM_CLASSIFICATIONS = {
    "coherent-compatible": "existing-subsystem",
    "defective-but-compatible": "existing-subsystem",
    "incompatible-with-change": "scoped-migration",
    "no-discernible-local-architecture": "local-to-change",
}
SUBSYSTEM_KEYS = {
    "name",
    "classification",
    "architecture_scope",
    "evidence",
    "response",
    "coexistence",
    "migration",
    "rollback",
}
DATA_OWNERSHIP_KEYS = {
    "resource",
    "owner_component_id",
    "authorized_writer_component_ids",
    "write_paths",
    "coordination",
}
SCENARIO_KEYS = {"id", "description"}
CANDIDATE_KEYS = {"name", "selected", "differs_on_axes", "scenario_impacts"}
SCENARIO_IMPACT_KEYS = {
    "scenario_id",
    "components_crossed",
    "contracts_crossed",
    "acceptable",
    "rationale",
}


@dataclass(frozen=True)
class ComponentRecord:
    path: Path
    component_id: str
    phase_ids: tuple[str, ...]
    phase_write_paths: tuple[tuple[str, tuple[str, ...]], ...]


def normalize_heading(value: str) -> str:
    value = re.sub(r"[`*_]", "", value)
    value = re.sub(r"\s+", " ", value.strip().lower())
    return value


def heading_entries(text: str) -> list[tuple[int, str, int]]:
    return [
        (len(match.group(1)), normalize_heading(match.group(2)), match.start())
        for match in HEADING_RE.finditer(text)
    ]


def missing_heading_names(text: str, required: Iterable[str]) -> list[str]:
    available = {name for _, name, _ in heading_entries(text)}
    return [name for name in required if normalize_heading(name) not in available]


def heading_body(text: str, heading: str, level: int) -> str | None:
    """Return one Markdown heading body through the next peer or parent heading."""

    expected = normalize_heading(heading)
    entries = heading_entries(text)
    for index, (entry_level, name, start) in enumerate(entries):
        if entry_level != level or name != expected:
            continue
        line_end = text.find("\n", start)
        body_start = len(text) if line_end < 0 else line_end + 1
        body_end = len(text)
        for next_level, _, next_start in entries[index + 1 :]:
            if next_level <= level:
                body_end = next_start
                break
        return text[body_start:body_end]
    return None


def unique_level_heading_body(
    text: str,
    heading: str,
    level: int,
    path: Path,
    errors: list[str] | None,
) -> str | None:
    """Return a heading body only when its name occurs once at the required level."""

    expected = normalize_heading(heading)
    matches = [entry for entry in heading_entries(text) if entry[1] == expected]
    if len(matches) != 1 or matches[0][0] != level:
        if errors is not None:
            exact_count = sum(entry_level == level for entry_level, _, _ in matches)
            errors.append(
                f"{path}: must contain exactly one level-{level} {heading!r} heading; "
                f"found {len(matches)} total and {exact_count} at the required level"
            )
        return None
    return heading_body(text, heading, level)


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append(f"{path}: file is not valid UTF-8")
    except OSError as exc:
        errors.append(f"{path}: cannot read file: {exc}")
    return ""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key {key!r}")
        result[key] = value
    return result


def nonempty_string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{label}: expected an array of non-empty strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label}: duplicate values are not allowed")
    return value


def exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{label}: expected an object")
        return False
    keys = set(value)
    if keys != expected:
        errors.append(
            f"{label}: keys differ; missing={sorted(expected - keys)}, "
            f"extra={sorted(keys - expected)}"
        )
        return False
    return True


def nonempty_string(value: Any, label: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty string")
        return False
    return True


def normalize_repository_pattern(pattern: str) -> str:
    """Return a conservative canonical prefix for path-overlap checks."""

    value = pattern.replace("\\", "/").strip()
    parts = value.split("/")
    if ".." in parts:
        return ""
    value = "/".join(part for part in parts if part not in ("", "."))
    wildcard_positions = [
        position for character in "*?[" if (position := value.find(character)) >= 0
    ]
    if wildcard_positions:
        cut = min(wildcard_positions)
        if cut > 0 and value[cut - 1] != "/":
            cut = value.rfind("/", 0, cut) + 1
        value = value[:cut]
    return value.rstrip("/")


def patterns_may_overlap(first: str, second: str) -> bool:
    first_prefix = normalize_repository_pattern(first).casefold()
    second_prefix = normalize_repository_pattern(second).casefold()
    if not first_prefix or not second_prefix:
        return True
    if first_prefix == second_prefix:
        return True
    return first_prefix.startswith(second_prefix + "/") or second_prefix.startswith(
        first_prefix + "/"
    )


def markdown_lines_outside_fences(markdown: str) -> list[str]:
    """Return Markdown lines that are not inside fenced code blocks."""

    lines: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in markdown.splitlines():
        if fence_character is not None:
            closing_fence = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                line,
            )
            if closing_fence:
                fence_character = None
                fence_length = 0
            continue
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group("fence")
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        lines.append(line)
    return lines


def expected_write_paths(markdown: str) -> list[str]:
    """Extract real Markdown bullets while ignoring fenced and indented code."""

    paths: list[str] = []
    for line in markdown_lines_outside_fences(markdown):
        match = EXPECTED_WRITE_PATH_RE.match(line)
        if match:
            paths.append(match.group(1))
    return paths


def validate_repository_pattern(pattern: str, label: str, errors: list[str]) -> None:
    normalized = pattern.replace("\\", "/").strip()
    if not normalized:
        errors.append(f"{label}: path pattern must not be empty")
    elif normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        errors.append(f"{label}: path pattern must be repository-relative: {pattern!r}")
    elif ".." in normalized.split("/"):
        errors.append(f"{label}: path pattern escapes the repository: {pattern!r}")


def parse_decomposition_assessment(
    path: Path, text: str, errors: list[str]
) -> dict[str, Any] | None:
    starts = text.count(DECOMPOSITION_BEGIN)
    ends = text.count(DECOMPOSITION_END)
    if starts == 0 and ends == 0:
        errors.append(f"{path}: missing canonical decomposition-assessment block")
        return None
    if starts != 1 or ends != 1:
        errors.append(f"{path}: expected exactly one canonical decomposition-assessment block")
        return None
    start = text.find(DECOMPOSITION_BEGIN) + len(DECOMPOSITION_BEGIN)
    end = text.find(DECOMPOSITION_END, start)
    if end < start:
        errors.append(f"{path}: decomposition-assessment markers are out of order")
        return None
    try:
        parsed = json.loads(
            text[start:end].strip(), object_pairs_hook=reject_duplicate_keys
        )
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{path}: invalid decomposition-assessment JSON: {exc}")
        return None
    label = f"{path}: decomposition-assessment"
    if not exact_keys(parsed, DECOMPOSITION_REQUIRED_KEYS, label, errors):
        return None

    if parsed.get("schema_version") != 1:
        errors.append(f"{label}.schema_version must equal 1")
    context = parsed.get("context")
    if not isinstance(context, str) or context not in DECOMPOSITION_CONTEXTS:
        errors.append(f"{label}.context must be one of {sorted(DECOMPOSITION_CONTEXTS)}")
    decision = parsed.get("decision_kind")
    if not isinstance(decision, str) or decision not in DECOMPOSITION_DECISIONS:
        errors.append(
            f"{label}.decision_kind must be one of {sorted(DECOMPOSITION_DECISIONS)}"
        )
    if context == "greenfield" and decision != "greenfield":
        errors.append(f"{label}: greenfield context requires decision_kind 'greenfield'")
    if context == "existing" and decision == "greenfield":
        errors.append(f"{label}: existing context cannot use decision_kind 'greenfield'")

    axes = parsed.get("axes")
    if exact_keys(axes, DECOMPOSITION_AXES, f"{label}.axes", errors):
        for key, value in axes.items():
            nonempty_string(value, f"{label}.axes.{key}", errors)
    nonempty_string_list(
        parsed.get("language_constraints"), f"{label}.language_constraints", errors
    )

    subsystems = parsed.get("affected_subsystems")
    if not isinstance(subsystems, list):
        errors.append(f"{label}.affected_subsystems: expected an array")
        subsystems = []
    subsystem_names: list[str] = []
    for index, subsystem in enumerate(subsystems):
        item_label = f"{label}.affected_subsystems[{index}]"
        if not exact_keys(subsystem, SUBSYSTEM_KEYS, item_label, errors):
            continue
        name = subsystem.get("name")
        if nonempty_string(name, f"{item_label}.name", errors):
            subsystem_names.append(name)
        classification = subsystem.get("classification")
        expected_scope = (
            SUBSYSTEM_CLASSIFICATIONS.get(classification)
            if isinstance(classification, str)
            else None
        )
        if expected_scope is None:
            errors.append(
                f"{item_label}.classification must be one of "
                f"{sorted(SUBSYSTEM_CLASSIFICATIONS)}"
            )
        elif subsystem.get("architecture_scope") != expected_scope:
            errors.append(
                f"{item_label}.architecture_scope must equal {expected_scope!r} "
                f"for {classification!r}"
            )
        evidence = nonempty_string_list(
            subsystem.get("evidence"), f"{item_label}.evidence", errors
        )
        if not evidence:
            errors.append(f"{item_label}.evidence must not be empty")
        nonempty_string(subsystem.get("response"), f"{item_label}.response", errors)
        for key in ("coexistence", "migration", "rollback"):
            value = subsystem.get(key)
            if value is not None and not nonempty_string(value, f"{item_label}.{key}", errors):
                continue
            if classification == "incompatible-with-change" and value is None:
                errors.append(f"{item_label}.{key} must be non-empty for incompatible architecture")
    if len(subsystem_names) != len(set(subsystem_names)):
        errors.append(f"{label}.affected_subsystems names must be unique")
    if context == "existing" and not subsystems:
        errors.append(f"{label}.affected_subsystems must not be empty for existing context")
    if context == "greenfield" and subsystems:
        errors.append(f"{label}.affected_subsystems must be empty for greenfield context")

    ownership = parsed.get("data_ownership")
    if not isinstance(ownership, list):
        errors.append(f"{label}.data_ownership: expected an array")
        ownership = []
    resources: list[str] = []
    for index, record in enumerate(ownership):
        item_label = f"{label}.data_ownership[{index}]"
        if not exact_keys(record, DATA_OWNERSHIP_KEYS, item_label, errors):
            continue
        resource = record.get("resource")
        if nonempty_string(resource, f"{item_label}.resource", errors):
            resources.append(resource)
        owner = record.get("owner_component_id")
        if not isinstance(owner, str) or not re.fullmatch(r"CMP-\d{3,}", owner):
            errors.append(f"{item_label}.owner_component_id must match CMP-###")
        writers = nonempty_string_list(
            record.get("authorized_writer_component_ids"),
            f"{item_label}.authorized_writer_component_ids",
            errors,
        )
        if not writers:
            errors.append(f"{item_label}.authorized_writer_component_ids must not be empty")
        for writer in writers:
            if not re.fullmatch(r"CMP-\d{3,}", writer):
                errors.append(
                    f"{item_label}.authorized_writer_component_ids contains invalid ID {writer!r}"
                )
        if isinstance(owner, str) and owner not in writers:
            errors.append(f"{item_label}: owner_component_id must be an authorized writer")
        paths = nonempty_string_list(record.get("write_paths"), f"{item_label}.write_paths", errors)
        if not paths:
            errors.append(f"{item_label}.write_paths must not be empty")
        for path_index, pattern in enumerate(paths):
            validate_repository_pattern(
                pattern, f"{item_label}.write_paths[{path_index}]", errors
            )
        coordination = record.get("coordination")
        if coordination is not None:
            nonempty_string(coordination, f"{item_label}.coordination", errors)
        if len(writers) > 1 and coordination is None:
            errors.append(f"{item_label}.coordination is required for multiple writers")
    if len(resources) != len(set(resources)):
        errors.append(f"{label}.data_ownership resources must be unique")
    for left_index, left in enumerate(ownership):
        if not isinstance(left, dict):
            continue
        left_owner = left.get("owner_component_id")
        left_paths = left.get("write_paths")
        if not isinstance(left_owner, str) or not isinstance(left_paths, list):
            continue
        for right in ownership[left_index + 1 :]:
            if not isinstance(right, dict):
                continue
            right_owner = right.get("owner_component_id")
            right_paths = right.get("write_paths")
            if (
                not isinstance(right_owner, str)
                or not isinstance(right_paths, list)
                or left_owner == right_owner
                or any(not isinstance(path, str) for path in left_paths + right_paths)
            ):
                continue
            if any(
                patterns_may_overlap(left_path, right_path)
                for left_path in left_paths
                for right_path in right_paths
            ):
                errors.append(
                    f"{label}: resources {left.get('resource')!r} and "
                    f"{right.get('resource')!r} have overlapping write paths but "
                    "different owners"
                )

    scenarios = parsed.get("scenarios")
    if not isinstance(scenarios, list):
        errors.append(f"{label}.scenarios: expected an array")
        scenarios = []
    scenario_ids: list[str] = []
    for index, scenario in enumerate(scenarios):
        item_label = f"{label}.scenarios[{index}]"
        if not exact_keys(scenario, SCENARIO_KEYS, item_label, errors):
            continue
        scenario_id = scenario.get("id")
        if not isinstance(scenario_id, str) or not re.fullmatch(r"SCN-\d{3,}", scenario_id):
            errors.append(f"{item_label}.id must match SCN-###")
        else:
            scenario_ids.append(scenario_id)
        nonempty_string(scenario.get("description"), f"{item_label}.description", errors)
    if len(scenario_ids) != len(set(scenario_ids)):
        errors.append(f"{label}.scenario IDs must be unique")
    minimum_scenarios = 2 if decision == "reuse" else 4
    if (
        isinstance(decision, str)
        and decision in DECOMPOSITION_DECISIONS
        and not minimum_scenarios <= len(scenarios) <= 6
    ):
        errors.append(
            f"{label}.scenarios must contain {minimum_scenarios} to 6 entries "
            f"for decision_kind {decision!r}"
        )

    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        errors.append(f"{label}.candidates: expected an array")
        candidates = []
    minimum_candidates = 1 if decision == "reuse" else 2
    if (
        isinstance(decision, str)
        and decision in DECOMPOSITION_DECISIONS
        and len(candidates) < minimum_candidates
    ):
        errors.append(
            f"{label}.candidates must contain at least {minimum_candidates} entries "
            f"for decision_kind {decision!r}"
        )
    candidate_names: list[str] = []
    selected_count = 0
    scenario_set = set(scenario_ids)
    for index, candidate in enumerate(candidates):
        item_label = f"{label}.candidates[{index}]"
        if not exact_keys(candidate, CANDIDATE_KEYS, item_label, errors):
            continue
        name = candidate.get("name")
        if nonempty_string(name, f"{item_label}.name", errors):
            candidate_names.append(name)
        selected = candidate.get("selected")
        if not isinstance(selected, bool):
            errors.append(f"{item_label}.selected must be boolean")
            selected = False
        selected_count += int(selected)
        differs = nonempty_string_list(
            candidate.get("differs_on_axes"), f"{item_label}.differs_on_axes", errors
        )
        unknown_axes = set(differs) - DECOMPOSITION_AXES
        if unknown_axes:
            errors.append(f"{item_label}.differs_on_axes has unknown axes {sorted(unknown_axes)}")
        if not selected and not differs:
            errors.append(f"{item_label}.differs_on_axes must not be empty for an alternative")
        impacts = candidate.get("scenario_impacts")
        if not isinstance(impacts, list):
            errors.append(f"{item_label}.scenario_impacts: expected an array")
            continue
        impact_ids: list[str] = []
        for impact_index, impact in enumerate(impacts):
            impact_label = f"{item_label}.scenario_impacts[{impact_index}]"
            if not exact_keys(impact, SCENARIO_IMPACT_KEYS, impact_label, errors):
                continue
            scenario_id = impact.get("scenario_id")
            if isinstance(scenario_id, str):
                impact_ids.append(scenario_id)
            else:
                errors.append(f"{impact_label}.scenario_id must be a string")
            for key, minimum in (("components_crossed", 1), ("contracts_crossed", 0)):
                value = impact.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                    errors.append(f"{impact_label}.{key} must be an integer >= {minimum}")
            acceptable = impact.get("acceptable")
            if not isinstance(acceptable, bool):
                errors.append(f"{impact_label}.acceptable must be boolean")
            elif selected and not acceptable:
                errors.append(f"{impact_label}: selected candidate must accept every scenario")
            nonempty_string(impact.get("rationale"), f"{impact_label}.rationale", errors)
        if len(impact_ids) != len(set(impact_ids)) or set(impact_ids) != scenario_set:
            errors.append(
                f"{item_label}.scenario_impacts must cover each scenario exactly once; "
                f"missing={sorted(scenario_set - set(impact_ids))}, "
                f"extra={sorted(set(impact_ids) - scenario_set)}"
            )
    if len(candidate_names) != len(set(candidate_names)):
        errors.append(f"{label}.candidate names must be unique")
    if selected_count != 1:
        errors.append(f"{label}.candidates must contain exactly one selected candidate")
    return parsed


def parse_delivery_scope(path: Path, text: str, errors: list[str]) -> dict[str, Any] | None:
    """Parse the one machine-readable scope record."""

    starts = text.count(SCOPE_BEGIN)
    ends = text.count(SCOPE_END)
    if starts == 0 and ends == 0:
        return None
    if starts != 1 or ends != 1:
        errors.append(f"{path}: expected exactly one canonical delivery-scope block")
        return None
    start = text.find(SCOPE_BEGIN) + len(SCOPE_BEGIN)
    end = text.find(SCOPE_END, start)
    if end < start:
        errors.append(f"{path}: delivery-scope end marker precedes its begin marker")
        return None
    try:
        parsed = json.loads(
            text[start:end].strip(), object_pairs_hook=reject_duplicate_keys
        )
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{path}: invalid delivery-scope JSON: {exc}")
        return None
    if not isinstance(parsed, dict):
        errors.append(f"{path}: delivery-scope value must be an object")
        return None

    keys = set(parsed)
    if keys != SCOPE_REQUIRED_KEYS:
        errors.append(
            f"{path}: delivery-scope keys differ; "
            f"missing={sorted(SCOPE_REQUIRED_KEYS - keys)}, "
            f"extra={sorted(keys - SCOPE_REQUIRED_KEYS)}"
        )
        return None
    if parsed.get("schema_version") != 1:
        errors.append(f"{path}: delivery-scope.schema_version must equal 1")
    if not isinstance(parsed.get("delivery_scope_mode"), str) or parsed.get(
        "delivery_scope_mode"
    ) not in DELIVERY_SCOPE_MODES:
        errors.append(
            f"{path}: delivery-scope.delivery_scope_mode must be one of "
            f"{sorted(DELIVERY_SCOPE_MODES)}"
        )
    for key in ("requested_outcome", "impact_cone"):
        if not isinstance(parsed.get(key), str) or not parsed.get(key, "").strip():
            errors.append(f"{path}: delivery-scope.{key} must be a non-empty string")
    for key in (
        "preserved_behavior",
        "non_goals",
        "planned_phase_ids",
        "authorized_phase_ids",
        "applicable_documents",
    ):
        parsed[key] = nonempty_string_list(
            parsed.get(key), f"{path}: delivery-scope.{key}", errors
        )
    if not parsed.get("non_goals"):
        errors.append(f"{path}: delivery-scope.non_goals must not be empty")
    if not parsed.get("planned_phase_ids"):
        errors.append(f"{path}: delivery-scope.planned_phase_ids must not be empty")
    scope_mode = parsed.get("delivery_scope_mode")
    if (
        isinstance(scope_mode, str)
        and scope_mode in DELIVERY_SCOPE_MODES - {"full product"}
        and not parsed.get("preserved_behavior")
    ):
        errors.append(
            f"{path}: delivery-scope.preserved_behavior must not be empty for a bounded mode"
        )

    for key in ("planned_phase_ids", "authorized_phase_ids"):
        for phase_id in parsed.get(key, []):
            if not isinstance(phase_id, str) or not re.fullmatch(
                r"PH-\d{3,}-\d{2,}", phase_id
            ):
                errors.append(f"{path}: delivery-scope.{key} has invalid ID {phase_id!r}")
    planned = set(parsed.get("planned_phase_ids", []))
    authorized = set(parsed.get("authorized_phase_ids", []))
    if not authorized <= planned:
        errors.append(
            f"{path}: authorized_phase_ids must be a subset of planned_phase_ids; "
            f"extra={sorted(authorized - planned)}"
        )

    applicable = set(parsed.get("applicable_documents", []))
    concern_documents = set(FULL_PRODUCT_FILES)
    if not applicable <= concern_documents:
        errors.append(
            f"{path}: delivery-scope.applicable_documents has unknown paths "
            f"{sorted(applicable - concern_documents)}"
        )
    sources = parsed.get("preserved_document_sources")
    if not isinstance(sources, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, str)
        or not value.strip()
        for key, value in (sources.items() if isinstance(sources, dict) else [])
    ):
        errors.append(
            f"{path}: delivery-scope.preserved_document_sources must map paths to non-empty evidence"
        )
        return None
    omitted = concern_documents - applicable
    if set(sources) != omitted:
        errors.append(
            f"{path}: preserved_document_sources must cover exactly omitted concern documents; "
            f"missing={sorted(omitted - set(sources))}, "
            f"extra={sorted(set(sources) - omitted)}"
        )
    if parsed.get("delivery_scope_mode") == "full product" and applicable != concern_documents:
        errors.append(f"{path}: full product scope must mark every concern document applicable")
    return parsed


def validate_headings(path: Path, text: str, required: Iterable[str], errors: list[str]) -> None:
    for heading in missing_heading_names(text, required):
        errors.append(f"{path}: missing required section '## {heading.title()}'")


def validate_global_metadata(path: Path, text: str, warnings: list[str]) -> None:
    prefix = text[:1800].lower()
    for marker in GLOBAL_METADATA_MARKERS:
        if marker not in prefix:
            warnings.append(f"{path}: top-of-document metadata may be missing '{marker}'")


def normalize_inline_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    return value


def delivery_status_values(
    text: str, stage_body: str | None
) -> tuple[dict[str, str], dict[str, str]]:
    """Return unique metadata values and well-formed stage statuses."""

    visible_text = "\n".join(markdown_lines_outside_fences(text))
    metadata_values: dict[str, str] = {}
    for field in DELIVERY_STATUS_METADATA_FIELDS:
        field_values = re.findall(
            rf"^-\s+\*\*{re.escape(field)}:\*\*\s+(\S.*)$",
            visible_text[:2400],
            re.IGNORECASE | re.MULTILINE,
        )
        if len(field_values) == 1:
            metadata_values[field.casefold()] = normalize_inline_value(field_values[0])

    stage_statuses: dict[str, str] = {}
    if stage_body is not None:
        for stage in DELIVERY_STATUS_STAGES:
            rows = re.findall(
                rf"^\|\s*{re.escape(stage)}\s*\|\s*([^|\n]+)\|"
                r"\s*([^|\n]+)\|\s*([^|\n]+)\|\s*$",
                stage_body,
                re.IGNORECASE | re.MULTILINE,
            )
            if len(rows) == 1:
                stage_statuses[stage.casefold()] = normalize_inline_value(
                    rows[0][0]
                ).casefold()
    return metadata_values, stage_statuses


def validate_delivery_status(
    path: Path, text: str, errors: list[str], warnings: list[str]
) -> None:
    """Validate the concise derived operator view without making it authoritative."""

    visible_text = "\n".join(markdown_lines_outside_fences(text))
    stage_body = unique_level_heading_body(
        visible_text, "stage status", 2, path, errors
    )
    metadata_values, stage_statuses = delivery_status_values(text, stage_body)
    for field in DELIVERY_STATUS_METADATA_FIELDS:
        field_values = re.findall(
            rf"^-\s+\*\*{re.escape(field)}:\*\*\s+(\S.*)$",
            visible_text[:2400],
            re.IGNORECASE | re.MULTILINE,
        )
        if len(field_values) != 1:
            errors.append(
                f"{path}: top metadata must contain exactly one non-empty {field!r} field; "
                f"found {len(field_values)}"
            )
        else:
            metadata_values[field.casefold()] = normalize_inline_value(field_values[0])
    summary_type = metadata_values.get("summary type", "").casefold()
    if summary_type and summary_type != "derived human-readable delivery status":
        errors.append(
            f"{path}: Summary type must equal 'Derived human-readable delivery status'"
        )
    authority = metadata_values.get("authority", "").casefold()
    if authority and not authority.startswith("non-authoritative"):
        errors.append(
            f"{path}: Authority must begin with 'Non-authoritative'"
        )
    current_stage = metadata_values.get("current stage", "").casefold()
    if current_stage and current_stage not in DELIVERY_STATUS_CURRENT_STAGES:
        errors.append(
            f"{path}: Current stage must be one of "
            f"{sorted(DELIVERY_STATUS_CURRENT_STAGES)}"
        )
    current_status = metadata_values.get("current status", "").casefold()
    if current_status and current_status not in DELIVERY_STATUS_STAGE_STATUSES:
        errors.append(
            f"{path}: Current status must be one of "
            f"{sorted(DELIVERY_STATUS_STAGE_STATUSES)}"
        )
    last_updated = metadata_values.get("last updated", "")
    if last_updated:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_updated):
            errors.append(f"{path}: Last updated must use valid YYYY-MM-DD format")
        else:
            try:
                date.fromisoformat(last_updated)
            except ValueError:
                errors.append(f"{path}: Last updated must use valid YYYY-MM-DD format")
    validate_headings(path, visible_text, DELIVERY_STATUS_HEADINGS, errors)
    if stage_body is not None:
        for stage in DELIVERY_STATUS_STAGES:
            rows = re.findall(
                rf"^\|\s*{re.escape(stage)}\s*\|\s*([^|\n]+)\|"
                r"\s*([^|\n]+)\|\s*([^|\n]+)\|\s*$",
                stage_body,
                re.IGNORECASE | re.MULTILINE,
            )
            if len(rows) != 1:
                errors.append(
                    f"{path}: stage-status table must contain exactly one {stage!r} row; "
                    f"found {len(rows)}"
                )
                continue
            status = rows[0][0].strip().casefold()
            if status not in DELIVERY_STATUS_STAGE_STATUSES:
                errors.append(
                    f"{path}: {stage!r} status must be one of "
                    f"{sorted(DELIVERY_STATUS_STAGE_STATUSES)}"
                )
            if not rows[0][1].strip():
                errors.append(f"{path}: {stage!r} outcome cell must not be empty")
            if not rows[0][2].strip():
                errors.append(f"{path}: {stage!r} evidence cell must not be empty")
    if current_stage in stage_statuses and current_status:
        if current_status != stage_statuses[current_stage]:
            errors.append(
                f"{path}: Current status {current_status!r} must match the "
                f"{metadata_values.get('current stage')!r} stage row "
                f"{stage_statuses[current_stage]!r}"
            )
    word_count = len(re.findall(r"\b[\w'-]+\b", visible_text))
    if word_count > 1500:
        warnings.append(
            f"{path}: human delivery status is {word_count} words; keep it near one page"
        )


def validate_delivery_status_against_plan(
    status_path: Path,
    status_text: str,
    readme_path: Path,
    readme_text: str,
    errors: list[str],
) -> None:
    """Require the planning row to agree with the canonical planning readiness."""

    visible_readme = "\n".join(markdown_lines_outside_fences(readme_text))
    readiness_body = unique_level_heading_body(
        visible_readme,
        "planning status and phase-readiness statement",
        2,
        readme_path,
        errors,
    )
    if readiness_body is None:
        return
    matches = re.findall(
        r"^-\s+\*\*Planning status:\*\*\s+(\S.*)$",
        readiness_body,
        re.IGNORECASE | re.MULTILINE,
    )
    if len(matches) != 1:
        errors.append(
            f"{readme_path}: planning-readiness section must contain exactly one "
            f"non-empty 'Planning status' field; found {len(matches)}"
        )
        return
    planning_status = normalize_inline_value(matches[0]).casefold()
    expected_stage_status = PLANNING_STATUS_TO_STAGE_STATUS.get(planning_status)
    if expected_stage_status is None:
        errors.append(
            f"{readme_path}: Planning status must be one of "
            f"{sorted(PLANNING_STATUS_TO_STAGE_STATUS)}"
        )
        return

    visible_status = "\n".join(markdown_lines_outside_fences(status_text))
    stage_body = unique_level_heading_body(
        visible_status, "stage status", 2, status_path, None
    )
    _, stage_statuses = delivery_status_values(status_text, stage_body)
    planning_row_status = stage_statuses.get("planning")
    if planning_row_status and planning_row_status != expected_stage_status:
        errors.append(
            f"{status_path}: Planning row status {planning_row_status!r} disagrees with "
            f"{readme_path.name} Planning status {planning_status!r}; expected "
            f"{expected_stage_status!r}"
        )


def validate_required_file(
    path: Path,
    errors: list[str],
    warnings: list[str],
) -> str:
    text = read_text(path, errors)
    if not text:
        errors.append(f"{path}: required file is empty or unreadable")
        return ""

    if path.name == "delivery-status.md":
        validate_delivery_status(path, text, errors, warnings)
    else:
        validate_global_metadata(path, text, warnings)

    required: tuple[str, ...] | None = None
    if path.name == "README.md":
        required = README_HEADINGS
    elif path.name == "delivery-status.md":
        required = None
    elif path.name == "00-product-description.md":
        required = PRODUCT_DESCRIPTION_HEADINGS
    elif path.name == "92-delivery-roadmap.md":
        required = ROADMAP_HEADINGS
    elif path.name == "93-implementation-units.md":
        required = IMPLEMENTATION_UNITS_HEADINGS

    if required is not None:
        validate_headings(path, text, required, errors)

    if path.name in {"92-delivery-roadmap.md", "93-implementation-units.md"}:
        lowered = text.lower()
        missing = [value for value in DEPENDENCY_CLASSIFICATIONS if value not in lowered]
        if missing:
            errors.append(f"{path}: missing dependency classifications: {', '.join(missing)}")

    if path.name not in {"04-external-system-evidence.md", "99-open-questions.md"}:
        for pattern in UNRESOLVED_PATTERNS:
            if pattern.search(text):
                warnings.append(f"{path}: contains unresolved marker matching /{pattern.pattern}/")

    return text


def phase_subsection_body(block: str, heading: str) -> str | None:
    match = re.search(
        rf"^####\s+{re.escape(heading)}\s*$\n(?P<body>.*?)(?=^#{{1,4}}\s|\Z)",
        block,
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match else None


def validate_component(
    path: Path,
    errors: list[str],
    warnings: list[str],
    minimum_phase_count: int,
    included_phase_ids: set[str] | None = None,
    require_atomicity_rationale: bool = False,
) -> ComponentRecord | None:
    text = read_text(path, errors)
    if not text:
        return None

    validate_global_metadata(path, text, warnings)
    validate_headings(path, text, COMPONENT_HEADINGS, errors)

    component_matches = list(COMPONENT_ID_RE.finditer(text[:2200]))
    if len(component_matches) != 1:
        errors.append(f"{path}: expected exactly one top-of-document 'Component ID: CMP-###' entry")
        return None

    component_id = component_matches[0].group(1).upper()
    component_number = component_matches[0].group(2)

    all_phase_matches = list(PHASE_RE.finditer(text))
    phase_matches = [
        (index, match)
        for index, match in enumerate(all_phase_matches)
        if included_phase_ids is None or match.group(1).upper() in included_phase_ids
    ]
    if len(phase_matches) < minimum_phase_count:
        errors.append(
            f"{path}: expected at least {minimum_phase_count} "
            "'### PH-###-## — ...' phase section(s)"
        )
        return ComponentRecord(path, component_id, tuple(), tuple())

    phase_ids: list[str] = []
    phase_write_paths: list[tuple[str, tuple[str, ...]]] = []
    boundaries = [match.start() for match in all_phase_matches] + [len(text)]
    for index, match in phase_matches:
        phase_id = match.group(1).upper()
        phase_component_number = match.group(2)
        phase_ids.append(phase_id)

        if phase_component_number != component_number:
            errors.append(
                f"{path}: {phase_id} does not belong to {component_id}; numeric prefixes must match"
            )

        block = text[boundaries[index] : boundaries[index + 1]]
        phase_name = match.group(0).strip()
        for heading in missing_heading_names(block, PHASE_SUBHEADINGS):
            errors.append(f"{path}: {phase_name} missing '#### {heading.title()}'")

        write_domain_body = phase_subsection_body(block, "Expected write domains")
        write_paths = expected_write_paths(write_domain_body) if write_domain_body is not None else []
        if not write_paths:
            errors.append(
                f"{path}: {phase_id} must list at least one backticked repository-relative "
                "pattern under '#### Expected write domains'"
            )
        if len(write_paths) != len(set(write_paths)):
            errors.append(f"{path}: {phase_id} expected write-domain paths must be unique")
        for write_index, write_path in enumerate(write_paths):
            validate_repository_pattern(
                write_path,
                f"{path}: {phase_id} expected write domain[{write_index}]",
                errors,
            )
        phase_write_paths.append((phase_id, tuple(write_paths)))

        if require_atomicity_rationale and len(phase_matches) == 1:
            atomicity = re.search(
                r"^####\s+Atomicity rationale\s*$\n(?P<body>.*?)(?=^#{1,4}\s|\Z)",
                block,
                re.IGNORECASE | re.MULTILINE | re.DOTALL,
            )
            if not atomicity or not atomicity.group("body").strip():
                errors.append(
                    f"{path}: {phase_id} requires a non-empty '#### Atomicity rationale'"
                )

        lowered = block.lower()
        if not any(value in lowered for value in DEPENDENCY_CLASSIFICATIONS):
            errors.append(
                f"{path}: {phase_id} must name a dependency or preliminary parallelization classification"
            )

    if len(phase_ids) != len(set(phase_ids)):
        errors.append(f"{path}: duplicate phase IDs found within the component document")

    for pattern in VAGUE_PATTERNS:
        if pattern.search(text):
            warnings.append(f"{path}: contains vague phrase matching /{pattern.pattern}/")

    return ComponentRecord(
        path,
        component_id,
        tuple(phase_ids),
        tuple(phase_write_paths),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a planning root for the product planning skill."
    )
    parser.add_argument(
        "repository_root",
        nargs="?",
        default=".",
        help="Target repository root (default: current directory)",
    )
    parser.add_argument(
        "--plan-root",
        help=(
            "Planning root to validate; relative paths resolve from repository_root "
            "(default: docs/implementation-plan)"
        ),
    )
    args = parser.parse_args()

    repo_root = Path(args.repository_root).expanduser().resolve()
    if args.plan_root:
        selected_plan_root = Path(args.plan_root).expanduser()
        plan_root = (
            selected_plan_root
            if selected_plan_root.is_absolute()
            else repo_root / selected_plan_root
        ).resolve()
    else:
        plan_root = repo_root / PLAN_RELATIVE_PATH
    errors: list[str] = []
    warnings: list[str] = []

    if not plan_root.is_dir():
        print(f"ERROR: planning directory does not exist: {plan_root}")
        return 1

    product_description_path = plan_root / "00-product-description.md"
    product_description = (
        read_text(product_description_path, errors) if product_description_path.is_file() else ""
    )
    scope_block_present = SCOPE_BEGIN in product_description or SCOPE_END in product_description
    scope = parse_delivery_scope(product_description_path, product_description, errors)

    required_texts: dict[str, str] = {}
    for filename in CORE_REQUIRED_FILES:
        path = plan_root / filename
        if not path.is_file():
            errors.append(f"missing required file: {path}")
        else:
            text = validate_required_file(path, errors, warnings)
            required_texts[filename] = text

    readme_text = required_texts.get("README.md", "")
    delivery_status_text = required_texts.get("delivery-status.md", "")
    if readme_text and delivery_status_text:
        validate_delivery_status_against_plan(
            plan_root / "delivery-status.md",
            delivery_status_text,
            plan_root / "README.md",
            readme_text,
            errors,
        )

    if scope is None:
        delivery_scope_mode = "full product"
        if not scope_block_present:
            errors.append(
                "00-product-description.md: missing canonical delivery-scope block; "
                "normalize the legacy plan before validation or implementation handoff"
            )
        applicable_documents = set(FULL_PRODUCT_FILES)
        planned_phase_ids: set[str] | None = None
    else:
        delivery_scope_mode = scope.get("delivery_scope_mode")
        applicable_documents = set(scope.get("applicable_documents", []))
        planned_phase_ids = set(scope.get("planned_phase_ids", []))

    for filename in FULL_PRODUCT_FILES:
        path = plan_root / filename
        if filename in applicable_documents and not path.is_file():
            errors.append(f"missing required file: {path}")
        elif path.is_file():
            required_texts[filename] = validate_required_file(path, errors, warnings)

    components_dir = plan_root / "components"
    if not components_dir.is_dir():
        errors.append(f"missing components directory: {components_dir}")
        component_files: list[Path] = []
    else:
        component_files = sorted(
            path
            for path in components_dir.glob("*.md")
            if path.is_file() and not path.name.startswith(".")
        )
        if not component_files:
            errors.append(f"no component plans found in: {components_dir}")

    phase_occurrences: dict[str, list[Path]] = {}
    for path in component_files:
        for match in PHASE_RE.finditer(read_text(path, errors)):
            phase_occurrences.setdefault(match.group(1).upper(), []).append(path)

    if planned_phase_ids is None:
        selected_files = component_files
    else:
        for phase_id in sorted(planned_phase_ids):
            occurrences = phase_occurrences.get(phase_id, [])
            if len(occurrences) != 1:
                errors.append(
                    f"delivery-scope planned phase {phase_id} must occur exactly once; "
                    f"found {len(occurrences)}"
                )
        if delivery_scope_mode == "full product":
            selected_files = component_files
            discovered_phase_ids = set(phase_occurrences)
            if planned_phase_ids != discovered_phase_ids:
                errors.append(
                    "full product planned_phase_ids must equal all component phase IDs; "
                    f"missing={sorted(discovered_phase_ids - planned_phase_ids)}, "
                    f"extra={sorted(planned_phase_ids - discovered_phase_ids)}"
                )
        else:
            selected_files = sorted(
                {
                    path
                    for phase_id in planned_phase_ids
                    for path in phase_occurrences.get(phase_id, [])
                }
            )
        if not selected_files:
            errors.append("no component plan contains a delivery-scope planned phase")

    records = [
        record
        for path in selected_files
        if (
            record := validate_component(
                path,
                errors,
                warnings,
                minimum_phase_count=2 if delivery_scope_mode == "full product" else 1,
                included_phase_ids=planned_phase_ids,
                require_atomicity_rationale=delivery_scope_mode != "full product",
            )
        )
        is not None
    ]

    component_ids = [record.component_id for record in records]
    if len(component_ids) != len(set(component_ids)):
        errors.append("component IDs must be unique across component documents")

    phase_locations: dict[str, Path] = {}
    phase_write_domains: dict[str, tuple[str, tuple[str, ...]]] = {}
    for record in records:
        for phase_id in record.phase_ids:
            if phase_id in phase_locations:
                errors.append(
                    f"duplicate phase ID {phase_id}: {phase_locations[phase_id]} and {record.path}"
                )
            else:
                phase_locations[phase_id] = record.path
        for phase_id, write_paths in record.phase_write_paths:
            phase_write_domains[phase_id] = (record.component_id, write_paths)

    roadmap_text = required_texts.get("92-delivery-roadmap.md", "")
    handoff_text = required_texts.get("93-implementation-units.md", "")
    readme_text = required_texts.get("README.md", "")
    decomposition = parse_decomposition_assessment(
        plan_root / "93-implementation-units.md", handoff_text, errors
    )
    if decomposition is not None:
        known_components = set(component_ids)
        for index, ownership in enumerate(decomposition.get("data_ownership", [])):
            if not isinstance(ownership, dict):
                continue
            label = f"93-implementation-units.md: data_ownership[{index}]"
            owner = ownership.get("owner_component_id")
            writers = ownership.get("authorized_writer_component_ids")
            if (
                not isinstance(owner, str)
                or not re.fullmatch(r"CMP-\d{3,}", owner)
                or not isinstance(writers, list)
                or any(
                    not isinstance(writer, str)
                    or not re.fullmatch(r"CMP-\d{3,}", writer)
                    for writer in writers
                )
            ):
                continue
            unknown = {owner, *writers} - known_components
            if unknown:
                errors.append(
                    f"{label}: component IDs must exist in the in-scope component plans; "
                    f"unknown={sorted(unknown)}"
                )

        ownership_records = [
            record
            for record in decomposition.get("data_ownership", [])
            if isinstance(record, dict)
        ]
        for phase_id, (component_id, write_paths) in phase_write_domains.items():
            for ownership in ownership_records:
                declared_paths = ownership.get("write_paths")
                writers = ownership.get("authorized_writer_component_ids")
                if (
                    not isinstance(declared_paths, list)
                    or any(not isinstance(path, str) for path in declared_paths)
                    or not isinstance(writers, list)
                    or any(not isinstance(writer, str) for writer in writers)
                ):
                    continue
                if not any(
                    patterns_may_overlap(write_path, declared_path)
                    for write_path in write_paths
                    for declared_path in declared_paths
                ):
                    continue
                if component_id not in writers:
                    errors.append(
                        f"{phase_locations.get(phase_id, plan_root)}: {phase_id} component "
                        f"{component_id} has an expected write domain overlapping resource "
                        f"{ownership.get('resource')!r} but is not an authorized writer; "
                        f"allowed={sorted(writers)}"
                    )

    for component_id in component_ids:
        if component_id not in roadmap_text:
            errors.append(f"92-delivery-roadmap.md: missing component ID {component_id}")
        if component_id not in handoff_text:
            errors.append(f"93-implementation-units.md: missing component ID {component_id}")
        if component_id not in readme_text:
            warnings.append(f"README.md: identifier registry may be missing {component_id}")

    for phase_id in phase_locations:
        if phase_id not in roadmap_text:
            errors.append(f"92-delivery-roadmap.md: missing phase ID {phase_id}")
        if phase_id not in handoff_text:
            errors.append(f"93-implementation-units.md: missing phase ID {phase_id}")
        if phase_id not in readme_text:
            warnings.append(f"README.md: identifier registry may be missing {phase_id}")

    combined_text = ""
    for path in plan_root.rglob("*.md"):
        try:
            combined_text += "\n" + path.read_text(encoding="utf-8")
        except OSError:
            pass

    if not REQUIREMENT_ID_RE.search(combined_text):
        errors.append("no requirement IDs found; expected IDs such as FR-001, NFR-001, or CON-001")

    if re.search(r"\bdeferred decision", combined_text, re.IGNORECASE) and not DEFERRED_DECISION_RE.search(
        combined_text
    ):
        warnings.append("deferred decisions are mentioned but no DEC-### identifiers were found")

    print(f"Plan root: {plan_root}")
    print(f"Component plans in scope: {len(selected_files)}")
    print(f"Component IDs: {len(component_ids)}")
    print(f"Phase IDs: {len(phase_locations)}")

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
