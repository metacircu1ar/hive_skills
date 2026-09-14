# Parallel Phase-Commit Review Orchestration Protocol

## Purpose

This reference contains the detailed procedures for Review Phases 10–14 after the user approves review. Read it together with `references/code-review-skill.md`, `references/history-rewrite-protocol.md`, and `references/agent-model-policy.md`.

### Review Phase 10 — Freeze commit scope and prepare review artifacts

Read `references/history-rewrite-protocol.md`. Require separately installed `phase-commit-reviewer` version `1.3.0` or newer.

1. Freeze the current passing commit as `review_baseline_commit`.
2. Derive phase commits from execution-manifest `integration_commit` values, not from every branch commit.
3. Verify each phase maps to exactly one commit, the commit message contains the phase ID, and phase order is deterministic.
4. Read the schema-v2 execution manifest from `review_baseline_commit`; treat that Git object, not a mutable worktree copy, as the review scope and phase source. Record target parent, component, plan section, boundary section, contracts, changed paths, later phase commits, and final baseline for each phase. Copy the five typed scope fields into the assignment's unique approved-scope JSON block. In both the phase's review-manifest record and reviewer assignment, set `external_fidelity_required` explicitly: `true` when the phase implements, emulates, or validates an uncontrolled provider protocol or its mapping into the product-owned port; `false` when it has no such responsibility, including a consumer that uses only the normalized port. When true, also attach the applicable dossier and evidence, known gaps, test-double provenance and omissions, provider version/environment, and conformance results.
5. Create a backup ref at the original passing tip.
6. Detect whether history is published, protected, shared, or uncertain. Use a dedicated local rewrite branch unless safe unpublished history can be amended locally. Never force-push automatically.
7. Create `docs/implementation-plan/parallel-implementation/parallel-review/` containing `README.md`, `review-manifest.json`, `review-ledger.md`, `commit-map.md`, `findings/`, and `reviewer-prompts/`.
8. Determine full-parallel or bounded-parallel review batches from the host concurrency limit, assign one unique reviewer instance per phase, and record the planned batches.
9. Generate one prompt from `assets/reviewer-prompt-template.md` per phase, calculate SHA-256 over its exact bytes, record that value as `prompt_sha256` in the phase review, and validate the package before dispatch. Dispatch those exact bytes; regenerate and re-hash after any prompt edit.

### Review Phase 11 — Launch one fresh reviewer per phase in parallel

For every phase commit, create an isolated detached worktree at that target commit, or an equivalent immutable target snapshot, and launch one fresh `gpt-5.6-sol` / `xhigh` agent with the `phase-commit-reviewer` skill. Give it read-only Git-object access to the frozen final baseline for later-state comparison.

Each reviewer receives the exact target commit and parent, final baseline, the hash-identified prompt with typed approved-scope fields and preservation obligations, component plan and phase, boundary and phase, consumed/produced contracts, architecture and quality plans, repository rules, full phase map, later-phase summaries, safe validation commands, review protocol, JSON schema, and the explicit `external_fidelity_required` value. When it is true, the reviewer also receives the applicable external-system dossier and evidence, known gaps, test-double provenance and omissions, provider version/environment, and available characterization or conformance results. The reviewer does not derive or override the scope data or flag. Reviewers are read-only, do not receive one another's findings, and return at most 15 verified findings.

Dispatch all reviewers concurrently when host capacity permits. A hard host concurrency cap may be handled with bounded parallel batches, but every phase still receives a distinct fresh agent and the manifest must record batch membership, distinct reviewer instance IDs, and overlapping start/completion evidence. When more than one phase exists, a one-at-a-time single-agent loop is not parallel and requires explicit fallback approval. If the host cannot create fresh reviewer contexts or provision the approved profile, stop with an explicit blocker.

### Review Phase 12 — Verify, deduplicate, and assign findings

After all reviewers finish, the main agent:

1. validates every report against `assets/review-findings.schema.json`;
2. deduplicates identical mechanisms across commits;
3. independently checks target code, final code, callers, tests, plans, boundaries, and contracts;
4. classifies each report as `confirmed`, `rejected`, `duplicate`, `already-fixed`, or `reassigned`;
5. assigns every confirmed issue to the earliest responsible phase;
6. designs a regression test when practical and assigns it to the earliest phase where it can validly run;
7. enters contract change control when a fix changes a frozen public contract;
8. records evidence and a deterministic history-reconstruction plan before editing.

Do not fix a merely plausible candidate without main-agent verification. Do not preserve a reviewer's phase attribution when evidence identifies a different root-cause phase.

### Review Phase 13 — Amend responsible phases and replay descendants

Follow `references/history-rewrite-protocol.md`. After all findings are adjudicated, use one controlled history reconstruction from the parent of the earliest affected phase rather than repeatedly rebasing for each finding.

At each affected phase:

- apply only verified fixes assigned there;
- add phase-valid regression tests when possible;
- run targeted, phase, contract, migration, generated-artifact, and affected checks;
- amend the phase commit while preserving its ID and purpose;
- replay later phase commits in order, resolving conflicts without losing later behavior.

When a regression test requires later test infrastructure, amend the code fix into the responsible phase and the test into the earliest valid later phase. Reconstruct the complete original-to-current commit map. Update manifests and ledgers in a separate metadata commit after final hashes exist. Keep the backup ref. Never force-push without separate authorization.

### Review Phase 14 — Final verification and finish

After all verified fixes are integrated:

1. run every new regression test;
2. run affected phase and contract validations;
3. run the complete repository build and quality suite again;
4. verify migrations, generated artifacts, phase exit criteria, and preserved later functionality;
5. record findings, dispositions, tests, old-to-new commits, final code checkpoint, backup ref, profile evidence, and limitations in the review artifacts; keep the review manifest at `status: validating` with `metadata_commit: pending` during pre-commit checks;
6. update `docs/implementation-plan/delivery-status.md` from the final review manifest, ledger, commit map, and validation evidence: set the **Review** row and current status, summarize material fixes and residual risks, state any operator action, and link rather than copying detailed findings or traces;
7. validate the implementation, pre-completion review, and current planner packages so the review records and human-status structure are checked;
8. set the review manifest to `status: completed` and `metadata_commit: self`, then commit the resolved review records and human-status update in one separate orchestration metadata commit after all rewritten phase hashes exist; `self` denotes the commit containing that exact manifest, avoiding an impossible literal SHA self-reference; never amend a phase commit merely to carry the summary;
9. rerun the implementation, completed-review, and planner validators from the committed tip so `metadata_commit: self` and the final clean package are checked;
10. verify the final branch is clean;
11. remove review worktrees only when no unique work exists;
12. explicitly tell the operator that the human delivery status was updated, give its path, state the review outcome, and say whether any action remains;
13. finish the skill without another generic question.

If review stops blocked before Phase 14 completes and control returns to the operator, perform the same status update and notification using the latest authoritative review evidence. Commit it with the corresponding orchestration records when the workflow is already committing review metadata; never sweep unrelated work into that commit. Reviewer agents remain read-only and never update the cross-stage summary themselves.
