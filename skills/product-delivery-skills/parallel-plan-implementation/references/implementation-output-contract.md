# Parallel Implementation Output Contract

## Default directory tree

Create:

```text
docs/implementation-plan/parallel-implementation/
├── README.md
├── execution-manifest.json
├── dependency-graph.md
├── contract-baseline.md
├── integration-order.md
├── implementation-ledger.md
├── boundaries/
│   ├── <component-plan-name>.md
│   └── ...
└── worker-prompts/
    ├── <phase-id-lowercase>.md
    └── ...
```

Do not create boundary documents for components outside the user-approved scope. Record excluded or blocked phases in the manifest with reasons.

## Cross-stage human delivery status

`docs/implementation-plan/delivery-status.md` remains outside this nested orchestration directory. It is the concise, derived operator view created by the planner. The main implementation orchestrator updates its **Implementation** row after final implementation verification or when implementation returns blocked, and updates its **Review** row after review completes, is declined, or returns blocked. Implementors and read-only reviewers never edit it.

The summary links to `execution-manifest.json`, `implementation-ledger.md`, phase commits, review artifacts, and validation evidence instead of copying them. It never grants scope, changes a status in a manifest or ledger, resolves a finding, or overrides a commit or test result. After each top-level update, the main orchestrator explicitly tells the operator the path, current stage/status, and required action. Run the planner validator against the current repository after updating it. When implementation or review artifacts are being committed, include the summary in the separate orchestration metadata commit; never amend a phase commit solely to carry a human-status update.

## Global conventions

Use stable IDs:

- component: `CMP-###`;
- phase or implementation unit: `PH-###-##`;
- contract: `CTR-###`;
- product or architecture decision: existing `DEC-###` or `ADR-###`;
- integration issue when useful: `INT-###`.

Use repository-relative paths for repository-owned artifacts. The manifest may use a canonical absolute `repository_root` and absolute integration or worker worktree paths because those fields describe the active execution environment.

Statuses must come from documented enumerations. Do not use ambiguous states such as “mostly done.”

### Commit self-reference rule

A committed manifest, boundary document, or worker prompt cannot contain the hash of the commit that contains it. Use a two-step protocol:

1. commit the frozen contracts, boundaries, prompts, and manifest with unresolved launch-base fields set to `pending`;
2. resolve that commit hash, create worker branches from it, then record the resolved hash in a separate orchestration commit on the integration branch.

`pending` is allowed only for a future or not-yet-dispatched wave. A ready or running unit must have a resolved base commit in the integration branch's current manifest.

## `README.md`

Required sections:

1. Implementation status and approved scope
2. Baseline and contract-baseline commits
3. Environment capability result
4. Component and phase scope
5. Contract summary
6. Verified parallel waves
7. Integration strategy
8. Document index
9. Current blockers and decision gates
10. How to resume or revise execution

Clearly distinguish boundaries prepared, workers launched, units completed, units integrated, and units verified.

## `execution-manifest.json`

This is the machine-readable orchestration source. Conform to `assets/execution-manifest.schema.json`.

Use execution-manifest schema version `2`. Version 2 makes `agent_profiles`, `review_gate`, and the typed approved-scope fields mandatory; schema validation and the bundled validator must accept the same document.

It must contain:

- schema version;
- repository and planning roots;
- approved scope;
- integration branch and worktree;
- baseline, planning, contract-baseline, and current checkpoint commits;
- host capability declarations;
- requested and actual main, implementor, and reviewer profiles;
- a separate review-gate status and authorization record when review is offered;
- contract registry;
- shared-path owner registry;
- implementation units;
- verified waves;
- deterministic integration order;
- excluded or blocked units;
- validation commands;
- update timestamp and status.

The `approved_scope` object must contain:

- `phase_ids` and a concise human-readable `description`;
- `delivery_scope_mode`, using the planner's four-value enumeration;
- non-empty `requested_outcome` and `impact_cone` strings;
- `preserved_behavior` and `non_goals` arrays of explicit statements.

The preservation array must be present, and every bounded mode requires at least one explicit preservation statement; the array may be empty only for `full product`. Every mode requires at least one explicit non-goal. These five typed fields must equal the canonical delivery-scope block in `00-product-description.md` at `integration.planning_commit`; `description` is only their summary. `phase_ids` must equal executable unit IDs, each must be in that immutable plan's `authorized_phase_ids`, and excluded IDs never grant authority. Executable and excluded IDs are disjoint and together cover `planned_phase_ids`, so repository-wide inspection or validation cannot add or silently omit phases.

Read the canonical decomposition assessment from `93-implementation-units.md` at the same immutable planning commit. Do not duplicate it as mutable manifest prose. Every implementation unit must declare at least one write-capable `owned_paths`, `shared_paths`, or `generated_paths` entry. Unit `component_id` and those paths must agree with the data-writer registry: phases of an authorized writer component may write the declared paths; any other component is a validation error. Multiple authorized writer components require the recorded coordination mechanism and the corresponding dependency or shared-path serialization in the execution artifacts.

Every worker prompt contains exactly one raw JSON object between `<!-- approved-scope:begin -->` and `<!-- approved-scope:end -->`. It copies the five typed scope fields without re-summarization. Before dispatch, commit the prompt and schema-v2 execution manifest into the unit's base commit; later validation reads both from that commit rather than trusting mutable worktree copies.

### Schema migration

Do not relabel a version-1 manifest as version 2. Re-read the canonical plan scope, make executable and excluded phase IDs disjoint, populate `agent_profiles` and `review_gate`, regenerate the unique scope block in every worker prompt, commit the packet, and then record version 2. For a version-1 review package, regenerate reviewer prompts from the immutable review-baseline execution manifest, record each exact prompt's SHA-256, and create a version-2 review manifest.

Every implementation unit must include:

- phase and component IDs;
- plan, boundary, and worker-prompt paths;
- wave and integration index;
- base commit, or `pending` for a later wave whose checkpoint does not yet exist;
- branch and worktree;
- execution classification and open decision gates;
- predecessor dependency edges classified as contract-bound or implementation-bound;
- consumed and produced contract IDs;
- owned, read-only, shared, generated, and forbidden paths;
- the applicable shared-path owner and reconciliation strategy for every shared path;
- validation commands;
- status;
- worker result and commits when available;
- integration commit when integrated;
- limitations and blockers.

## `dependency-graph.md`

Required sections:

1. Graph purpose and source
2. Node registry
3. Edge registry
4. Dependency-type decisions
5. Mermaid dependency graph
6. Cycles found and resolutions
7. Contract-parallel edges
8. Implementation-bound edges
9. Decision-gated units
10. Shared-path serialization constraints

Every edge lists provider, consumer, type, reason, contracts, and earliest eligible wave.

## `contract-baseline.md`

Required sections:

1. Baseline purpose
2. Baseline commit
3. Contract registry
4. Materialized declarations and schemas
5. Generated artifacts
6. Mocks, fakes, fixtures, and emulators
7. Contract tests and validation commands
8. Compatibility and versioning
9. Contract ownership
10. Contract gaps and reclassified dependencies
11. Change-control procedure

Do not mark the baseline frozen until every first-wave contract validates.

## `integration-order.md`

Required sections:

1. Ordering principles
2. Integration checkpoint history
3. Ordered phase list
4. Per-wave order
5. Shared-file reconciliation owners
6. Migration and generated-artifact order
7. Validation after each phase
8. Stop conditions
9. Replanning triggers

The ordered phase list uses implementation dependencies, not worker finish times.

## `implementation-ledger.md`

Required sections:

1. Ledger status
2. Phase implementation records
3. Contract change records
4. Integration issues and resolutions
5. Validation summary
6. Pre-existing failures and environmental limitations
7. Deviations and approvals
8. Retained worktrees and branches
9. Remaining units and production gates

For every phase record:

- phase and component IDs;
- worker status;
- worker commits;
- integration commit;
- contracts consumed and produced;
- changed paths;
- commands and results;
- exit-criteria result;
- deviations;
- integration issues;
- completion status.

## `boundaries/<component-plan-name>.md`

Create one boundary document per included component plan. Use the complete structure in `references/boundary-contract-standard.md`.

A boundary file must contain a `### PH-###-## — ...` section for every included phase of that component. Keep canonical contracts in their source files and link to them.

## `worker-prompts/<phase-id-lowercase>.md`

Create one prompt per worker unit from `assets/worker-prompt-template.md`.

The prompt is an execution packet, not a generic role description. It must identify exact paths, contracts, checks, commit requirements, and blocker behavior. Copy the five typed scope fields into the template's one raw JSON scope block, and copy the unit's `owned_paths`, `read_only_paths`, `shared_paths`, `generated_paths`, and `forbidden_paths` into its one raw JSON path-policy block. Reject duplicate blocks or keys. The validator cross-checks both blocks against the execution manifest stored in the unit's immutable base commit, cross-checks the current manifest against that immutable path policy, and rejects any prompt write grant overlapping the orchestrator-owned human status.

## Update discipline

- The main agent owns all orchestration documents.
- The main agent alone owns the cross-stage `delivery-status.md`; workers and reviewers treat it as read-only.
- Workers treat these files as read-only unless explicitly assigned to documentation-only work.
- Update the manifest and ledger after every material state transition.
- Commit boundary and manifest changes before workers rely on them.
- Record actual execution separately from planned execution; never mark a wave executed merely because it was designed.

## Optional `parallel-review/` package

Create this package only after the repository is clean, buildable, and passing and the user explicitly approves parallel review.

### `parallel-review/review-manifest.json`

Conform to schema version 2 in `assets/review-manifest.schema.json`. Record:

- explicit review authorization;
- frozen original review baseline and pre-phase base;
- backup ref, rewrite branch, publication status, and force-push authorization;
- requested and actual reviewer profile;
- review execution mode, host concurrency limit, batch membership, distinct reviewer instances, and start/completion timestamps;
- exact phase order and one review record per phase;
- original parent/commit and current rewritten commit;
- explicit `external_fidelity_required` classification for every phase;
- reviewer prompts that reproduce the review-baseline execution manifest's typed approved-scope fields exactly, plus each prompt's exact-byte `prompt_sha256`;
- plan, boundary, contract, prompt, and findings paths;
- one main-agent disposition per finding;
- finding counts, regression-test count, validation results, final code checkpoint, and metadata commit (`self` in a completed manifest means the commit containing that exact manifest).

### `parallel-review/findings/<phase>.json`

Each fresh reviewer returns one file conforming to `assets/review-findings.schema.json`. The report is immutable reviewer evidence. The main agent does not edit the reviewer verdict to make it agree; it records acceptance, rejection, duplication, already-fixed state, or reassignment separately in the review manifest and ledger.

### `parallel-review/reviewer-prompts/<phase>.md`

Create one complete prompt from `assets/reviewer-prompt-template.md` per phase. It must include the exact target and parent, frozen final baseline, `phase-commit-reviewer` >= 1.3.0 requirement, the same `external_fidelity_required` value as the review manifest, exactly one raw JSON scope block copied from the execution manifest stored at the review baseline, full relevant context paths, contracts, phase map, validation commands, requested/actual profile, strict read-only policy, and output path. Record SHA-256 over the exact prompt bytes and dispatch only bytes matching that hash.

### `parallel-review/commit-map.md`

Record original and current commit IDs for every phase, including phases whose logical content did not change but whose hashes changed during descendant replay. Distinguish phase commits from orchestration metadata commits.

### `parallel-review/review-ledger.md`

Record reviewer dispatches, raw findings, main-agent dispositions, assigned phases, fixes, regression tests, contract changes, conflict resolutions, validation, backup refs, retained branches/worktrees, and publication gates.

## Review metadata self-reference

Do not place final rewritten commit IDs inside the same phase commits whose hashes those fields describe. After history reconstruction and pre-completion validation, set the completed review manifest's `metadata_commit` to `self` and create one separate orchestration metadata commit containing that exact manifest, the resolved old-to-new map, final evidence, and the human status update. Rerun validation from the committed tip; the validator resolves `self` to the latest commit containing the manifest and rejects an uncommitted or different working copy.
