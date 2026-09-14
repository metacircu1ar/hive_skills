---
name: hive-parallel-review-loop
description: "Run multiple independent repository implementation/review loops concurrently as hive_workflow processes backed by named hive_registry implementors and parallel reviewer panels. Use when a YAML manifest supplies disjoint repositories and shared plus per-assignment context, and no Codex subagents should be launched."
metadata:
  version: "1.0.0"
  argument-hint: "<parallel-review-config.yaml>"
  compatibility: "Requires the sibling hive-review-loop skill, Python 3.9+, PyYAML for YAML input, Git, hive_registry RPC protocol 1, and hive_workflow run-manifest contract 1."
---

# Hive Parallel Review Loop

Run `N` independent Hive implementation/review workflows across `N` disjoint
repositories. Each workflow has one named registry implementor and a
configurable panel of named registry reviewers. Hive runs the reviewers in each
panel concurrently; this wrapper additionally runs multiple repository
workflows concurrently up to `max_parallel_runs`.

Never launch Codex subagents. The only worker processes are `hive_workflow`
commands, and only `hive_registry` may instantiate provider agents and own
their sessions.

Read the complete sibling [hive-review-loop](../hive-review-loop/SKILL.md) skill
and its [configuration contract](../hive-review-loop/references/configuration.md)
before executing this skill.

## Execute

1. Require unique assignment IDs, pairwise-disjoint absolute Git worktree
   roots, an external artifact root, a positive concurrency limit, defaults for
   registry agents, and complete shared plus per-assignment context.
2. Confirm that every task authorizes the configured registry implementor to
   modify its repository.
3. Validate the entire batch before launching any Hive run:

   ~~~text
   python3 "<hive-review-loop-skill-dir>/scripts/run_hive_loops.py" parallel "<config.yaml>" --validate-only
   ~~~

4. Run the batch:

   ~~~text
   python3 "<hive-review-loop-skill-dir>/scripts/run_hive_loops.py" parallel "<config.yaml>"
   ~~~

5. Report the aggregate Markdown summary, JSON summary, and every assignment's
   Hive run, reviewer panel, round reports, launcher logs, and terminal status.

The launcher completes independent assignments even when another assignment
fails. Exit `0` requires every assignment to reach reviewer consensus and
complete requested cleanup. Exit `1` means at least one assignment needs
attention; its Hive run and sessions remain available. Exit `2` means batch
preflight failed before any workflow launch.

Resume after fixing external failures or extending assignment round limits:

~~~text
python3 "<hive-review-loop-skill-dir>/scripts/run_hive_loops.py" parallel "<config.yaml>" --resume
~~~

Existing assignments with `run.json` resume; assignments without a run start
normally. Never delete or replace preserved run directories to manufacture a
clean batch result.

## Concurrency model

`max_parallel_runs` limits concurrent repository workflows, not reviewer count.
If two repository runs are active and each has three reviewers, up to six
reviewer provider turns can overlap after their implementor turns. Choose the
limit from provider quotas and machine capacity.

No repository, Hive run directory, or launcher-artifact directory may overlap
another repository. Each assignment receives its own Hive run and registry
sessions; no agent conversation is shared across assignments.

## Example activations

- "Run this three-repository Hive manifest with two workflows at a time."
- "Use the default reviewer panel everywhere, but override it for the billing repository."
- "Resume only the unfinished Hive runs and produce a new aggregate summary."
