---
name: parallel-code-review-loop
description: "Run multiple independent implementation-and-review pairs concurrently, each using the code-review-loop protocol in its own repository. Use when a caller already has distinct task assignments and repository working paths and wants bounded parallel execution with one persistent reviewer per implementor."
metadata:
  version: "1.0.0"
  argument-hint: "<input-manifest>"
  compatibility: "Requires the sibling code-review-loop skill and an environment that can confirm concurrent worker capacity, deliver live role messages, and launch, monitor, cancel, and await agents. Agent provider and model selection are intentionally unspecified."
---

# Parallel Code Review Loop

Coordinate a set of independent implementor/reviewer pairs. Each pair runs the complete [code-review-loop](../code-review-loop/SKILL.md) protocol in one repository. This skill schedules and monitors pairs; it does not replace or duplicate the single-pair file protocol.

Read the complete sibling `code-review-loop/SKILL.md` before launching any role.

## Scope

Use this skill only when the caller already supplies distinct assignments and repository working paths. It does not:

- decompose an epic into tasks;
- create repositories or worktrees;
- decide which agent provider, model, or runtime implements either role;
- merge, cherry-pick, or otherwise integrate completed repositories; or
- allow multiple active pairs to share one working path.

Agent-provider selection is deliberately outside this version of the contract. Use the launch mechanism available in the execution environment without adding provider assumptions to task context.

## Input contract

Require one general context block and a non-empty assignment list. JSON is the dependency-free canonical file format; the validator also accepts YAML when PyYAML is installed:

~~~json
{
  "general_context": {
    "sources": [
      {"path": "/absolute/path/to/epic.md", "description": "Shared context"}
    ]
  },
  "assignments": [
    {
      "id": "task-a",
      "working_path": "/absolute/path/to/repo-a",
      "agent_context": {"task_source": "/absolute/path/to/repo-a/TASK.md"}
    },
    {
      "id": "task-b",
      "working_path": "/absolute/path/to/repo-b",
      "agent_context": {"task_source": "/absolute/path/to/repo-b/TASK.md"}
    }
  ]
}
~~~

The number of pairs, `N`, is the number of assignments. Do not require a separate count.

For each assignment:

- `id` is a unique stable data identifier used in messages, status, and the final report. Do not use it directly as a provider agent name.
- `working_path` is the absolute repository root and also that pair's code-review-loop coordination directory.
- `agent_context` contains the task-specific objective, constraints, acceptance criteria, relevant base or comparison, evidence sources, validation expectations, and required output. It must include the full task text or identify the exact absolute file or files containing it.

`general_context` contains information every implementor needs, such as the shared product objective, architecture, conventions, constraints, preserved behavior, common evidence, and integration expectations. Context may be inline text or described absolute paths. A directory path alone is not an adequate task source; identify the operative files and what each source contributes.

Do not accept a separate reviewer-context block. The implementor's mandatory channel handoff is the authoritative source of repository, task, evidence, and implementation context for its reviewer.

An optional caller-supplied `max_parallel_pairs` may reduce concurrency. When present, it must be an integer greater than or equal to one. Otherwise derive the limit from confirmed worker capacity.

## Preflight

Before launching agents:

1. Require at least one assignment and unique non-empty assignment IDs.
2. Resolve every working path to its canonical absolute path, following symlinks.
3. Require each path to exist and be a repository root suitable for its task.
4. Reject equal, ancestor, or descendant canonical paths. Parallel pairs must not share any repository subtree, even through aliases, symlinks, or nested repositories.
5. Confirm that no implementor or reviewer from an earlier session is still active in any selected repository. Stale files are handled by implementor startup cleanup; stale live agents are not.
6. Verify that all referenced context sources exist and that each assignment contains enough information for its implementor to produce the base skill's complete reviewer handoff.
7. Confirm that the runtime can route live worker messages to this orchestrator before a worker terminates, correlate them to the sending role, monitor role status, cancel either role, and confirm cancellation termination. Do not use this skill in a runtime that exposes output only after termination.
8. Confirm the number of worker slots concurrently available to launched roles, excluding the orchestrator and other occupants. Do not launch any role when capacity is unknown or fewer than two worker slots are available.
9. Run `python3 "<skill-dir>/scripts/validate_input.py" "<input-manifest>" --confirmed-worker-slots <count>`. Treat any error as a preflight failure. The script validates the machine-checkable input and path invariants and prints the effective pair limit and conservative launch-name candidates.
10. Confirm that the runtime can keep two slots available for every admitted pair. Compute the effective concurrency limit as the minimum of `N`, `max_parallel_pairs` when supplied, and `floor(confirmed_worker_slots / 2)`. Verify the proposed launch names against the provider's syntax and adapt them deterministically if necessary without introducing collisions.

Never fill all available worker slots with implementors that will later wait for reviewers. Capacity is reserved and released by complete pair, not by individual role.

The validator cannot prove that a path is the correct repository for its task, that context is complete, that old agents are absent, or that runtime capability claims are true. The orchestrator remains responsible for those checks.

## Control-plane messages

Keep orchestration messages out of the six repository protocol files. Each role sends one-line `PAIR_EVENT` messages through the runtime's live agent-to-orchestrator channel. The suffix is a JSON object. Validate its assignment ID, role, and canonical path against the launch record; a malformed or mismatched event is a pair failure.

The implementor startup event is:

~~~text
PAIR_EVENT {"event":"startup_clean","assignment_id":"task-a","role":"implementor","working_path":"/absolute/path/to/repo-a"}
~~~

After clean base-protocol completion and before exiting, each role sends:

~~~text
PAIR_EVENT {"event":"terminal_result","assignment_id":"task-a","role":"implementor","working_path":"/absolute/path/to/repo-a","outcome":"completion_acknowledged","review_rounds":2,"last_review_outcome":"NO_FINDINGS","validation_summary":"All documented checks passed"}
PAIR_EVENT {"event":"terminal_result","assignment_id":"task-a","role":"reviewer","working_path":"/absolute/path/to/repo-a","outcome":"completion_acknowledged","review_rounds":2,"last_review_outcome":"NO_FINDINGS","validation_summary":null}
~~~

`review_rounds` is a positive integer counted independently by each role and must agree. `last_review_outcome` must be `NO_FINDINGS` for a clean terminal result. `validation_summary` is a non-empty implementor report of checks and outcomes; it is `null` for the static reviewer.

A role that can report a protocol error before exiting sends this smaller failure event:

~~~text
PAIR_EVENT {"event":"failure","assignment_id":"task-a","role":"reviewer","working_path":"/absolute/path/to/repo-a","failure_kind":"protocol_error","summary":"Invalid frozen snapshot"}
~~~

`failure_kind` and `summary` must be non-empty strings. An absent failure event does not turn an unexpected role exit into success.

## Construct role assignments

### Implementor

Give each implementor:

- its assignment ID, provider-valid launch name, and canonical working path;
- the complete general context;
- only its own agent-specific context;
- the absolute or otherwise unambiguous location of the sibling `code-review-loop` skill;
- instruction to follow that skill as `implementor`, with completion authority omitted so it defaults to `implementor`;
- instruction to treat its working path as both current directory and coordination directory;
- instruction not to spawn or simulate its reviewer;
- instruction to send the structured `startup_clean` event immediately after `startup-cleanup` emits `startup_cleanup_complete`, then continue implementation without waiting for an acknowledgement; and
- instruction to count accepted review rounds and, after `wait-for-completion` emits `completion_acknowledged`, send its structured terminal result before exiting.

The implementor must combine the general and assignment-specific contexts into the mandatory self-contained channel handoff. It may point the reviewer to large sources by exact absolute path as permitted by the base skill.

### Reviewer

Give each reviewer only:

- its assignment ID, provider-valid launch name, and canonical working path;
- the location of the sibling `code-review-loop` skill;
- instruction to follow that skill simply as `reviewer`; reviewers have no completion-authority input;
- instruction to treat its working path as both current directory and coordination directory;
- instruction to learn all repository, task, evidence, and review-target context from the `wait-for-request` JSON `message` rather than guessing, inspecting protocol files, or reviewing before a request; and
- instruction to count accepted review rounds and, after `acknowledge-completion` succeeds, send its structured terminal result before exiting.

Do not duplicate general or agent-specific task context in the reviewer launch prompt. This prevents the launch prompt and protocol handoff from becoming two conflicting sources of truth.

Derive unique provider-valid launch names independently from assignment IDs. Prefer deterministic ordinal names such as `pair_001_implementor` and `pair_001_reviewer`, adapted only when the runtime has different syntax constraints. Record the assignment-ID-to-launch-name mapping. Sanitizing the caller's IDs directly is insufficient because distinct IDs can collapse to the same provider name.

## Schedule pairs

Maintain one state per assignment:

~~~text
QUEUED -> IMPLEMENTOR_STARTED -> STARTUP_CLEAN -> PAIR_RUNNING -> COMPLETING -> COMPLETED
                `------------------------- any failure ----------------> CANCELLING -> FAILED
~~~

For each admitted wave:

1. Reserve two worker slots per admitted assignment.
2. Launch the admitted implementors in parallel in their respective working paths.
3. Wait for and validate each implementor's structured `startup_clean` event. Do not infer readiness from elapsed time or repository files.
4. Launch that assignment's reviewer as soon as its notification arrives. Reviewers for different ready pairs may launch in parallel.
5. Leave both roles to execute the base skill until its implementor-owned completion handshake terminates them. Collect and validate both structured terminal results.
6. Release a pair's two-slot reservation only after every role launched for it has terminated, including a counterpart canceled after failure. Then admit queued assignments up to the concurrency limit.

The base skill's per-pair ordering remains mandatory: old roles stopped, implementor launched, implementor startup cleanup completed, then reviewer launched. Do not launch all reviewers first or launch both roles in one unordered batch.

## Monitor and finish

Use the environment's agent-status or wait mechanism rather than polling protocol files. Continue until every assignment is `COMPLETED` or `FAILED` and every launched role has terminated.

A pair is `COMPLETED` only when:

- its implementor sends a valid terminal result reporting the base skill's `completion_acknowledged` outcome and exits successfully;
- its reviewer sends a matching valid terminal result reporting successful completion acknowledgement and exits successfully;
- the two results agree on assignment, canonical path, review-round count, and final `NO_FINDINGS` outcome;
- one final read-only check finds none of the six code-review-loop protocol paths in the working path.

If a role exits unexpectedly, reports a protocol error, sends an invalid control-plane event, fails to launch, or cannot complete its handshake, transition the pair to `CANCELLING`. Immediately cancel any surviving counterpart through the runtime control plane and wait until every launched role in that pair has terminated. Do not ask the survivor to repair or clean the failed session. Then mark the pair `FAILED` and release its reserved slots.

Preserve the failed pair's repository and all remaining protocol files for diagnosis; cancellation is an agent-lifecycle action, not permission to delete files. Do not silently replace or restart a failed role. If cancellation cannot be confirmed, report an orchestration failure and do not claim the wrapper has terminated cleanly. Independent pairs may continue when capacity remains. Do not report aggregate success while any pair failed.

## Final report

Report:

- shared general-context sources;
- requested pair count, peak concurrent pair count, and whether waves were required;
- for every assignment: ID, canonical working path, implementor result, reviewer result, review-round outcome, validation summary, and terminal status;
- any failed or unlaunched assignment and its preserved diagnostic state; and
- that repository integration was not performed unless separately requested and authorized.

## Example activations

- "Run these five independent repositories through implementation and static review in parallel."
- "Apply the shared migration context to every task, give each worker its own task context, and wait for all review pairs to finish."
- "Run as many implementation-review pairs as capacity permits and queue the rest."
