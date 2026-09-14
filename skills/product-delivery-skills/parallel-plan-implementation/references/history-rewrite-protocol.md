# Verified-Finding History Reconstruction Protocol

## Purpose

Amend verified fixes into the phase commits that own them while preserving all later phase behavior, tests, contracts, and traceability.

## Preconditions

Do not rewrite phase history until:

- implementation is complete for the approved scope;
- the repository is clean, buildable, and passing at a frozen review baseline;
- the user approved parallel review;
- every phase maps to exactly one reviewable integration commit;
- all reviewer reports have returned or are explicitly blocked;
- the main agent has verified, deduplicated, and assigned every surviving finding;
- a backup ref points to the original passing tip;
- remote publication and branch-protection status are known;
- the rewrite plan and expected phase order are recorded.

## Safety policy

1. Never rewrite the user's unrelated branch or working tree.
2. Never force-push or update a protected/shared remote ref without separate explicit authorization.
3. When publication status is uncertain, treat history as published.
4. Preserve a backup ref and original commit map until the rewritten branch is validated and accepted.
5. Use a dedicated rewrite branch when history is published, protected, merge-heavy, or otherwise unsafe to amend in place.
6. Stop rather than discarding a descendant change that conflicts with an earlier fix.
7. Orchestration metadata containing final hashes must be committed after the rewritten phase chain; no commit can reliably record its own final hash.

## Phase-commit invariant

The reviewable phase chain should contain one dedicated logical commit per `PH-###-##`, in topological integration order. Planning, contract-baseline, and orchestration metadata commits may exist, but the review manifest must distinguish them from phase commits.

When the original integration branch uses merge commits or cannot supply an unambiguous phase chain, construct a dedicated local linearized review branch before dispatch. Preserve commit authorship and phase IDs where repository policy permits.

## Assign fixes before rewriting

For each main-agent-confirmed issue, record:

- source reviewer finding IDs;
- exact root mechanism;
- earliest responsible phase;
- files and contracts affected;
- fix strategy;
- regression-test strategy;
- whether the test can exist in the responsible phase;
- expected descendant conflicts or generated-artifact changes;
- validation commands at the edit stop and at final tip.

A fix belongs to the earliest phase where the faulty behavior was introduced and where the corrected implementation can coherently exist.

A regression test belongs in that same phase when its test infrastructure and public surface already exist. When they do not, put the code fix in the responsible phase and the regression test in the earliest later phase that can validly express it. Record the split.

## Prefer one controlled replay

After all findings are adjudicated, perform one controlled history reconstruction from the parent of the earliest affected phase rather than repeatedly rebasing descendants for each individual finding.

Typical procedure:

1. verify a clean integration/rewrite worktree;
2. resolve and record the original phase chain and parents;
3. create the backup ref;
4. create the rewrite branch at the original passing baseline;
5. start an interactive rebase or equivalent deterministic replay from the parent of the earliest affected phase;
6. mark every phase receiving a code fix or phase-valid test for `edit`;
7. replay unaffected phase commits unchanged in logical content;
8. at each edit stop, apply only the fixes and tests assigned to that phase;
9. run targeted, contract, phase, migration, generated-artifact, and affected checks available at that historical point;
10. amend while preserving the phase ID and purpose in the commit message;
11. continue replay, resolving conflicts against current plans and canonical contracts;
12. never drop later functionality merely to make replay easier;
13. after the phase chain is reconstructed, run the full repository suite at the final tip;
14. create a separate orchestration metadata commit updating old-to-new commit mapping, manifests, ledgers, and validation evidence.

Equivalent plumbing-based reconstruction is permitted when interactive rebase is unsuitable, provided it preserves the same invariants and audit trail.

## Conflict resolution

For every descendant conflict:

- identify which phase introduced each side;
- preserve the corrected earlier invariant and the intended later feature;
- consult the latest approved plan, frozen/changed contracts, and finding disposition;
- regenerate generated code only from its canonical source;
- preserve migration ordering and mixed-version compatibility;
- rerun the descendant phase's targeted checks;
- record non-trivial conflict resolution in the review ledger.

Do not resolve by weakening validation, deleting tests, bypassing authorization, or reverting required later behavior.

## Contract change control

When a verified fix changes a public contract:

1. stop the affected replay point;
2. determine whether the change is corrective-compatible, versioned-breaking, or plan-changing;
3. update the canonical contract, owner/consumer boundaries, generated artifacts, mocks, and contract tests together;
4. assign provider and consumer changes to the correct phases;
5. re-review affected phase attribution when the contract change moves ownership;
6. obtain user clarification when the change alters intended product behavior rather than correcting implementation;
7. record the contract version and compatibility decision.

## Validation ladder

At an edited phase commit, run what can validly run at that historical point:

- new regression test, failing on the original commit when reproducible and passing after the fix;
- target module/component tests;
- contract tests;
- type, lint, static-analysis, and security checks for touched paths;
- migration/schema checks;
- generated-artifact consistency checks.

At the rewritten final tip, run:

- every regression test for confirmed findings;
- all affected phase exit checks;
- full build and test suite;
- formatting, linting, type checking, static analysis, security, packaging, and migration checks required by the plan;
- end-to-end and contract suites available in the environment;
- parallel-plan and parallel-review validators;
- clean-worktree and commit-map checks.

## Completion evidence

Record:

- original passing baseline and backup ref;
- rewrite branch;
- original-to-current commit for every phase;
- findings assigned and fixed per phase;
- tests added per phase;
- conflicts and resolutions;
- contract changes;
- targeted and final validation results;
- final code checkpoint and separate metadata commit;
- publication status and any retained local refs/worktrees.

## Blockers

Stop with the backup intact when:

- a phase cannot be mapped to one commit;
- the target commit or parent changed after review dispatch;
- unrelated user changes contaminate the rewrite worktree;
- a required fix would change intended product behavior without clarification;
- a descendant conflict cannot preserve both the corrected invariant and later requirements;
- the repository cannot return to a buildable, passing state;
- remote history would need rewriting without authorization.
