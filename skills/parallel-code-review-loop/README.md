# Parallel code-review loop example

This is a human-facing example of the workflow defined by [SKILL.md](SKILL.md). `SKILL.md` is the normative contract if this example and the skill ever disagree.

## Scenario: one workspace, N repositories

Suppose one workspace contains shared epic context and three independent repositories:

```text
/workspace/
├── context/
│   └── EPIC.md
├── accounts-repo/
│   └── TASK.md
├── billing-repo/
│   └── TASK.md
└── notifications-repo/
    └── TASK.md
```

Here `N = 3`. The orchestrator creates one dedicated pair for each repository. Assignment IDs remain stable report data; the orchestrator derives separate provider-valid launch names for the agents:

| Assignment | Baseline implementor name | Baseline reviewer name | Repository and coordination directory |
|---|---|---|---|
| `accounts` | `pair_001_implementor` | `pair_001_reviewer` | `/workspace/accounts-repo` |
| `billing` | `pair_002_implementor` | `pair_002_reviewer` | `/workspace/billing-repo` |
| `notifications` | `pair_003_implementor` | `pair_003_reviewer` | `/workspace/notifications-repo` |

Each pair is independent. Its repository root is also its `code-review-loop` coordination directory, so temporary `.hive_skills_*` protocol files appear only in that repository. They are removed after clean completion.

With six confirmed worker slots available in addition to the orchestrator, all three pairs can run concurrently. With only four, the orchestrator runs at most two complete pairs at once and queues the remaining pair. It never starts implementors without reserving capacity for their reviewers. If it cannot confirm at least two slots, live progress-message delivery, monitoring, and cancellation, preflight stops without launching a pair.

Within every pair, startup is ordered:

```text
implementor starts
  -> implementor completes startup cleanup
  -> orchestrator receives a structured startup_clean event
  -> reviewer starts
  -> pair follows the code-review-loop protocol to completion
  -> both roles send matching terminal_result events and exit
```

## Example input file

Save a manifest such as `/workspace/parallel-review-input.json`:

```json
{
  "general_context": {
    "objective": "Complete the three tasks as one compatible epic.",
    "sources": [
      {
        "path": "/workspace/context/EPIC.md",
        "description": "Shared architecture, compatibility constraints, and integration expectations."
      }
    ],
    "common_constraints": [
      "Preserve existing public APIs unless a task explicitly changes one.",
      "Leave implementation changes uncommitted for later integration."
    ]
  },
  "assignments": [
    {
      "id": "accounts",
      "working_path": "/workspace/accounts-repo",
      "agent_context": {
        "objective": "Implement the account-lockout task.",
        "task_source": "/workspace/accounts-repo/TASK.md",
        "validation": "Run the repository's documented account test suite.",
        "required_output": "Working code, tests, and a completed review loop."
      }
    },
    {
      "id": "billing",
      "working_path": "/workspace/billing-repo",
      "agent_context": {
        "objective": "Implement the invoice-retry task.",
        "task_source": "/workspace/billing-repo/TASK.md",
        "validation": "Run the repository's documented billing test suite.",
        "required_output": "Working code, tests, and a completed review loop."
      }
    },
    {
      "id": "notifications",
      "working_path": "/workspace/notifications-repo",
      "agent_context": {
        "objective": "Implement the delivery-deduplication task.",
        "task_source": "/workspace/notifications-repo/TASK.md",
        "validation": "Run the repository's documented notification test suite.",
        "required_output": "Working code, tests, and a completed review loop."
      }
    }
  ],
  "max_parallel_pairs": 3
}
```

Add or remove assignment entries to obtain arbitrary `N`. Every `working_path` must be an absolute, disjoint repository root: equal and nested roots are rejected. `max_parallel_pairs` is optional and, when present, must be a positive integer. The effective limit is the minimum of `N`, that value, and half the confirmed worker slots.

After confirming six concurrently available worker slots, the orchestrator runs the deterministic preflight check:

```text
python3 "/installed/parallel-code-review-loop/scripts/validate_input.py" "/workspace/parallel-review-input.json" --confirmed-worker-slots 6
```

The command prints canonical roots, collision-safe baseline launch names, effective concurrency, and whether waves are required. The orchestrator verifies those names against its provider and adapts them if necessary. YAML manifests are also accepted when PyYAML is installed; JSON needs only Python's standard library.

## What each role receives

Every implementor receives the shared `general_context`, its own `agent_context`, its assignment ID, and its repository path. Its first protocol message gives its reviewer the complete repository, task, evidence, and review-target context.

Each reviewer starts with only its assignment ID, repository path, reviewer role, and the base `code-review-loop` skill location. It obtains task context from the implementor's protocol message, keeping that message as the single source of truth.

The orchestrator waits until all pairs finish or fail, then reports each assignment separately. If one role fails, it cancels the surviving role through the runtime and leaves that repository and its protocol files untouched for diagnosis. It does not merge or otherwise integrate the repositories unless that is requested as a separate operation.

## Maintainer checks

Run the deterministic preflight tests with:

```text
PYTHONDONTWRITEBYTECODE=1 python3 "<skill-dir>/scripts/test_validate_input.py" -v
```

These tests cover manifest structure, capacity arithmetic, path isolation, and launch-name derivation. They do not simulate an agent provider or prove live message delivery, cancellation, role compliance, or process liveness; those remain runtime preflight requirements and should be exercised end to end when the supported runtime changes.
