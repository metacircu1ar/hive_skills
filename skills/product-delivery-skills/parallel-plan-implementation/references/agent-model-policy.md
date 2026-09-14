# Agent Model and Reasoning Policy

## Purpose

This policy fixes the requested execution profiles for orchestration, implementation, and review, while preventing a skill from claiming that a host selected a model it did not actually select.

## Required requested profiles

| Role | Requested model | Requested reasoning effort | Responsibilities |
|---|---|---|---|
| Main agent | `gpt-5.6-sol` | `ultra` | contract ownership, orchestration, integration, finding adjudication, fixes, history reconstruction, and final validation |
| Implementor agent | `gpt-5.6-terra` | `xhigh` | one bounded product phase in one isolated worktree |
| Reviewer agent | `gpt-5.6-sol` | `xhigh` | read-only review of one phase commit with complete phase context |

Preserve these requested values in generated prompts and manifests unless the user explicitly changes them.

## Host-dependent selection

A Markdown skill cannot change the model already running the main agent, guarantee that a selector exists, or prove the actual runtime profile when the host does not expose it.

Before implementation execution:

1. request the main and implementor profiles through the host's supported mechanism;
2. record each role as `confirmed`, `host-unverifiable`, `unavailable`, or `substituted`;
3. record the actual model and reasoning effort when the host exposes them;
4. never silently map a requested profile to another model or effort level;
5. obtain explicit user approval before a substitution;
6. record the approved substitute and reason in the execution manifest and implementation ledger.

Before parallel review, repeat the check for the reviewer profile. Record `unavailable` and block review when the requested profile cannot be provisioned and no approved substitute exists.

## Required profile object

Use this shape wherever a profile is recorded:

```json
{
  "requested_model": "gpt-5.6-sol",
  "requested_reasoning_effort": "ultra",
  "actual_model": "gpt-5.6-sol",
  "actual_reasoning_effort": "ultra",
  "selection_status": "confirmed",
  "substitution_approved": false,
  "notes": []
}
```

Allowed `selection_status` values are:

- `confirmed`: the host exposed and selected the requested profile;
- `host-unverifiable`: the host accepted the request but does not expose enough identity information to prove it;
- `unavailable`: the requested profile cannot be provisioned;
- `substituted`: another profile was selected after explicit user approval.

A role may execute only when it is `confirmed`, or when it is `host-unverifiable` or `substituted` with an explicit user-approved exception recorded. An `unavailable` role blocks that stage.

## Main-agent limitation

The skill is executed by the current main agent. When that agent is not already running with `gpt-5.6-sol` at `ultra` and the host cannot transfer orchestration to that profile, disclose the mismatch before code execution. Do not claim to be the requested model.

## Implementor dispatch

Every implementor task must include:

- requested and actual model and effort;
- exact phase and component IDs;
- branch, worktree, and launch-baseline commit;
- exact plan and boundary sections;
- canonical contracts and repository rules;
- owned, read-only, shared, generated, and forbidden paths;
- validation commands and required result shape;
- blocker behavior when the requested profile or required context is unavailable.

The phase result records the actual profile used.

## Reviewer dispatch

Every reviewer task must include:

- requested model `gpt-5.6-sol`;
- requested reasoning effort `xhigh`;
- exact phase, target commit, selected parent, and frozen final review baseline;
- the complete phase-specific context packet;
- the `phase-commit-reviewer` skill and output schema;
- a strict read-only requirement.

Reviewer freshness means one newly created isolated agent context per phase commit. Reusing one reviewer sequentially across commits does not satisfy the workflow.

## No false precision

When the host reports only a broad model family, record the exposed value and `host-unverifiable`; do not invent a more specific actual selector. Requested settings remain visible even when the host cannot prove them.
