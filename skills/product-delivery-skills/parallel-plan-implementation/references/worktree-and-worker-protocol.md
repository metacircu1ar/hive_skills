# Worktree and Worker Protocol

## Purpose

This protocol isolates write-heavy implementation units and prevents workers from contaminating the integration branch or one another.

## Repository preflight

Record:

- repository root and Git version;
- current branch and `HEAD`;
- existing worktrees;
- uncommitted, staged, and untracked paths;
- submodules, large-file storage, sparse checkout, hooks, and repository-specific rules;
- environment setup commands;
- build, test, lint, type, format, security, migration, and generation commands;
- credentials or services unavailable in isolated worktrees.

Never assume that a new worktree automatically contains ignored files, installed dependencies, local databases, secrets, or generated artifacts.

## Protecting user changes

Do not use destructive commands such as `git reset --hard`, `git clean -fd`, or an unconditional stash.

When the user's checkout is dirty:

1. determine whether changed files overlap the approved implementation or informed the plan;
2. if they overlap or are required, obtain a safe inclusion decision before creating the baseline;
3. if they are unrelated, leave that checkout untouched and create the integration worktree from committed `HEAD`;
4. copy and commit only approved planning/orchestration documents into the integration branch when they are not yet committed;
5. record excluded changes so the final report does not imply they were integrated.

## Integration branch and worktree

Use a dedicated branch and worktree for the main agent. Derive names safely from repository conventions and avoid collisions.

Record:

- branch name;
- worktree path;
- baseline commit;
- planning commit;
- contract-baseline commit;
- current integration checkpoint after every wave.

The main agent alone writes to this worktree during worker execution.

## Worker branch and worktree

For each implementation unit:

- create a unique branch from the manifest's exact base commit;
- create a unique worktree outside the integration working tree;
- verify the worktree points to the intended branch and commit;
- run repository setup appropriate to that worktree;
- record path and branch in `execution-manifest.json`;
- do not reuse a worktree for a different phase until the first unit is integrated or explicitly abandoned.

A safe naming convention is conceptually:

```text
branch: agent/ph-001-02-short-outcome
worktree: <orchestration-root>/ph-001-02
```

Adapt to repository policy. Do not rely on the example literally when names already exist.

## Base-commit rules

- Never attempt to make a commit record its own hash. Commit the launch baseline with `pending` metadata, resolve its hash, create worker branches from it, and record the resolved hash in a later integration-branch orchestration commit.
- Units in the same wave normally share the same integration checkpoint.
- A contract-bound consumer's base must contain the frozen contract and support artifacts.
- An implementation-bound consumer's base must contain the integrated predecessor implementation.
- Record the base commit per unit; never infer it later from branch ancestry alone.
- Do not rebase an active worker silently. Contract or baseline changes require coordination and a manifest update.

## Worker context packet

Every implementor receives the requested runtime profile `gpt-5.6-terra` / `xhigh`, the host-reported actual profile, and:

- unit and component IDs;
- exactly one approved-scope JSON block containing the typed delivery scope mode, requested outcome, impact cone, preserved behavior, and non-goals copied from the schema-v2 `execution-manifest.json` in the unit's base commit;
- exact worktree path and branch;
- source component plan and phase link;
- component boundary document and phase link;
- canonical contract IDs and paths;
- relevant architecture and repository rules;
- owned, read-only, shared, generated, and forbidden paths;
- implementation scope and explicit non-scope;
- required commands and exit criteria;
- expected commit and result format;
- instruction to return `CONTRACT_BLOCKER` when that scope block or a required contract is missing, malformed, duplicated, or contradictory rather than guessing or changing it.

Give the implementor complete context relevant to its phase, including every plan, boundary, contract, repository rule, predecessor guarantee, and consumer obligation needed to implement it correctly. Do not bury it in unrelated plans; relevance, not minimum token count, defines the packet. It may read additional repository files needed to understand existing code but must not expand its assigned scope.

## Worker write policy

A worker may:

- edit owned paths;
- add tests and documentation within owned paths;
- use canonical generators as specified;
- request a contract change through its result.

A worker may not:

- edit canonical contracts or boundary documents unless explicitly assigned as contract owner;
- change another unit's owned paths;
- write to the integration checkout;
- merge, rebase, or delete branches;
- weaken tests, security, authorization, data integrity, or observability to make checks pass;
- add broad temporary compatibility code outside its phase exit criteria;
- perform production actions.

## Shared files

When a worker needs a shared file:

1. prefer an extension point or generated registration that avoids editing it;
2. otherwise assign the file to one owner in the wave;
3. other workers produce a clearly identified integration instruction or fragment rather than editing the file;
4. the owner or main agent performs deterministic reconciliation;
5. run the canonical generator and checks after reconciliation.

For lockfiles, the main agent may regenerate once after integrating all dependency-manifest changes in a wave, provided the repository's package manager guarantees deterministic output.

For migrations, use a centrally defined ordering and naming policy. Parallel workers must not independently choose colliding sequence numbers or assume migration order.

## Worker validation

Workers run all checks required by their boundary and as many affected repository checks as practical. They must report:

- exact commands;
- exit status;
- tests passed, failed, skipped, or unavailable;
- environment limitations;
- generated files;
- pre-existing failures observed;
- unverified exit criteria.

A green worker branch is not sufficient evidence for integration. The main agent reruns relevant checks after applying the unit with previously integrated work.

## Worker result states

Use one of:

- `COMPLETED`: implementation and required local checks completed.
- `COMPLETED_WITH_LIMITATIONS`: code completed, but named checks could not run for environmental reasons.
- `CONTRACT_BLOCKER`: a required boundary is missing, contradictory, or insufficient.
- `IMPLEMENTATION_BLOCKER`: code cannot proceed because of repository, dependency, or tooling state not represented by a boundary.
- `FAILED`: work attempted but did not meet the phase contract.

A blocker result must include evidence, affected contract or phase IDs, and the smallest decision needed from the main agent.

## Commit policy

Workers create coherent commits on their branch. The repository's normal commit policy applies.

Every worker result includes:

- commit IDs in order;
- concise purpose of each commit;
- changed paths;
- generated paths;
- whether the branch is clean;
- whether any untracked files remain.

The main agent integrates the logical phase as one dedicated commit containing the `PH-###-##` ID. Prefer squashing or curating worker commits into that phase commit so later commit-scoped review and safe amendment are unambiguous. Orchestration metadata commits remain separate.

## Cleanup

Before removing a worktree:

- verify it is the intended worktree;
- verify its branch and commit status;
- verify no uncommitted or untracked files contain unique work;
- verify the unit is integrated, rejected with evidence, or intentionally archived;
- update the manifest and ledger.

Never force-remove a worktree merely to simplify cleanup.
