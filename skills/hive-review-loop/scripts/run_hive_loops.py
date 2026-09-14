#!/usr/bin/env python3
"""Run one or many Hive-backed implementation/reviewer loops from YAML."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


WORKFLOW_NAME = "implement-and-run-reviewers"


class ConfigError(ValueError):
    """The launcher configuration is invalid or unsafe to execute."""


@dataclass(frozen=True)
class Source:
    path: Path
    purpose: str


@dataclass(frozen=True)
class Context:
    text: str
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class HiveCommands:
    workflow: str
    registry: str


@dataclass(frozen=True)
class Assignment:
    identifier: str
    repo: Path
    run_dir: Path
    implementor: str
    reviewers: tuple[str, ...]
    max_rounds: int
    include_diff: bool
    cleanup_on_success: bool
    shared_context: Context
    task_context: Context


@dataclass(frozen=True)
class LaunchPlan:
    commands: HiveCommands
    assignments: tuple[Assignment, ...]
    max_parallel_runs: int
    artifact_root: Optional[Path]


@dataclass(frozen=True)
class SummaryAssessment:
    path: Path
    consensus_reached: Optional[bool]
    failed_steps: Optional[int]
    unmet_loops: Optional[int]
    error: Optional[str]


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{field} must be a mapping")
    return value


def _known_keys(value: dict[str, Any], allowed: set[str], field: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"{field} has unknown field(s): {', '.join(unknown)}")


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string")
    if value != value.strip():
        raise ConfigError(f"{field} must not have surrounding whitespace")
    return value


def _positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(f"{field} must be an integer greater than or equal to 1")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{field} must be true or false")
    return value


def _existing_path(value: Any, field: str, directory: Optional[bool]) -> Path:
    raw = _nonempty_string(value, field)
    path = Path(raw)
    if not path.is_absolute():
        raise ConfigError(f"{field} must be an absolute path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ConfigError(f"{field} does not resolve: {error}") from error
    if directory is True and not resolved.is_dir():
        raise ConfigError(f"{field} must name an existing directory: {resolved}")
    if directory is False and not resolved.is_file():
        expected = "file"
        raise ConfigError(f"{field} must name an existing {expected}: {resolved}")
    return resolved


def _future_directory(value: Any, field: str) -> Path:
    raw = _nonempty_string(value, field)
    path = Path(raw)
    if not path.is_absolute():
        raise ConfigError(f"{field} must be an absolute path")
    resolved = path.resolve(strict=False)
    if resolved == Path(resolved.anchor):
        raise ConfigError(f"{field} must not be a filesystem root")
    if resolved.exists() and not resolved.is_dir():
        raise ConfigError(f"{field} exists and is not a directory: {resolved}")
    return resolved


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        if first.exists() and second.exists() and os.path.samefile(first, second):
            return True
    except OSError:
        pass
    return first == second or first in second.parents or second in first.parents


def _load_document(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read configuration {path}: {error}") from error

    if path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise ConfigError(f"invalid JSON in {path}: {error}") from error

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as error:
        raise ConfigError(
            "YAML configuration requires PyYAML; install it or use JSON"
        ) from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML in {path}: {error}") from error


def _context(value: Any, field: str, required: bool) -> Context:
    if value is None and not required:
        return Context(text="", sources=())
    data = _mapping(value, field)
    _known_keys(data, {"text", "sources"}, field)
    text = data.get("text", "")
    if not isinstance(text, str):
        raise ConfigError(f"{field}.text must be a string")
    sources_value = data.get("sources", [])
    if not isinstance(sources_value, list):
        raise ConfigError(f"{field}.sources must be a list")

    sources: list[Source] = []
    for index, raw_source in enumerate(sources_value):
        source_field = f"{field}.sources[{index}]"
        source_data = _mapping(raw_source, source_field)
        _known_keys(source_data, {"path", "purpose"}, source_field)
        source_path = _existing_path(source_data.get("path"), f"{source_field}.path", directory=None)
        purpose = _nonempty_string(source_data.get("purpose"), f"{source_field}.purpose")
        sources.append(Source(path=source_path, purpose=purpose))

    if required and not text.strip() and not sources:
        raise ConfigError(f"{field} must provide text, at least one source, or both")
    if required and not text.strip() and sources and not any(source.path.is_file() for source in sources):
        raise ConfigError(
            f"{field} must include task text or an exact task file; directories may only add supporting context"
        )
    return Context(text=text.strip(), sources=tuple(sources))


def _agent_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{field} must be a non-empty list of registry agent names")
    agents = tuple(_nonempty_string(item, f"{field}[{index}]") for index, item in enumerate(value))
    if any("," in agent for agent in agents):
        raise ConfigError(f"{field} entries must not contain commas")
    return agents


def _resolve_command(value: Any, field: str) -> str:
    raw = _nonempty_string(value, field)
    if os.sep in raw or (os.altsep is not None and os.altsep in raw):
        path = Path(raw)
        if not path.is_absolute():
            raise ConfigError(f"{field} must be absolute when it contains a directory separator")
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise ConfigError(f"{field} does not resolve: {error}") from error
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise ConfigError(f"{field} is not an executable file: {resolved}")
        return str(resolved)
    resolved = shutil.which(raw)
    if resolved is None:
        raise ConfigError(f"{field} is not available on PATH: {raw}")
    return str(Path(resolved).resolve())


def _hive_commands(value: Any) -> HiveCommands:
    data = _mapping(value, "hive")
    _known_keys(data, {"workflow_cli", "registry_cli"}, "hive")
    return HiveCommands(
        workflow=_resolve_command(data.get("workflow_cli", "hive_workflow"), "hive.workflow_cli"),
        registry=_resolve_command(data.get("registry_cli", "hive_registry"), "hive.registry_cli"),
    )


def _settings(data: dict[str, Any], field: str, defaults: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    allowed = {"implementor", "reviewers", "max_rounds", "diff", "cleanup_on_success"}
    _known_keys(data, allowed, field)
    merged = dict(defaults or {})
    merged.update(data)
    if "implementor" not in merged:
        raise ConfigError(f"{field}.implementor is required directly or through defaults")
    if "reviewers" not in merged:
        raise ConfigError(f"{field}.reviewers is required directly or through defaults")
    return {
        "implementor": _nonempty_string(merged["implementor"], f"{field}.implementor"),
        "reviewers": _agent_list(merged["reviewers"], f"{field}.reviewers"),
        "max_rounds": _positive_integer(merged.get("max_rounds", 5), f"{field}.max_rounds"),
        "include_diff": _boolean(merged.get("diff", True), f"{field}.diff"),
        "cleanup_on_success": _boolean(
            merged.get("cleanup_on_success", True), f"{field}.cleanup_on_success"
        ),
    }


def _validate_repo(repo: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        check=False,
    )
    if result.returncode != 0:
        raise ConfigError(f"repository is not a Git worktree: {repo}: {result.stderr.strip()}")
    try:
        root = Path(result.stdout.strip()).resolve(strict=True)
    except OSError as error:
        raise ConfigError(f"Git returned an invalid root for {repo}: {error}") from error
    if root != repo:
        raise ConfigError(f"repo must be the Git worktree root, not a subdirectory: {repo} (root: {root})")


def load_single(path: Path) -> LaunchPlan:
    data = _mapping(_load_document(path), "configuration")
    _known_keys(
        data,
        {
            "schema_version", "hive", "repo", "run_dir", "implementor", "reviewers",
            "max_rounds", "diff", "cleanup_on_success", "context",
        },
        "configuration",
    )
    if data.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")
    commands = _hive_commands(data.get("hive", {}))
    repo = _existing_path(data.get("repo"), "repo", directory=True)
    run_dir = _future_directory(data.get("run_dir"), "run_dir")
    if _paths_overlap(repo, run_dir):
        raise ConfigError("run_dir must be outside the reviewed repository")
    settings_data = {key: data[key] for key in ("implementor", "reviewers", "max_rounds", "diff", "cleanup_on_success") if key in data}
    settings = _settings(settings_data, "configuration")
    assignment = Assignment(
        identifier="review",
        repo=repo,
        run_dir=run_dir,
        shared_context=Context(text="", sources=()),
        task_context=_context(data.get("context"), "context", required=True),
        **settings,
    )
    return LaunchPlan(commands=commands, assignments=(assignment,), max_parallel_runs=1, artifact_root=None)


def load_parallel(path: Path) -> LaunchPlan:
    data = _mapping(_load_document(path), "configuration")
    _known_keys(
        data,
        {
            "schema_version", "hive", "artifact_root", "max_parallel_runs", "defaults",
            "general_context", "assignments",
        },
        "configuration",
    )
    if data.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")
    commands = _hive_commands(data.get("hive", {}))
    artifact_root = _future_directory(data.get("artifact_root"), "artifact_root")
    max_parallel_runs = _positive_integer(data.get("max_parallel_runs", 1), "max_parallel_runs")
    defaults = _mapping(data.get("defaults", {}), "defaults")
    _known_keys(defaults, {"implementor", "reviewers", "max_rounds", "diff", "cleanup_on_success"}, "defaults")
    shared = _context(data.get("general_context"), "general_context", required=False)
    raw_assignments = data.get("assignments")
    if not isinstance(raw_assignments, list) or not raw_assignments:
        raise ConfigError("assignments must be a non-empty list")

    assignments: list[Assignment] = []
    identifiers: set[str] = set()
    for index, raw_assignment in enumerate(raw_assignments):
        field = f"assignments[{index}]"
        assignment_data = _mapping(raw_assignment, field)
        _known_keys(
            assignment_data,
            {
                "id", "repo", "context", "implementor", "reviewers", "max_rounds", "diff",
                "cleanup_on_success",
            },
            field,
        )
        identifier = _nonempty_string(assignment_data.get("id"), f"{field}.id")
        if identifier in {".", ".."} or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in identifier):
            raise ConfigError(f"{field}.id may contain only letters, digits, dot, underscore, and hyphen")
        folded = identifier.casefold()
        if folded in identifiers:
            raise ConfigError(f"duplicate assignment id ignoring case: {identifier}")
        identifiers.add(folded)
        repo = _existing_path(assignment_data.get("repo"), f"{field}.repo", directory=True)
        run_dir = (artifact_root / identifier / "hive-run").resolve(strict=False)
        launcher_dir = (artifact_root / identifier / "launcher").resolve(strict=False)
        for candidate, candidate_name in ((run_dir, "Hive run"), (launcher_dir, "launcher artifacts")):
            if _paths_overlap(repo, candidate):
                raise ConfigError(f"{candidate_name} for {identifier} must be outside its repository")
        setting_values = {
            key: assignment_data[key]
            for key in ("implementor", "reviewers", "max_rounds", "diff", "cleanup_on_success")
            if key in assignment_data
        }
        settings = _settings(setting_values, field, defaults=defaults)
        assignments.append(
            Assignment(
                identifier=identifier,
                repo=repo,
                run_dir=run_dir,
                shared_context=shared,
                task_context=_context(assignment_data.get("context"), f"{field}.context", required=True),
                **settings,
            )
        )

    for index, assignment in enumerate(assignments):
        for earlier in assignments[:index]:
            if _paths_overlap(assignment.repo, earlier.repo):
                raise ConfigError(
                    f"assignment repositories must be disjoint: {assignment.identifier} overlaps {earlier.identifier}"
                )
            if _paths_overlap(assignment.run_dir, earlier.run_dir):
                raise ConfigError(f"assignment run directories overlap: {assignment.identifier} and {earlier.identifier}")
        for repository_owner in assignments:
            if _paths_overlap(assignment.run_dir, repository_owner.repo) or _paths_overlap(
                _launcher_dir(assignment), repository_owner.repo
            ):
                raise ConfigError(
                    f"artifacts for {assignment.identifier} overlap repository {repository_owner.identifier}"
                )

    return LaunchPlan(
        commands=commands,
        assignments=tuple(assignments),
        max_parallel_runs=min(max_parallel_runs, len(assignments)),
        artifact_root=artifact_root,
    )


def _registry_environment(commands: HiveCommands) -> dict[str, str]:
    return {**os.environ, "HIVE_REGISTRY_CLI": commands.registry}


def _canonicalize_agents(plan: LaunchPlan) -> LaunchPlan:
    environment = _registry_environment(plan.commands)
    listed = subprocess.run(
        [plan.commands.registry, "list", "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )
    if listed.returncode != 0:
        raise ConfigError(f"hive_registry list failed: {listed.stderr.strip()}")
    try:
        payload = json.loads(listed.stdout)
        roster_values = payload["agents"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ConfigError("hive_registry list --json returned an invalid payload") from error
    if not isinstance(roster_values, list):
        raise ConfigError("hive_registry roster must contain an agents list")

    roster: dict[str, tuple[str, set[str]]] = {}
    for item in roster_values:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not isinstance(item.get("capabilities"), list)
            or not all(isinstance(capability, str) for capability in item["capabilities"])
        ):
            raise ConfigError("hive_registry roster contains an invalid agent record")
        roster[item["id"].casefold()] = (item["id"], set(item["capabilities"]))

    selected: list[str] = []
    normalized: list[Assignment] = []
    for assignment in plan.assignments:
        implementor_record = roster.get(assignment.implementor.casefold())
        if implementor_record is None:
            raise ConfigError(f"unknown implementor registry agent: {assignment.implementor}")
        if "act" not in implementor_record[1]:
            raise ConfigError(f"implementor agent lacks act capability: {implementor_record[0]}")
        reviewers: list[str] = []
        for reviewer in assignment.reviewers:
            record = roster.get(reviewer.casefold())
            if record is None:
                raise ConfigError(f"unknown reviewer registry agent: {reviewer}")
            if "read_only" not in record[1]:
                raise ConfigError(f"reviewer agent lacks read_only capability: {record[0]}")
            reviewers.append(record[0])
        selected.extend((implementor_record[0], *reviewers))
        normalized.append(
            replace(assignment, implementor=implementor_record[0], reviewers=tuple(reviewers))
        )

    unique_selected = list(dict.fromkeys(selected))
    doctor = subprocess.run(
        [plan.commands.registry, "doctor", *unique_selected],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )
    if doctor.returncode != 0:
        details = doctor.stderr.strip() or doctor.stdout.strip()
        raise ConfigError(f"hive_registry doctor failed: {details}")

    described = subprocess.run(
        [plan.commands.workflow, "describe", WORKFLOW_NAME],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=environment,
        check=False,
    )
    if described.returncode != 0:
        raise ConfigError(
            f"hive_workflow does not provide {WORKFLOW_NAME}: {described.stderr.strip()}"
        )
    return replace(plan, assignments=tuple(normalized))


def _validate_resume_manifest(assignment: Assignment) -> None:
    manifest_path = assignment.run_dir / "run.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read existing Hive run manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("workflow") != WORKFLOW_NAME:
        raise ConfigError(f"existing run is not a {WORKFLOW_NAME} run: {assignment.run_dir}")
    params = manifest.get("params")
    if not isinstance(params, dict):
        raise ConfigError(f"existing Hive run has invalid params: {manifest_path}")

    expected = {
        "implementor": assignment.implementor,
        "reviewers": list(assignment.reviewers),
        "diff": assignment.include_diff,
        "prompt": _prompt(assignment),
    }
    for field, value in expected.items():
        if params.get(field) != value:
            raise ConfigError(
                f"resume configuration changes recorded {field} for {assignment.identifier}; start a new run instead"
            )
    recorded_repo = params.get("repo")
    if not isinstance(recorded_repo, str) or Path(recorded_repo).resolve(strict=False) != assignment.repo:
        raise ConfigError(
            f"resume configuration changes recorded repo for {assignment.identifier}; start a new run instead"
        )
    recorded_rounds = params.get("maxRounds")
    if isinstance(recorded_rounds, bool) or not isinstance(recorded_rounds, int):
        raise ConfigError(f"existing Hive run has invalid maxRounds: {manifest_path}")
    if assignment.max_rounds < recorded_rounds:
        raise ConfigError(
            f"resume may extend max_rounds for {assignment.identifier}, but may not reduce it below {recorded_rounds}"
        )


def preflight(plan: LaunchPlan, resume: bool) -> LaunchPlan:
    for assignment in plan.assignments:
        _validate_repo(assignment.repo)
        run_manifest = assignment.run_dir / "run.json"
        if run_manifest.exists() and not resume:
            raise ConfigError(
                f"run already exists for {assignment.identifier}; use --resume or choose another run directory"
            )
        if assignment.run_dir.exists() and any(assignment.run_dir.iterdir()) and not run_manifest.exists():
            raise ConfigError(
                f"run directory is non-empty but has no run.json: {assignment.run_dir}"
            )
        launcher_dir = _launcher_dir(assignment)
        if not resume and launcher_dir.exists() and any(launcher_dir.iterdir()):
            raise ConfigError(
                f"launcher directory is non-empty for a new run: {launcher_dir}"
            )
    normalized = _canonicalize_agents(plan)
    if resume:
        for assignment in normalized.assignments:
            if (assignment.run_dir / "run.json").exists():
                _validate_resume_manifest(assignment)
    return normalized


def _render_context(title: str, context: Context) -> list[str]:
    lines = [f"## {title}"]
    if context.text:
        lines.extend(("", context.text))
    if context.sources:
        lines.extend(("", "Sources available to implementor and reviewers:"))
        lines.extend(f"- `{source.path}` — {source.purpose}" for source in context.sources)
    if not context.text and not context.sources:
        lines.extend(("", "None supplied."))
    return lines


def _prompt(assignment: Assignment) -> str:
    lines = [
        "# Hive implementation and review assignment",
        "",
        f"Assignment ID: `{assignment.identifier}`",
        f"Repository: `{assignment.repo}`",
        "",
        *_render_context("Shared context", assignment.shared_context),
        "",
        *_render_context("Task context", assignment.task_context),
        "",
        "## Required execution behavior",
        "",
        "Implement the complete task in the named repository, preserve unrelated user changes, "
        "run appropriate implementation-side validation, and report the checks and outcomes. "
        "Every reviewer receives this complete task context directly and performs the workflow's "
        "strictly static read-only review. Address valid findings until every configured reviewer "
        "passes or the round limit is exhausted.",
    ]
    return "\n".join(lines).strip() + "\n"


def _launcher_dir(assignment: Assignment) -> Path:
    if assignment.run_dir.name == "hive-run":
        return assignment.run_dir.parent / "launcher"
    return assignment.run_dir.parent / f"{assignment.run_dir.name}-launcher"


def _next_log_prefix(launcher_dir: Path, base: str) -> str:
    candidate = base
    suffix = 2
    while (launcher_dir / f"{candidate}.stdout.log").exists() or (
        launcher_dir / f"{candidate}.stderr.log"
    ).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _workflow_command(plan: LaunchPlan, assignment: Assignment, resume: bool) -> tuple[list[str], bool]:
    run_manifest = assignment.run_dir / "run.json"
    if resume and run_manifest.exists():
        return (
            [
                plan.commands.workflow,
                "resume",
                str(assignment.run_dir),
                "--max-rounds",
                str(assignment.max_rounds),
                "--no-ui",
                "--print-run-dir",
            ],
            True,
        )
    return (
        [
            plan.commands.workflow,
            "run",
            WORKFLOW_NAME,
            "--implementor",
            assignment.implementor,
            "--reviewers",
            ",".join(assignment.reviewers),
            "--max-rounds",
            str(assignment.max_rounds),
            "--repo",
            str(assignment.repo),
            f"--diff={'true' if assignment.include_diff else 'false'}",
            "--prompt",
            _prompt(assignment),
            "--run-dir",
            str(assignment.run_dir),
            "--no-ui",
            "--print-run-dir",
        ],
        False,
    )


def _stdout_reports_run_dir(stdout: str, expected: Path, cwd: Path) -> bool:
    for line in stdout.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        try:
            path = Path(candidate)
            if not path.is_absolute():
                path = cwd / path
            if path.resolve(strict=False) == expected:
                return True
        except (OSError, ValueError):
            continue
    return False


def _summary_assessment(assignment: Assignment) -> SummaryAssessment:
    summary_path = assignment.run_dir / "summary.json"

    def invalid(message: str) -> SummaryAssessment:
        return SummaryAssessment(
            path=summary_path,
            consensus_reached=None,
            failed_steps=None,
            unmet_loops=None,
            error=message,
        )

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return invalid("Hive summary.json is missing")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return invalid(f"cannot read Hive summary.json: {error}")
    if not isinstance(payload, dict):
        return invalid("Hive summary.json must contain an object")
    if payload.get("workflow") != WORKFLOW_NAME:
        return invalid(f"Hive summary.json does not identify workflow {WORKFLOW_NAME}")

    recorded_run_dir = payload.get("runDir")
    if not isinstance(recorded_run_dir, str) or not recorded_run_dir.strip():
        return invalid("Hive summary.json has no valid runDir")
    recorded_path = Path(recorded_run_dir)
    if not recorded_path.is_absolute():
        recorded_path = assignment.repo / recorded_path
    if recorded_path.resolve(strict=False) != assignment.run_dir:
        return invalid("Hive summary.json runDir does not match the configured run directory")

    failed_steps = payload.get("failed")
    if isinstance(failed_steps, bool) or not isinstance(failed_steps, int) or failed_steps < 0:
        return invalid("Hive summary.json failed must be a non-negative integer")
    unmet_loops = payload.get("unmetLoops")
    if isinstance(unmet_loops, bool) or not isinstance(unmet_loops, int) or unmet_loops < 0:
        return invalid("Hive summary.json unmetLoops must be a non-negative integer")

    collected = payload.get("collected")
    if not isinstance(collected, list) or not collected:
        return invalid("Hive summary.json has no collected reviewer verdict")
    final_collection = collected[-1]
    if not isinstance(final_collection, dict) or not isinstance(final_collection.get("approved"), bool):
        return invalid("Hive summary.json final collected result has no boolean approved verdict")

    return SummaryAssessment(
        path=summary_path,
        consensus_reached=final_collection["approved"],
        failed_steps=failed_steps,
        unmet_loops=unmet_loops,
        error=None,
    )


def execute_assignment(plan: LaunchPlan, assignment: Assignment, resume: bool) -> dict[str, Any]:
    launcher_dir = _launcher_dir(assignment)
    launcher_dir.mkdir(parents=True, exist_ok=True)
    command, resumed = _workflow_command(plan, assignment, resume)
    environment = _registry_environment(plan.commands)
    workflow_log = _next_log_prefix(launcher_dir, "workflow-resume" if resumed else "workflow")
    completed = subprocess.run(
        command,
        cwd=assignment.repo,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    (launcher_dir / f"{workflow_log}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (launcher_dir / f"{workflow_log}.stderr.log").write_text(completed.stderr, encoding="utf-8")

    run_dir_reported = _stdout_reports_run_dir(completed.stdout, assignment.run_dir, assignment.repo)
    run_manifest_exists = (assignment.run_dir / "run.json").is_file()
    summary = _summary_assessment(assignment)
    expected_exit_code = (
        None if summary.consensus_reached is None else 0 if summary.consensus_reached else 1
    )
    consensus_exit_agree = (
        expected_exit_code is not None and completed.returncode == expected_exit_code
    )
    if not run_dir_reported or not run_manifest_exists or summary.error is not None:
        status = "infrastructure_failed"
    elif summary.consensus_reached and completed.returncode == 0:
        status = "passed"
    else:
        # A valid non-consensus result and every disagreement between the
        # authoritative verdict and process exit need operator attention. Keep
        # the run and its registry sessions intact in all of these cases.
        status = "needs_attention"

    cleanup_exit_code: Optional[int] = None
    if status == "passed" and assignment.cleanup_on_success:
        cleanup_log = _next_log_prefix(launcher_dir, "cleanup")
        cleanup = subprocess.run(
            [plan.commands.workflow, "cleanup", str(assignment.run_dir)],
            cwd=assignment.repo,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        cleanup_exit_code = cleanup.returncode
        (launcher_dir / f"{cleanup_log}.stdout.log").write_text(cleanup.stdout, encoding="utf-8")
        (launcher_dir / f"{cleanup_log}.stderr.log").write_text(cleanup.stderr, encoding="utf-8")
        if cleanup.returncode != 0:
            status = "cleanup_failed"

    reports = sorted(str(path) for path in (assignment.run_dir / "rounds").glob("round-*.md"))
    result = {
        "id": assignment.identifier,
        "repo": str(assignment.repo),
        "run_dir": str(assignment.run_dir),
        "implementor": assignment.implementor,
        "reviewers": list(assignment.reviewers),
        "resumed": resumed,
        "workflow_exit_code": completed.returncode,
        "consensus_reached": summary.consensus_reached,
        "consensus_exit_agree": consensus_exit_agree,
        "summary_failed_steps": summary.failed_steps,
        "summary_unmet_loops": summary.unmet_loops,
        "summary_error": summary.error,
        "run_dir_reported": run_dir_reported,
        "run_manifest_exists": run_manifest_exists,
        "cleanup_exit_code": cleanup_exit_code,
        "status": status,
        "reports": reports,
        "summary": str(summary.path) if summary.path.is_file() else None,
        "launcher_logs": str(launcher_dir),
    }
    (launcher_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _public_plan(plan: LaunchPlan) -> dict[str, Any]:
    return {
        "workflow_cli": plan.commands.workflow,
        "registry_cli": plan.commands.registry,
        "max_parallel_runs": plan.max_parallel_runs,
        "artifact_root": None if plan.artifact_root is None else str(plan.artifact_root),
        "assignments": [
            {
                "id": assignment.identifier,
                "repo": str(assignment.repo),
                "run_dir": str(assignment.run_dir),
                "implementor": assignment.implementor,
                "reviewers": list(assignment.reviewers),
                "max_rounds": assignment.max_rounds,
                "diff": assignment.include_diff,
                "cleanup_on_success": assignment.cleanup_on_success,
            }
            for assignment in plan.assignments
        ],
    }


def _write_parallel_summary(plan: LaunchPlan, results: list[dict[str, Any]]) -> tuple[Path, Path]:
    assert plan.artifact_root is not None
    plan.artifact_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_parallel_runs": plan.max_parallel_runs,
        "passed": sum(result["status"] == "passed" for result in results),
        "needs_attention": sum(result["status"] != "passed" for result in results),
        "results": results,
    }
    json_path = plan.artifact_root / "parallel-summary.json"
    markdown_path = plan.artifact_root / "parallel-summary.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Parallel Hive review summary",
        "",
        f"- Passed: {payload['passed']}",
        f"- Needs attention: {payload['needs_attention']}",
        f"- Maximum concurrent Hive runs: {plan.max_parallel_runs}",
        "",
        "| Assignment | Status | Repository | Hive run |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| `{result['id']}` | `{result['status']}` | `{result['repo']}` | `{result['run_dir']}` |"
        for result in results
    )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def run_plan(plan: LaunchPlan, parallel: bool, resume: bool) -> tuple[list[dict[str, Any]], Optional[tuple[Path, Path]]]:
    if not parallel:
        return [execute_assignment(plan, plan.assignments[0], resume)], None
    with concurrent.futures.ThreadPoolExecutor(max_workers=plan.max_parallel_runs) as executor:
        futures = [executor.submit(execute_assignment, plan, assignment, resume) for assignment in plan.assignments]
        results: list[dict[str, Any]] = []
        for assignment, future in zip(plan.assignments, futures):
            try:
                results.append(future.result())
            except Exception as error:  # Preserve independent runs and report launcher failures.
                results.append(
                    {
                        "id": assignment.identifier,
                        "repo": str(assignment.repo),
                        "run_dir": str(assignment.run_dir),
                        "implementor": assignment.implementor,
                        "reviewers": list(assignment.reviewers),
                        "resumed": resume,
                        "workflow_exit_code": None,
                        "consensus_reached": None,
                        "consensus_exit_agree": False,
                        "summary_failed_steps": None,
                        "summary_unmet_loops": None,
                        "summary_error": None,
                        "run_dir_reported": False,
                        "run_manifest_exists": (assignment.run_dir / "run.json").is_file(),
                        "cleanup_exit_code": None,
                        "status": "launcher_failed",
                        "reports": [],
                        "summary": None,
                        "launcher_logs": str(_launcher_dir(assignment)),
                        "error": str(error),
                    }
                )
    return results, _write_parallel_summary(plan, results)


def parse_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("single", "parallel"))
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(arguments)


def main(arguments: Optional[list[str]] = None) -> int:
    options = parse_args(sys.argv[1:] if arguments is None else arguments)
    try:
        plan = load_single(options.configuration) if options.mode == "single" else load_parallel(options.configuration)
        plan = preflight(plan, resume=options.resume)
        if options.validate_only:
            print(json.dumps(_public_plan(plan), indent=2, sort_keys=True))
            return 0
        results, summary_paths = run_plan(plan, parallel=options.mode == "parallel", resume=options.resume)
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    output: dict[str, Any] = {"results": results}
    if summary_paths is not None:
        output["parallel_summary_json"] = str(summary_paths[0])
        output["parallel_summary_markdown"] = str(summary_paths[1])
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if all(result["status"] == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
