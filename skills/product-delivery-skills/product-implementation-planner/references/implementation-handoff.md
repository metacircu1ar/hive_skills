# Implementation Handoff

## Purpose

This reference defines the permitted transition from planning to implementation and preserves a separate authorization gate for optional phase-commit review.

## Preconditions

Offer implementation only after:

- all planning documents have been written;
- the planning validator passes without errors;
- planning status and the canonical `planned_phase_ids` / `authorized_phase_ids` registries are explicit and validated;
- stable component IDs, phase IDs, dependency edges, boundary candidates, and parallelization constraints exist;
- the canonical decomposition assessment passes scenario, subsystem-classification, and data-owner validation;
- `delivery-status.md` records the planning outcome, evidence links, and current operator action without redefining canonical scope;
- blocking decisions are either resolved or exclude all phases being offered.

## Required implementation question

When one or more phases are authorized, ask:

> The implementation plan is complete for the approved scope. Should I proceed with implementation using the `parallel-plan-implementation` skill?

The user must explicitly approve implementation. Do not soften this into automatic execution.

## Handoff payload

Pass the companion skill:

- absolute repository root;
- planning root, `docs/implementation-plan/`;
- human delivery-status path, `docs/implementation-plan/delivery-status.md`, as a derived navigation aid rather than an authority;
- planning-set status;
- exact authorized component-phase IDs;
- unresolved `DEC-###` gates and phases they block;
- source branch and current Git commit;
- repository cleanliness state;
- planner-validator result;
- candidate parallel waves and mandatory serialization constraints;
- the immutable `93-implementation-units.md` decomposition assessment and its data-writer registry;
- user-specified implementation scope or parallelism limit;
- requested execution profiles.

The companion skill must re-read the planning files rather than relying only on a summary.

## Requested profiles

The requested delivery profiles are:

- main agent: `gpt-5.6-sol`, reasoning effort `ultra`;
- implementor agents: `gpt-5.6-terra`, reasoning effort `xhigh`;
- reviewer agents: `gpt-5.6-sol`, reasoning effort `xhigh`.

Model selection is host-dependent. The companion records requested and actual values and obtains explicit user approval before substitution. The planner does not claim that the current main agent can retroactively change its model.

## Skill activation and portability

Agent Skills are instructions and resources; skill activation and subagent execution are supplied by the host.

1. Activate `parallel-plan-implementation` through the host's supported mechanism when installed.
2. If skill activation is file-based, load its `SKILL.md` explicitly.
3. If it is missing, do not imitate partial implementation behavior under the planning skill.
4. If the host lacks parallel subagents or isolated worktrees, the companion may prepare boundaries and an execution manifest but must not claim parallel execution. A sequential fallback requires separate explicit authorization.
5. The optional review stage requires the separately installed `phase-commit-reviewer` skill and fresh isolated reviewer contexts.

## Separate review authorization

Implementation authorization does **not** authorize phase-commit review, finding-driven fixes, or history reconstruction.

After all approved implementation is integrated and the repository is clean, buildable, and passing, the implementation companion asks:

> Implementation and integration are complete for the approved scope, and the project is buildable and passing. Should I run a parallel review of every phase commit?

Only an affirmative answer authorizes reviewer dispatch and local phase-history reconstruction. It does not authorize remote force-push, production deployment, or another irreversible action.

## Blocked planning sets

If no phase is authorized, do not offer implementation. State the blocking IDs and ask whether the user wants them resolved. After amendment and validation, offer implementation again.

## No duplicate confirmation

The user's affirmative answer to the planning skill is implementation authorization. The companion performs technical preflight but does not ask another generic implementation question. It may ask a genuinely product-changing clarification when plans and boundaries cannot resolve it safely. The later review question is intentionally separate because it authorizes a different, history-modifying stage.
