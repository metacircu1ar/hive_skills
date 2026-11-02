---
name: parallel-code-review-loop
description: "Run multiple implementation/static-review conversations through one shared code-review-loop dispatcher. Use when the caller supplies shared context, task-specific context, and repository paths."
metadata:
  argument-hint: "<input-manifest>"
  compatibility: "Requires the sibling code-review-loop skill and a runtime that can launch agents asynchronously, deliver completion notifications while listening, and inspect/stop agents; conversation reuse needs runtime resume support."
---

# Parallel Code Review Loop

Start one dispatcher and multiple implementors. The dispatcher creates every reviewer
worker. Each pair communicates directly through its own session in the shared
coordination directory. This wrapper supplies context and tracks task completion.

Read the complete sibling [code-review-loop skill](../code-review-loop/SKILL.md) before
launching. Its script-only access, silent waiting, static review, and lifecycle rules
apply here. The wrapper never reads, monitors, edits, or removes coordination files
directly; it uses the base scripts' JSON output.

## Inputs

Require an absolute `coordination_dir`, shared `general_context`, and a non-empty
`assignments` list. JSON needs only Python's standard library; YAML requires PyYAML.
Optional `session_mode` is `fresh` (default, preferred) or `reuse`; pass it to every
implementor as `session-mode=<value>`. Fresh mode closes each review session after its
result, including findings. Reuse mode resumes the same reviewer for later rounds.

~~~json
{
  "coordination_dir": "/workspace",
  "session_mode": "fresh",
  "general_context": {"task_source": "/workspace/EPIC.md"},
  "assignments": [
    {
      "id": "task-a",
      "working_path": "/workspace/repo-a",
      "agent_context": {"task_source": "/workspace/repo-a/TASK.md"}
    },
    {
      "id": "task-b",
      "working_path": "/workspace/repo-b",
      "agent_context": {"task": "Implement the requested change in repository B."}
    }
  ]
}
~~~

Each assignment has a unique stable `id`, an absolute repository `working_path`,
and non-empty `agent_context`. The working path is only a source path. All roles
coordinate in `coordination_dir`, regardless of repository location.

Shared and task context must together supply the full task text or exact absolute
task-file paths, constraints, review target, evidence sources, validation expectations,
and required output. A directory alone is not a task description. Do not supply a
second reviewer-context copy; the implementor's channel handoff carries that context.

This wrapper does not decompose tasks, arrange source directories, compare paths across
assignments, or integrate completed changes. No worker-slot input, pair limit, fixed pool,
or wave scheduling is supported. Runtime failures are reported per affected assignment.

## Validate and launch

1. Run `python3 "<skill-dir>/scripts/validate_input.py" "<input-manifest>"`.
   Resolve errors before launching. The script validates inputs and individual directory
   paths and returns normalized paths and implementor launch names.
2. Establish that the runtime can launch agents without waiting for their final answers,
   deliver live role messages and worker-completion notifications while listening,
   and inspect/stop agents and their processes. Establish conversation resume support. The
   dispatcher must be able to create its own reviewer children. No numeric slot gate applies.
3. If the caller supplied a running dispatcher for this coordination directory, use it.
   Otherwise launch one agent with the base skill as `reviewer`, the coordination directory,
   and any supplied reviewer model/runtime settings. That agent performs startup recovery.
   If an unclean-start marker requires `revive`, report that requirement; do not assume
   another dispatcher was stopped. Record whether this wrapper owns the dispatcher.
4. Launch the implementors for all assignments. Give each its assignment ID, the complete
   shared context, only its task context, its repository path, the coordination directory,
   the normalized session mode, and the base skill's absolute location. Invoke `implementor` with default completion
   authority. Explicitly prohibit spawning its own reviewer.
5. Tell each implementor to report every session ID immediately after `open-session`,
   then continue its task. Keep all IDs per assignment, not just the latest. There is
   no cleanup event or acknowledgement gate.

The wrapper launches no reviewer workers. They belong to the dispatcher, which gets
the review task through the session request. Use provider-valid unique launch names;
assignment IDs are report data rather than raw agent names.

## Progress and completion

Implementors send live control messages to the wrapper through the runtime, not
through protocol files. Use these two event shapes:

~~~text
PAIR_EVENT {"event":"session_opened","assignment_id":"task-a","session_id":"<id>"}
PAIR_EVENT {"event":"terminal_result","assignment_id":"task-a","session_id":"<id>","outcome":"completed","review_rounds":2,"last_review_outcome":"NO_FINDINGS","validation_summary":"Relevant checks passed"}
~~~

A failure message carries `event: "failure"`, the assignment ID, its session ID when
known, and a concrete `summary`. Correlate messages with the sending implementor.
Record session IDs as soon as they arrive, so failures can be closed. In fresh mode,
each round emits another `session_opened`; the terminal result names the final session
and counts review rounds across all of that assignment's sessions.
Reserve failure events for assignments that must stop; report nonterminal diagnostics
separately rather than labeling them as task failures.

An assignment completes successfully only when:

- its implementor sends a valid terminal result and exits successfully;
- the result names the latest recorded session, reports at least one review round,
  `NO_FINDINGS`, and the task's required checks; and
- `implementor_loop.py status --coordination-dir <dir> --session <id>` reports
  `session_status: "closed"` for every session recorded for that assignment.

Reviewers send the wrapper no terminal result. Closure is confirmed by the dispatcher;
channel files are retained, so file absence is not a completion check. Read state only
through the helper. Agent exit alone never implies a clean review.

On a failed assignment, stop any still-running implementor as needed, request
`close-session` for each of its known open sessions, and use `wait-for-close`. The dispatcher stops
the reviewer; the wrapper never cancels a reviewer child directly. If the implementor
failed before reporting a session ID, use dispatcher `status` to report the unresolved
session mapping rather than guessing which other conversation to close. Report closure
failures and preserve the failed outcome even when cleanup succeeds.

Other assignments continue independently. When all assigned sessions have closed,
stop a dispatcher owned by this wrapper through its service-shutdown procedure. Leave
a caller-provided dispatcher running. Remain silent during unchanged waits.

## Report

Report each assignment's repository path, session IDs, review rounds, implementor checks,
and completion/failure outcome. Include any failed closure or dispatcher shutdown.
Do not report aggregate success while a task or owned shutdown remains unresolved.

## Example activations

- "Run these task assignments through implementation and static review concurrently."
- "Use the workspace dispatcher for these three repository tasks."
- "Pass this shared context and each task's instructions to its implementor."

See [README.md](README.md) for the one-workspace, N-repository input example.
