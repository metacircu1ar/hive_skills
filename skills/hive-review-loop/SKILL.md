---
name: hive-review-loop
description: "Run one implementation-and-review loop through hive_workflow and named hive_registry agents, with one registry implementor and a configurable parallel reviewer panel. Use for a repository task that should be implemented and statically reviewed without launching Codex subagents or using the file-based code-review-loop protocol."
metadata:
  version: "1.0.0"
  argument-hint: "<review-config.yaml>"
  compatibility: "Requires Python 3.9+, PyYAML for YAML input, Git, hive_registry RPC protocol 1, and hive_workflow run-manifest contract 1 with the implement-and-run-reviewers workflow."
---

# Hive Review Loop

Execute one repository task through Hive. `hive_workflow` owns the loop,
parallel reviewer fan-out, consensus, run artifacts, resume, and cleanup;
`hive_registry` owns every implementor and reviewer agent, capability, provider
session, authentication home, and provider process.

This skill is an orchestrator only. Never spawn, delegate to, or simulate a
Codex subagent. Do not launch provider CLIs directly. Invoke only the bundled
launcher, which calls `hive_registry` for preflight and `hive_workflow` for the
actual run.

## Input

Require a single-run YAML or JSON configuration. Read
[references/configuration.md](references/configuration.md) for the complete
contract and example. The configuration names:

- one absolute Git worktree root and one external Hive run directory;
- one registry agent with `act` capability as implementor;
- one or more registry agents with `read_only` capability as reviewers;
- the round limit, diff inclusion, and successful-run cleanup policy; and
- complete task text and/or exact absolute context sources with their purpose.

Reviewer entries form a panel. Hive runs every reviewer in a round concurrently
and continues only when all return `PASS`. Repeating one registry agent name is
allowed and creates distinct reviewer slots and sessions.

## Execute

1. Inspect the configuration and confirm the requested task authorizes an
   implementation agent to modify the named repository.
2. Validate without launching agents:

   ~~~text
   python3 "<skill-dir>/scripts/run_hive_loops.py" single "<config.yaml>" --validate-only
   ~~~

   This resolves both Hive CLIs, verifies the Git root, checks registry
   capabilities and `doctor`, confirms the bundled workflow exists, and rejects
   unsafe artifact placement or an accidental existing run.
3. Run the loop:

   ~~~text
   python3 "<skill-dir>/scripts/run_hive_loops.py" single "<config.yaml>"
   ~~~

4. Report the Hive run directory, round reports, `summary.json`, launcher logs,
   registry roster used, consensus status, and cleanup status.

Exit `0` means every reviewer passed and requested cleanup, when enabled,
succeeded. Exit `1` preserves the run and sessions for diagnosis or resume.
Exit `2` is a configuration or preflight failure and launches no agents.

To resume a preserved run after correcting an external problem or increasing
`max_rounds` in the same configuration:

~~~text
python3 "<skill-dir>/scripts/run_hive_loops.py" single "<config.yaml>" --resume
~~~

Never replace a failed run directory, clean its registry sessions, or claim
consensus merely because all Hive processes exited. The Hive workflow's
machine-readable consensus result is authoritative. The launcher requires the
final collected `approved` verdict in `summary.json` and the workflow exit code
to agree; disagreement preserves the run and reports `needs_attention`.

## Boundaries

- Reviewers are strictly static and read-only; implementation-side validation
  belongs to the registry implementor.
- Context sources may be outside the repository, but every configured provider
  sandbox must be able to read them. Host-side existence does not prove that.
- Run artifacts stay outside the reviewed repository so they cannot pollute the
  submitted diff.
- The launcher does not commit, merge, push, or integrate repository changes.

## Example activations

- "Use these three registry reviewers in parallel until they all approve this repository task."
- "Run the Hive review loop from this YAML and preserve the run if consensus fails."
- "Resume the existing Hive run with a larger round limit; do not create subagents."
