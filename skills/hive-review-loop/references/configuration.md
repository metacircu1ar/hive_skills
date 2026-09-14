# Hive review-loop configuration

The launcher accepts YAML or JSON with `schema_version: 1`. YAML requires
PyYAML; JSON uses only Python's standard library. Unknown fields are rejected.

## Single repository

```yaml
schema_version: 1

hive:
  workflow_cli: /absolute/path/to/hive_workflow/hive_workflow
  registry_cli: /absolute/path/to/hive_registry/hive_registry

repo: /workspace/accounts-repo
run_dir: /workspace/hive-runs/accounts

implementor: Codex-GPT-5.3-xhigh-api
reviewers:
  - Claude-Opus-5-xhigh-login
  - Codex-GPT-5.6-Terra-high-login
max_rounds: 5
diff: true
cleanup_on_success: true

context:
  text: |
    Implement account lockout after five failed attempts. Preserve the existing
    public authentication API and unrelated worktree changes.
  sources:
    - path: /workspace/task-bundle/accounts-task.md
      purpose: Full task, acceptance criteria, and preserved behavior.
    - path: /workspace/evidence/accounts/
      purpose: Reproduction logs and failure traces.
```

`repo` must be the canonical Git worktree root. `run_dir` must be absolute and
outside the repository. `reviewers` is a non-empty list; entries run in
parallel during each Hive review round. Duplicate names intentionally create
separate reviewer slots and registry sessions.

`context` must contain non-empty `text`, at least one source, or both. Every
source path must be absolute and exist, and `purpose` must tell the agents what
the source contributes. A directory alone is not a complete task reference;
identify the operative task file or put the complete task in `text`.

`cleanup_on_success` defaults to `true`. Cleanup releases registry sessions but
does not delete Hive reports or launcher logs. Failed or non-consensus runs are
never cleaned automatically. Automatic cleanup requires both a final approved
reviewer collection in Hive's `summary.json` and a successful workflow exit;
missing, malformed, or contradictory evidence preserves the run.

## Multiple repositories

```yaml
schema_version: 1

hive:
  workflow_cli: /absolute/path/to/hive_workflow/hive_workflow
  registry_cli: /absolute/path/to/hive_registry/hive_registry

artifact_root: /workspace/hive-runs/epic-42
max_parallel_runs: 2

defaults:
  implementor: Codex-GPT-5.3-xhigh-api
  reviewers:
    - Claude-Opus-5-xhigh-login
    - Codex-GPT-5.6-Terra-high-login
  max_rounds: 5
  diff: true
  cleanup_on_success: true

general_context:
  text: |
    These repositories implement one migration. Preserve their published
    interfaces and keep cross-repository contract names consistent.
  sources:
    - path: /workspace/epic/architecture.md
      purpose: Shared architecture and integration constraints.

assignments:
  - id: accounts
    repo: /workspace/accounts-repo
    context:
      text: Implement account lockout according to the task bundle.
      sources:
        - path: /workspace/epic/accounts-task.md
          purpose: Complete accounts task and acceptance criteria.

  - id: billing
    repo: /workspace/billing-repo
    reviewers:
      - Claude-Opus-5-xhigh-login
      - Claude-Sonnet-4.6-max-login
      - Codex-GPT-5.6-Terra-high-login
    max_rounds: 7
    context:
      sources:
        - path: /workspace/epic/billing-task.md
          purpose: Complete billing task and acceptance criteria.

  - id: notifications
    repo: /workspace/notifications-repo
    context:
      text: Add idempotent notification delivery while preserving payload shape.
```

Each assignment may override `implementor`, `reviewers`, `max_rounds`, `diff`,
or `cleanup_on_success`. Effective implementor and reviewer values are required
after applying `defaults`.

Assignment IDs are case-insensitively unique and may contain letters, digits,
dot, underscore, and hyphen. Repositories must be pairwise disjoint, including
nested roots and symlink aliases. The launcher creates:

```text
<artifact_root>/
├── accounts/
│   ├── hive-run/          Hive prompts, responses, sessions, reports, summary
│   └── launcher/          Workflow stdout/stderr, cleanup logs, result.json
├── billing/
│   ├── hive-run/
│   └── launcher/
├── notifications/
│   ├── hive-run/
│   └── launcher/
├── parallel-summary.json
└── parallel-summary.md
```

`max_parallel_runs` limits active repository workflows. It does not limit the
parallel reviewer panel inside each workflow.

## Hive command discovery

`hive.workflow_cli` and `hive.registry_cli` may be absolute executable paths or
bare commands available on `PATH`. A value containing a directory separator
must be absolute. The launcher exports the resolved registry command through
`HIVE_REGISTRY_CLI` when invoking Hive Workflow, while preserving the caller's
registry config/state environment.
