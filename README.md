<h1 align="center">hive_skills</h1>

A personal collection of agent skills, workflow references, multi-agent coordination protocols, delivery playbooks, and focused audit checklists for AI coding agents.

## Contents

### Top-level workflow skills and references

These entries under [`skills/`](skills/) capture reusable agent workflows and review passes. Standalone references are Markdown files; installable skills use a directory containing `SKILL.md`.

| Skill or reference | Purpose |
| --- | --- |
| [`advisor`](skills/advisor-skill.md) | Configure a smaller Claude model to consult a stronger advisor model at difficult decision points. |
| [`batch`](skills/batch-skill.md) | Plan and execute wide, independently mergeable changes through parallel worktree agents and separate pull requests. |
| [`code-review`](skills/code-review-skill.md) | Review a diff, verify findings, and fix in place by default, or propose changes in read-only mode; optional finder/verifier worker counts and pull-request comments. |
| [`deep-research`](skills/deep-research-skill.md) | Produce a cited report through parallel searches, source extraction, and adversarial claim verification. |
| [`error-logging-review`](skills/error-logging-review/SKILL.md) | Trace error checking, handling, and logging; check useful non-error events, diagnostic context, sensitive data exposure, and log noise. Supports finder/verifier counts and both delivery modes. |
| [`goal`](skills/goal-skill.md) | Keep an agent working until an evidence-backed completion condition is judged to be satisfied. |
| [`init-verifiers`](skills/init-verifiers-skill.md) | Generate project-specific functional verifier skills for browser, CLI, and HTTP behavior. |
| [`input-contract-hardening`](skills/input-contract-hardening/SKILL.md) | Inventory every caller-input boundary (CLI, files/pipes, config, socket/RPC, MCP/tool arguments, generated command lines), then enforce its contract before side effects with typed, private-safe diagnostics (field, expected form, working example) that agree across surfaces. Hunts silent fallbacks, ignored options, lenient decoders, schema drift and blocking special files; requires ordering, privacy and unfiltered-suite evidence. Supports finder/verifier counts and both delivery modes. |
| [`microskills-review-generator`](skills/microskills/microskills-review-generator/SKILL.md) | Study a codebase's stack and architecture and generate as many narrow, project-specific review checklists as the evidence supports, one `SKILL.md` per microskill, into a chosen directory. It reports their location and never runs them. |
| [`microskills-review-runner`](skills/microskills/microskills-review-runner/SKILL.md) | Run a directory of microskills as independent exhaustive micropasses in parallel, with `--finders N` (default 0: sequential, no agents) capped at the host's concurrent-agent limit, and optional verifiers, then merge them into one deduplicated, verified list of fixes. Supports both delivery modes. |
| [`perf-optimization`](skills/perf-optimization/SKILL.md) | Locate bottlenecks with release-build CPU/wall accounting, bounded instrumentation and profiling, then prove each change with frozen-binary paired experiments under predeclared gates without weakening correctness or durability. Supports finder/verifier counts and both delivery modes. |
| [`professional-localization`](skills/professional-localization-skill.md) | Design localization as an end-to-end product boundary spanning UI, server, storage, contracts, and CI. |
| [`simplify`](skills/simplify-skill.md) | Improve reuse, simplicity, efficiency, and abstraction in place by default, or propose changes in read-only mode; optional review-worker count. |
| [`test-quality-review`](skills/test-quality-review/SKILL.md) | Review assertion strength, risk coverage, test doubles, reliability, isolation, and CI execution across languages and frameworks. Supports finder/verifier counts and both delivery modes. |
| [`testable-frontend`](skills/testable-frontend-skill.md) | Structure frontend code and test tiers so deterministic automated testing is practical by construction. |

`code-review`, `simplify`, `error-logging-review`, `test-quality-review`,
`input-contract-hardening`, and `perf-optimization` default to zero workers and `--delivery-mode in-place`. Use
`--delivery-mode read-only` to receive proposed modifications in prose or code
snippets without changing repository files.

Microskills split review into narrow, exhaustive passes. `/microskills-review-generator` writes
project-specific checklists, by default into `.microskills/` or into `--output DIR`.
`/microskills-review-runner --skills DIR` then runs one micropass per microskill. By
default it runs them itself, one at a time. `--finders N` runs up to `N` fresh finder
agents at once, capped at the host's concurrent-agent limit. It then merges the
results, and `--verifiers M` adds independent agents to re-check them:

```text
/microskills-review-generator --output /reviews/my-repo-microskills .
/microskills-review-runner --skills /reviews/my-repo-microskills --finders 12 --verifiers 2 .
```

### Agent coordination skills

The repository contains both lightweight file-protocol coordination skills and
Hive-backed skills that use named registry implementors, parallel reviewer
panels, durable workflow artifacts, and bounded multi-repository execution.

| Skill | Purpose |
| --- | --- |
| [`code-review-loop`](skills/code-review-loop/SKILL.md) | Share one dispatcher across implementation/static-review rounds. Use a fresh reviewer session per round by default, or resume the same conversation with `session-mode=reuse`. Workers finish each turn; scripts handle coordination, closure, and revival. |
| [`parallel-code-review-loop`](skills/parallel-code-review-loop/SKILL.md) | Start one dispatcher and multiple implementors with shared and task-specific context, supplied repository paths, and one coordination directory. See the [one-workspace, N-repository example](skills/parallel-code-review-loop/README.md). |
| [`hive-review-loop`](skills/hive-review-loop/SKILL.md) | Run one repository through a named `hive_registry` implementor and a configurable parallel reviewer panel using `hive_workflow`; it launches no Codex subagents. |
| [`hive-parallel-review-loop`](skills/hive-parallel-review-loop/SKILL.md) | Run multiple disjoint repository review loops as bounded concurrent `hive_workflow` processes, with shared defaults and per-assignment registry-agent overrides in YAML. |

Start a dispatcher, then invoke implementors for their tasks in the same coordination directory:

```text
/code-review-loop reviewer coord=/workspace
/code-review-loop implementor coord=/workspace
```

The dispatcher creates all reviewer workers; implementors never launch reviewers. Implementors default to `session-mode=fresh`: close the session after every result, including findings, and open a new one for the next round. Use `session-mode=reuse` to keep the same reviewer conversation, resumed by the dispatcher only when work arrives. Return to a session with `session=<id>`. Omitted completion authority defaults to `implementor`; `completion-authority=caller` lets an enclosing workflow decide when work ends, while fresh sessions still close after each review. All coordination-file access uses supplied scripts. Workers end each turn; implementors and the dispatcher prefer silent background waits with completion notifications. Every dispatcher start recovers open sessions without waking idle workers; use `revive` after an unclean stop or to restore dispatch in an existing conversation.

For multiple assignments, invoke `parallel-code-review-loop` with a manifest containing `coordination_dir`, shared context, and per-task repository paths and context. Optional `session_mode` defaults to `fresh`. The wrapper starts one dispatcher and the implementors, then verifies each implementor's result and closure of all its sessions. It imposes no pair limit or source-path separation checks. Install both complete skill directories because the wrapper depends on the base scripts.

After participants finish their result and closure checks, `dispatcher_loop.py cleanup-closed --coordination-dir /workspace` deletes closed sessions and their artifacts to keep them out of future scans. Open sessions remain; cleanup is explicit and keeps no archive.

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
skills/error-logging-review/
skills/test-quality-review/
skills/microskills/<skill-name>/
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
skills/error-logging-review/     Focused error-handling and logging review pass
skills/test-quality-review/      Language- and framework-independent test-quality pass
skills/microskills/              Microskill generator and parallel review runner
skills/code-review-loop/         Shared dispatcher and persistent review sessions
skills/code-review-loop/verification/  Bounded session/dispatcher TLA+ checks
skills/parallel-code-review-loop/  Multiple assignments using one review dispatcher
skills/hive-review-loop/       Hive-backed implementation and reviewer-panel loop
skills/hive-parallel-review-loop/  Bounded multi-repository Hive workflow launcher
skills/verified-commit-split/    Content-preserving Git commit-splitting skill
skills/audit/                    Focused audit skills
skills/product-delivery-skills/  Self-contained product-delivery skills
LICENSE                          MIT license
```
