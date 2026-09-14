<div align="center">
  <img src="logo.png" alt="hive_skills logo" width="480">
</div>

<h1 align="center">hive_skills</h1>

A personal collection of agent skills, workflow references, multi-agent coordination protocols, delivery playbooks, and focused audit checklists for AI coding agents.

## Contents

### Top-level workflow skills and references

The standalone Markdown files directly under [`skills/`](skills/) capture reusable agent workflows and extracted runtime behavior:

| Skill or reference | Purpose |
| --- | --- |
| [`advisor`](skills/advisor-skill.md) | Configure a smaller Claude model to consult a stronger advisor model at difficult decision points. |
| [`batch`](skills/batch-skill.md) | Plan and execute wide, independently mergeable changes through parallel worktree agents and separate pull requests. |
| [`code-review`](skills/code-review-skill.md) | Review a diff, verify findings, and fix in place by default, or propose changes in read-only mode; optional finder/verifier worker counts and pull-request comments. |
| [`deep-research`](skills/deep-research-skill.md) | Produce a cited report through parallel searches, source extraction, and adversarial claim verification. |
| [`goal`](skills/goal-skill.md) | Keep an agent working until an evidence-backed completion condition is judged to be satisfied. |
| [`init-verifiers`](skills/init-verifiers-skill.md) | Generate project-specific functional verifier skills for browser, CLI, and HTTP behavior. |
| [`professional-localization`](skills/professional-localization-skill.md) | Design localization as an end-to-end product boundary spanning UI, server, storage, contracts, and CI. |
| [`simplify`](skills/simplify-skill.md) | Improve reuse, simplicity, efficiency, and abstraction in place by default, or propose changes in read-only mode; optional review-worker count. |
| [`testable-frontend`](skills/testable-frontend-skill.md) | Structure frontend code and test tiers so deterministic automated testing is practical by construction. |

Both `code-review` and `simplify` default to zero workers and
`--delivery-mode in-place`. Use `--delivery-mode read-only` to receive proposed
modifications in prose or code snippets without changing repository files.

### Agent coordination skills

The repository contains both lightweight file-protocol coordination skills and
Hive-backed skills that use named registry implementors, parallel reviewer
panels, durable workflow artifacts, and bounded multi-repository execution.

| Skill | Purpose |
| --- | --- |
| [`code-review-loop`](skills/code-review-loop/SKILL.md) | Coordinate an `implementor` and persistent `reviewer` through session-isolated frozen-diff cycles, `NO_FINDINGS` work-item boundaries, and caller- or implementor-controlled session completion; the protocol includes [TLA+ state-machine verification](skills/code-review-loop/verification/README.md). |
| [`parallel-code-review-loop`](skills/parallel-code-review-loop/SKILL.md) | Schedule multiple independent `code-review-loop` pairs across distinct repository working paths, pass shared and assignment-specific context to implementors, enforce per-pair startup order, and wait for all pairs to terminate. See the [one-workspace, N-repository example](skills/parallel-code-review-loop/README.md). |
| [`hive-review-loop`](skills/hive-review-loop/SKILL.md) | Run one repository through a named `hive_registry` implementor and a configurable parallel reviewer panel using `hive_workflow`; it launches no Codex subagents. |
| [`hive-parallel-review-loop`](skills/hive-parallel-review-loop/SKILL.md) | Run multiple disjoint repository review loops as bounded concurrent `hive_workflow` processes, with shared defaults and per-assignment registry-agent overrides in YAML. |

For one pair, invoke `code-review-loop` on both agents with the appropriate role:

```text
/code-review-loop implementor
/code-review-loop reviewer
```

Omitting completion authority on the implementor defaults it to `completion-authority=implementor`. The reviewer has no completion-authority input. Use `completion-authority=caller` only on the implementor when an enclosing workflow, such as an epic implementor, must keep the reviewer alive across multiple work items and close the session itself. Continue such a session by resuming the same initialized implementor role; a fresh implementor invocation would perform startup cleanup and must begin a new session instead.

For multiple independent repositories, invoke `parallel-code-review-loop` on one orchestrator with its input manifest. The orchestrator validates disjoint repository roots and complete-pair capacity, then launches one `code-review-loop` implementor/reviewer pair per repository. Install the complete directories for both coordination skills because the parallel wrapper depends on the base protocol and its scripts.

For provider-neutral agent panels, use the Hive-backed variants. They call
[`hive_registry`](https://github.com/metacircu1ar/hive_registry) and
[`hive_workflow`](https://github.com/metacircu1ar/hive_workflow) directly and
never create Codex subagents.
`hive-review-loop` runs one registry implementor with one or more parallel
registry reviewers; `hive-parallel-review-loop` runs that topology across
multiple repositories from one YAML manifest.

### Git history skills

| Skill | Purpose |
| --- | --- |
| [`verified-commit-split`](skills/verified-commit-split/SKILL.md) | Split uncommitted work, one commit, or a contiguous commit range into logical commits while proving final tree identity against a protected backup. |

### Product delivery skills

[`skills/product-delivery-skills/`](skills/product-delivery-skills/) contains four self-contained, installable skills:

| Skill | Purpose |
| --- | --- |
| [`product-implementation-planner`](skills/product-delivery-skills/product-implementation-planner/SKILL.md) | Turn a product description and repository evidence into a phased implementation plan. |
| [`product-plan-compiler`](skills/product-delivery-skills/product-plan-compiler/SKILL.md) | Compile a detailed product plan into formal models, run relevant provers and model checkers, and refine inconsistencies before implementation. |
| [`parallel-plan-implementation`](skills/product-delivery-skills/parallel-plan-implementation/SKILL.md) | Implement an approved plan through controlled, dependency-aware parallel phases. |
| [`phase-commit-reviewer`](skills/product-delivery-skills/phase-commit-reviewer/SKILL.md) | Perform a read-only, phase-aware review of one implementation commit. |

The default delivery sequence is `product-implementation-planner` → `product-plan-compiler` → `parallel-plan-implementation` → `phase-commit-reviewer`.

Across that sequence, the main stage orchestrator maintains `docs/implementation-plan/delivery-status.md` as a concise, derived human view of scope, stage outcomes, decisions, blockers, and evidence links. It remains non-authoritative, and the operator is explicitly told its path and any required action after planning, formal verification, implementation, and optional review.

Each product-delivery skill includes its supporting references, templates, schemas, scripts, and a dedicated README.

### Audit skills

[`skills/audit/`](skills/audit/) contains focused audit playbooks. Each one is intended to produce concrete findings with file paths, line numbers, impact, and suggested fixes.

| Skill | Purpose |
| --- | --- |
| [`audit-input-validation`](skills/audit/audit-input-validation/SKILL.md) | Audit client and server validation for user-controlled input. |
| [`audit-auth-and-access-control`](skills/audit/audit-auth-and-access-control/SKILL.md) | Audit auth flows, sessions, roles, admin routes, and cross-user data isolation. |
| [`audit-secrets-and-config`](skills/audit/audit-secrets-and-config/SKILL.md) | Audit hardcoded secrets, environment validation, and webhook signatures. |
| [`audit-rate-limiting`](skills/audit/audit-rate-limiting/SKILL.md) | Audit API-route rate-limit coverage and policy fit. |
| [`audit-cors`](skills/audit/audit-cors/SKILL.md) | Audit CORS configuration and origin allowlists. |
| [`audit-database-performance`](skills/audit/audit-database-performance/SKILL.md) | Audit indexes, pagination, unbounded queries, and connection-pool risks. |
| [`audit-resilience-and-observability`](skills/audit/audit-resilience-and-observability/SKILL.md) | Audit error boundaries, external I/O, health checks, logs, and backups. |
| [`audit-asset-pipeline`](skills/audit/audit-asset-pipeline/SKILL.md) | Audit uploads, storage, CDN/object storage, and asset delivery. |
| [`audit-type-safety`](skills/audit/audit-type-safety/SKILL.md) | Audit TypeScript safety bypasses and unchecked external data. |
| [`security-review`](skills/audit/security-review/SKILL.md) | Run an umbrella security review composed from focused web skills. |
| [`ios-prelaunch-checklist`](skills/audit/ios-prelaunch-checklist/SKILL.md) | Audit iOS App Store assets, technical setup, legal readiness, and signing. |

## Use

Clone the repository and copy the skill or reference you need into the directory expected by your agent runtime:

```text
skills/<standalone-workflow>-skill.md
skills/code-review-loop/
skills/parallel-code-review-loop/
skills/hive-review-loop/
skills/hive-parallel-review-loop/
skills/verified-commit-split/
skills/product-delivery-skills/<skill-name>/
skills/audit/<skill-name>/
```

## Repository layout

```text
skills/*-skill.md               Standalone workflow skills and references
skills/code-review-loop/         Two-agent implementation/review coordination skill
skills/code-review-loop/verification/  TLA+ model, checks, and reproducibility notes
skills/parallel-code-review-loop/  Multi-repository orchestration over isolated review pairs
skills/hive-review-loop/       Hive-backed implementation and reviewer-panel loop
skills/hive-parallel-review-loop/  Bounded multi-repository Hive workflow launcher
skills/verified-commit-split/    Content-preserving Git commit-splitting skill
skills/audit/                    Focused audit skills
skills/product-delivery-skills/  Self-contained product-delivery skills
LICENSE                          MIT license
```
