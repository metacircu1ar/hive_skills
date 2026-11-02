# Parallel code-review loop example

The [skill](SKILL.md) runs one dispatcher and N implementor/reviewer conversations.
All participants use one coordination directory, even when their source paths differ.

## One workspace, N repositories

For example, `/workspace` contains shared context and the supplied repositories:

```text
/workspace/
  EPIC.md
  accounts-repo/TASK.md
  billing-repo/TASK.md
  notifications-repo/TASK.md
  .hive_skills_reviews/        # managed exclusively by the base skill's scripts
    sessions/<session-id>/
```

The orchestrator starts one dispatcher and three implementors. The dispatcher creates
one reviewer worker per submitted session. By default, each round uses a fresh session
and reviewer, then closes that session. With `session_mode: "reuse"`, the dispatcher
resumes the same conversation for subsequent rounds. Workers finish each turn and
make no idle wait calls.

## Example input file

Save this as `/workspace/parallel-review-input.json`:

```json
{
  "coordination_dir": "/workspace",
  "session_mode": "fresh",
  "general_context": {
    "task_source": "/workspace/EPIC.md",
    "constraints": [
      "Preserve public APIs unless a task explicitly changes them.",
      "Leave implementation changes uncommitted."
    ]
  },
  "assignments": [
    {
      "id": "accounts",
      "working_path": "/workspace/accounts-repo",
      "agent_context": {
        "task_source": "/workspace/accounts-repo/TASK.md",
        "validation": "Run the account test suite."
      }
    },
    {
      "id": "billing",
      "working_path": "/workspace/billing-repo",
      "agent_context": {
        "task_source": "/workspace/billing-repo/TASK.md",
        "validation": "Run the billing test suite."
      }
    },
    {
      "id": "notifications",
      "working_path": "/workspace/notifications-repo",
      "agent_context": {
        "task_source": "/workspace/notifications-repo/TASK.md",
        "validation": "Run the notification test suite."
      }
    }
  ]
}
```

Add or remove assignments to obtain N. Repository arrangement is the caller's concern;
the wrapper checks each supplied directory but does not compare source paths across pairs.

Validate and invoke:

```text
python3 "/installed/parallel-code-review-loop/scripts/validate_input.py" "/workspace/parallel-review-input.json"
/parallel-code-review-loop /workspace/parallel-review-input.json
```

There is no capacity argument or pair-limit field. The runtime must support asynchronous
agent creation, completion notifications, conversation resume, and stopping; an actual
launch failure is reported. The base skill describes background waiting and host limits.

## What happens

1. Each implementor receives general context, its task context, repository path, and
   the common coordination directory.
2. It opens a session through the base script and reports each new ID to the wrapper.
3. It implements, tests, and submits a complete review handoff through that session.
4. The dispatcher launches a static reviewer, which publishes and ends its turn.
5. In fresh mode, the implementor reads the result and closes the session, even when
   there are findings. After fixes and checks, another round opens a new session with
   a complete handoff. In reuse mode, the same session stays open and the dispatcher
   resumes its reviewer; closure follows the final clean round.
6. After clean review, checks, and closure, the implementor reports its terminal result.
   The wrapper verifies that result and closure of every recorded session. It shuts
   down its own dispatcher after all assignments finish.

The wrapper never waits for reviewer terminal messages or for channel files to disappear.
On failure, it requests closure through the helper instead of cancelling a reviewer itself.
Every role uses the supplied scripts to interact with coordination files and is silent
while waiting.

An operator can say `revive` to the dispatcher to restore all open conversations,
including idle ones. Idle conversations remain dormant until a request arrives. A
normal start after clean service shutdown performs the same recovery. Replacements
for unavailable runtime conversations with pending work are reported.

## Maintainer checks

```text
python3 "<skill-dir>/scripts/test_validate_input.py"
python3 -m unittest discover -s "<base-skill-dir>/scripts" -p 'test_*.py'
```

Input tests check context, paths, and assignment identity. Base-script process tests
exercise routing, continuation, closure, and recovery decisions. The base skill's
[bounded TLA+ suite](../code-review-loop/verification/README.md) checks session and
dispatcher behavior; run its `verification/check-all.sh` when changing that protocol.
An actual agent exercise is still needed to check that agents follow the lifecycle
instructions.
