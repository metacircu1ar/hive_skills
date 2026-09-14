# Integration Protocol

## Purpose

The main agent integrates isolated phase implementations into one coherent product. Integration is an architectural activity, not a mechanical sequence of merges.

## Integration order

Use a topological order over implementation units.

Priority rules:

1. integrated implementation-bound predecessors before consumers;
2. component-local phase order unless the plan explicitly permits otherwise;
3. contract-foundation and shared-platform units before consumers;
4. deterministic order within dependency-equivalent units;
5. completion time never overrides dependency order.

Record the exact order in `integration-order.md` before applying worker changes. Update it only through documented dependency or contract change control.

## Pre-integration review

For each unit verify:

- worker result state permits integration;
- branch and worktree match the manifest;
- base commit matches the recorded checkpoint;
- branch is clean and commits exist;
- diff stays within owned or approved shared paths;
- no canonical contract changed without approval;
- implementation fulfills phase scope and does not include unrelated refactors;
- security, authorization, tenancy, data ownership, migration, observability, and failure semantics match the plan;
- tests are meaningful and do not merely assert implementation details;
- temporary scaffolding has an exit criterion and does not enter the production path unintentionally.

Reject or revise the unit before integration when these checks fail.

## Applying a unit

Produce one dedicated logical integration commit per phase. Prefer a linear first-parent chain suitable for exact phase review and later amendment. Common safe approaches are:

- squash the worker branch into one phase integration commit;
- cherry-pick a curated worker sequence and squash/amend it into one phase commit;
- use a repository-mandated merge strategy only when a separate deterministic linearized review branch can be constructed later.

The commit message must include the `PH-###-##` ID. Orchestration metadata commits are separate and must not be misidentified as phase commits. Do not fast-forward multiple workers together or preserve a merge shape that makes phase-to-commit mapping ambiguous.

## Conflict resolution

Resolve conflicts using this precedence:

1. confirmed product requirements and safety constraints;
2. canonical frozen contracts and approved contract changes;
3. architecture and data-ownership decisions;
4. latest integrated prerequisite behavior;
5. phase scope and worker implementation.

Do not resolve by taking one side wholesale without understanding the semantic conflict.

When a conflict reveals an invalid boundary:

- stop affected integrations;
- enter contract change control;
- update contract tests and affected workers;
- resume only after the revised baseline is committed.

## Shared-file reconciliation

For manifests, lockfiles, registries, generated outputs, migration indexes, and infrastructure definitions:

- identify the named owner from the manifest;
- apply all accepted logical changes;
- regenerate deterministically where applicable;
- verify no accepted dependency or registration was lost;
- run format, schema, generation, and consistency checks;
- include reconciliation in the phase commit of the designated owner or a dedicated contract-foundation commit.

Avoid hand-editing generated files unless the repository defines that as canonical.

## Validation ladder

After applying a unit, run the narrowest checks first and then expand:

1. formatting and syntax for changed files;
2. unit tests for changed modules;
3. canonical contract tests;
4. integration tests for affected boundaries;
5. type checking and static analysis;
6. migration and generated-artifact checks;
7. affected component build and tests;
8. repository-wide quality gates required by policy;
9. end-to-end or non-functional checks when the phase exit criteria require them.

A failure must be classified as:

- introduced by the unit;
- exposed by interaction with previously integrated work;
- pre-existing baseline failure;
- environmental limitation;
- contract defect.

Do not hide or relabel failures to preserve throughput.

## Integration fixes

The main agent may fix integration-only issues, but must:

- keep the fix within the phase's intended outcome or enter change control;
- add or update tests that reproduce the issue;
- avoid changing another not-yet-integrated unit's contract silently;
- record the fix in the implementation ledger;
- amend the phase integration commit when repository policy and publication state make that safe, or create a clearly linked follow-up commit.

The required reviewable history has one logical integration commit per phase. When repository policy creates merge-heavy history, record a linearization strategy before offering parallel phase review.

## Wave checkpoint

After all units in a wave are integrated:

- run cross-wave contract and affected end-to-end checks;
- confirm the integration branch is clean;
- record the checkpoint commit;
- update completed unit and contract statuses;
- re-evaluate downstream dependency classifications;
- update base commits for the next wave;
- create next-wave branches only from the new checkpoint.

## Partial failure in a wave

Independent units from a wave may be integrated even when another unit fails, provided:

- no dependency edge requires the failed unit;
- no shared-file reconciliation would become inconsistent;
- the resulting checkpoint remains coherent and passes required checks;
- the manifest and roadmap accurately show the missing unit.

Do not integrate a consumer whose provider or required contract failed.

## Final integration review

Before declaring the approved scope complete:

- validate every phase exit criterion;
- verify all contract implementations conform to canonical definitions;
- run the full applicable quality suite;
- inspect migration and rollback ordering;
- verify no worker branch contains unintegrated required work;
- verify planning and implementation documentation reflects actual code;
- verify no production action was taken without authorization;
- record remaining risks and deferred units.


## Pre-review integration gate

Before asking whether parallel review is needed:

- every approved phase is integrated and has one exact manifest-mapped commit;
- the phase commits appear in deterministic dependency order;
- the complete repository is clean, buildable, and passing;
- phase and contract validation evidence is current;
- the review baseline commit is frozen;
- the publication status of the phase chain is known;
- no worker branch contains required unintegrated work.

Parallel phase review is an independent defect-hunting pass, not a substitute for integration review or a way to defer known failures.
