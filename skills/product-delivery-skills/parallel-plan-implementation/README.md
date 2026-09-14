# Parallel Plan Implementation

A companion Agent Skill for `product-implementation-planner`.

It converts validated full-product or bounded-change phases into frozen contracts and boundaries, executes safe dependency waves with isolated implementor agents and Git worktrees, integrates one traceable commit per authorized phase, verifies the complete repository for regressions without expanding scope, and then offers an optional parallel review of every phase commit. When review is approved, fresh read-only reviewer agents return structured findings; the main agent verifies them, adds fixes and practical regression tests to the responsible phase commits, safely replays descendants, and restores a passing final state.

## Embedded complete-description comment

The source `SKILL.md` begins with a `COMPLETE SKILL DESCRIPTION` HTML comment covering contract and boundary generation, safe parallel worktree execution, ordered per-phase integration, the separate review approval gate, fresh phase reviewers, main-agent adjudication, controlled history reconstruction, regression tests, and final green-state completion. The shorter YAML `description` remains optimized for skill discovery and activation.

## Requested profiles

- Main agent: `gpt-5.6-sol`, reasoning effort `ultra`
- Implementor agents: `gpt-5.6-terra`, reasoning effort `xhigh`
- Reviewer agents: `gpt-5.6-sol`, reasoning effort `xhigh`

Model selection is host-dependent. Requested and actual profiles are recorded, and substitutions require explicit user approval.

## Companion skills

- Planning: `product-implementation-planner`
- Commit review: `phase-commit-reviewer`

The review stage must not imitate a reduced reviewer when `phase-commit-reviewer` is missing.

## Core guarantees

- contract-first boundaries rather than prose-only coordination;
- one canonical plan scope, schema-v2 execution authority, and unique scope blocks in immutable worker/reviewer packets;
- one immutable decomposition assessment whose data ownership is checked against actual unit write paths;
- one concise derived `delivery-status.md` updated and announced by the main orchestrator after implementation and review;
- one worktree and one fresh implementor per eligible phase;
- dependency-aware waves and explicit shared-path ownership;
- one reviewable logical integration commit per phase;
- a green repository before the review question is asked;
- one fresh read-only reviewer per phase commit after separate approval;
- complete plan, boundary, contract, repository, and final-state context for every reviewer;
- main-agent verification of all findings;
- one controlled history reconstruction from the earliest affected phase;
- regression tests for confirmed issues when practical;
- backup refs, no silent force-push, and final full-suite validation.

## Generated implementation artifacts

The planner-created `docs/implementation-plan/delivery-status.md` remains the cross-stage human view and links into the detailed packages below. It is not an execution authority.

```text
docs/implementation-plan/parallel-implementation/
├── README.md
├── execution-manifest.json
├── dependency-graph.md
├── contract-baseline.md
├── integration-order.md
├── implementation-ledger.md
├── boundaries/
└── worker-prompts/
```

When parallel review is approved:

```text
docs/implementation-plan/parallel-implementation/parallel-review/
├── README.md
├── review-manifest.json
├── review-ledger.md
├── commit-map.md
├── findings/
└── reviewer-prompts/
```

## Validation

```bash
python3 <skill-root>/scripts/validate_parallel_plan.py <repository-root>
python3 <skill-root>/scripts/validate_parallel_review.py <repository-root>
```

The first validator checks boundaries, contracts, waves, decomposition and data ownership, reserved orchestrator paths, profile records, and phase mappings. The second checks review authorization, reviewer prompts/results, original and rewritten commit maps, finding dispositions, backup/rewrite safety, and final validation evidence.
