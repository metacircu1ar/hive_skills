# Parallel Implementation Execution Workflow

## Purpose

This reference contains the detailed procedures for Implementation Phases 0–8. Read it completely before changing product code, then follow its phases in order. The main `SKILL.md` remains authoritative for approval gates, model policy, non-negotiable rules, review, and completion.

### Implementation Phase 0 — Preflight and safe baseline

1. Read `references/agent-model-policy.md` and `references/worktree-and-worker-protocol.md`.
2. Confirm requested and actual main/implementor profiles. Stop before code execution when the required profile is unavailable and no user-approved substitution exists.
3. Confirm that the repository is a Git repository and identify the current `HEAD`, branch, remotes, worktree list, repository rules, and quality commands.
4. Inspect uncommitted and untracked changes.
   - When they overlap planned paths, influenced the plan, or are otherwise required, do not exclude them silently. Obtain an explicit inclusion decision or safe snapshot strategy.
   - When they are unrelated, leave the user's checkout untouched and create a separate integration worktree from the committed baseline.
5. Confirm that the planning documents and `docs/implementation-plan/delivery-status.md` are available inside the integration baseline. Read the latter only as a derived human navigation aid; canonical plans and evidence control. Commit only planning and orchestration documents on the dedicated integration branch; never sweep unrelated changes into that commit.
6. Run the existing baseline build and tests. Record pre-existing failures rather than attributing them to workers.
7. Run:

```bash
python3 <planner-skill-root>/scripts/validate_plan.py <repository-root>
```

8. Verify that every approved unit has a stable phase ID, prerequisites, boundary inputs, boundary outputs, validation, and exit criteria.
9. Read the canonical decomposition assessment in `93-implementation-units.md` from the planning commit. Verify its selected candidate, per-subsystem classifications, scenario set, and data-writer registry rather than inferring them from mutable worktree prose.
10. Establish a dedicated integration branch and worktree. Record its baseline commit without assuming a fixed branch name.
11. Stop before worker launch when Git, worktrees, approved plans, decomposition assessment, or required repository tooling are unavailable.

### Implementation Phase 1 — Reconstruct and verify the dependency graph

Read every component plan in the approved scope, `92-delivery-roadmap.md`, and the baseline documents needed to understand affected dependencies rather than trusting the roadmap summary alone. Do not add an implementation unit merely because impact analysis found unrelated work outside the approved scope.

Use actual module, package, build, deployment, and path dependencies to test the selected decomposition. When path conflicts or implementation-bound edges are materially worse than the recorded scenario analysis predicted, stop and amend the plan. Do not use boundary generation as permission to substitute a preferred OOP, FP, layered, clean, service, or other architecture.

For every approved component phase, create one implementation unit and verify:

- unit ID and component ID;
- exact plan section;
- requirements delivered;
- predecessor and consumer units;
- open decision gates;
- dependency type for every edge;
- shared repositories, modules, schemas, generated outputs, migrations, manifests, lockfiles, and infrastructure resources;
- expected validation and exit criteria.

For every write-capable owned, shared, or generated path, compare the unit's component ID with the decomposition assessment's data-writer registry. Multiple phases of one authorized writer component are valid. A different component may write an overlapping declared resource only when it is named as an authorized writer and the execution waves or shared-path owner registry enforce the recorded migration, serialization, or reconciliation mechanism.

Use these dependency types:

- **Independent:** the unit needs no output from another implementation unit.
- **Contract-bound:** the unit needs only a frozen public contract and contract-support artifacts.
- **Implementation-bound:** the unit needs integrated code, generated output, schema state, migration state, or observed behavior from a predecessor.
- **Decision-gated:** a named decision must close first.

Use the strongest active constraint as the unit classification: `Decision-gated` over `Implementation-bound`, `Implementation-bound` over `Contract-bound`, and `Contract-bound` over `Independent`. Keep every individual predecessor edge classified separately.

Correct unsafe preliminary classifications. Build an acyclic graph. When a cycle exists, redesign the boundary, introduce a contract-foundation unit, or serialize the cycle; do not hide it.

### Implementation Phase 2 — Produce boundary documents and execution artifacts

Read `references/boundary-contract-standard.md` and `references/implementation-output-contract.md`.

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

Create exactly one boundary document for each component plan in the approved scope. Inside it, create a dedicated section for every included phase.

Each phase boundary must specify:

- inbound guarantees the worker may rely upon;
- outbound guarantees the phase must deliver;
- exact canonical contract IDs and paths;
- module paths, exported symbols, signatures, endpoint operations, event names, schemas, file formats, or command interfaces when applicable;
- behavioral semantics, including validation, errors, side effects, transactions, consistency, idempotency, ordering, concurrency, timeouts, and compatibility where relevant;
- data ownership and migration expectations;
- the applicable declared persistent resource, owner component, authorized writers, and coordination mechanism;
- cross-component provider and consumer responsibilities;
- deterministic mocks, fakes, generated clients, fixtures, or contract tests available before provider implementation exists;
- owned, shared, generated, and forbidden paths;
- required validation commands and exit evidence;
- decision gates and assumptions the worker must not make;
- integration prerequisites and the phase's obligations to later units.

Boundary documents describe reliance, not private implementation. Link to canonical schemas or declarations rather than copying definitions into multiple sources of truth.

Create schema-v2 `execution-manifest.json` from `assets/execution-manifest.schema.json`. Copy its five typed approved-scope fields from the canonical delivery-scope block in `00-product-description.md` at `integration.planning_commit`; set `phase_ids` to executable units only, and verify each against that immutable plan's authorization registry. It is the machine-readable source for worker assignment, waves, branches, worktrees, paths, dependencies, contracts, validation, and status. Copy the five fields into exactly one approved-scope JSON block in every worker prompt.

Reserve `docs/implementation-plan/delivery-status.md` for the main orchestrator. Do not include it in any worker's owned, shared, or generated paths. Workers may receive a link for orientation but never as scope or contract authority.

### Implementation Phase 3 — Freeze the contract baseline

Boundary prose is not enough for parallel coding. In the integration worktree, materialize the smallest implementation-neutral contract baseline required by the first parallel waves.

Applicable artifacts include:

- package or module skeletons and public exports;
- interface, protocol, abstract type, or declaration files;
- OpenAPI, GraphQL, Protocol Buffers, JSON Schema, AsyncAPI, event, or file-format definitions;
- generated clients or types produced deterministically from canonical schemas;
- contract-test suites;
- mock servers, adapters, fakes, fixtures, or test doubles;
- stable configuration keys and environment contracts;
- migration ownership and sequencing declarations.

Rules:

1. Do not hide full feature implementation inside the contract baseline.
2. Give every contract a stable `CTR-###` ID, owner, consumers, canonical path, compatibility rule, and status.
3. Compile, validate, or test every materialized contract.
4. When a consumer cannot build or test against the contract baseline, either add a legitimate contract-support artifact or reclassify the dependency as implementation-bound.
5. Commit the boundary documents, worker prompts, materialized contracts, and a manifest whose unresolved base-commit fields are `pending`. A Git commit cannot contain its own hash, so never attempt self-referential commit metadata.
6. Resolve the resulting commit as the frozen contract or launch baseline. Worker branches are created from that exact commit. Immediately afterward, update the integration-branch manifest and ledger with the resolved hash in a separate orchestration commit.

Run the bundled validator:

```bash
python3 <skill-root>/scripts/validate_parallel_plan.py <repository-root>
```

Fix all errors before launching workers. The validator may accept `pending` only for future or not-yet-dispatched wave bases; rerun it after dispatch metadata is recorded.

### Implementation Phase 4 — Form safe parallel waves

A wave is a set of units that may run concurrently from the same integration checkpoint.

A unit is eligible when:

- every decision gate due before it is closed;
- every implementation-bound predecessor is integrated into its base checkpoint;
- every contract-bound predecessor is represented by a frozen `CTR-###` contract and support artifacts;
- no other unit in the wave owns an overlapping write path;
- shared manifests, lockfiles, migrations, generated outputs, and infrastructure resources have a single writer or an explicit serialized reconciliation owner;
- required tooling and validation can run in its worktree.

Prefer the maximum safe wave, not the largest imaginable wave. A unit may be moved to a later wave whenever isolation would be artificial or costly.

Update `execution-manifest.json`, `dependency-graph.md`, and `integration-order.md` with the verified waves and base commits.

### Implementation Phase 5 — Create worktrees and dispatch workers

For the next ready wave:

1. Resolve the exact launch baseline commit containing the frozen contracts, boundaries, and worker prompts.
2. Create one unique branch and Git worktree per unit from that commit.
3. Update the integration-branch manifest and ledger with the resolved base commit, branch, and worktree in a separate orchestration commit; do not try to make the launch baseline record its own hash.
4. Place worktrees outside the integration working tree by default. Do not add worktree directories to committed product configuration merely for orchestration convenience.
5. Verify that one worker prompt generated from `assets/worker-prompt-template.md` and the matching schema-v2 execution manifest are present in the launch baseline for each unit. Validate their scope block from that commit, not a mutable worktree copy; supplement the runtime task message only with the resolved base commit and worktree path.
6. Give each worker only the context it needs:
   - the unique typed approved-scope JSON block copied from the execution manifest;
   - component plan and exact phase section;
   - component boundary document and exact phase section;
   - canonical contract files;
   - relevant architecture, domain, interface, security, testing, and repository-rule documents;
   - owned and forbidden paths;
   - validation commands;
   - required result format.
7. Spawn one fresh `gpt-5.6-terra` / `xhigh` implementor per eligible unit when the host supports subagents. Give it the generated prompt, complete relevant context, exact worktree, branch, and launch commit. Record the actual runtime profile.
8. Wait for every worker in the wave to return before integrating that wave.

A worker must:

- stay within its unit and worktree;
- implement production-quality code, tests, migrations, observability, and documentation required by the phase;
- consume frozen contracts exactly;
- avoid editing plans, boundary documents, canonical contracts, unrelated components, or another unit's paths;
- run its required checks;
- commit its work on its branch;
- return commit IDs, changed paths, test evidence, contract compliance, deviations, and blockers;
- return `CONTRACT_BLOCKER` without speculative implementation when the approved-scope block or a required guarantee is missing, malformed, duplicated, or contradictory.

When the host lacks parallel-agent support, stop after boundary and manifest generation and report that true parallel execution cannot be performed in that environment. Do not silently execute the worker list sequentially unless the user explicitly authorizes a sequential fallback.

### Implementation Phase 6 — Review and integrate one phase at a time

Read `references/integration-protocol.md` before integration.

Integrate in topological order from earliest prerequisites to latest dependents. Within one component, preserve phase order. Within a dependency-equivalent wave, use a deterministic order recorded in `integration-order.md`.

For each completed unit:

1. verify its branch, base commit, commit IDs, clean worktree, and reported status;
2. inspect the full diff for scope, quality, security, data ownership, contract compliance, and forbidden-path changes;
3. reject or repair undocumented contract drift before merge;
4. apply the unit to the integration branch using the repository's preferred policy;
5. resolve conflicts according to canonical contracts and architecture, never by choosing whichever side is easier;
6. run contract tests, the unit's checks, affected-component checks, migrations or generated-artifact checks, and required repository quality gates;
7. fix integration issues in the integration worktree;
8. create or amend one dedicated logical integration commit for the phase, such as `feat(PH-001-01): deliver <outcome>`; keep the reviewable phase chain linear when repository policy permits and exclude orchestration-only commits from phase mapping;
9. record the commit, validation evidence, deviations, and remaining risks in `implementation-ledger.md` and the manifest.

Do not integrate a dependent unit before its implementation-bound predecessors, even when the dependent worker finished first.

After a wave is integrated and validated, record the new checkpoint, re-evaluate downstream boundaries, and launch the next eligible wave.

### Implementation Phase 7 — Contract change control

A boundary may change only when implementation reveals a genuine defect, contradiction, or missing requirement.

When change is necessary:

1. stop integration of affected consumers;
2. identify the contract owner and affected units;
3. update the canonical contract, boundary document, execution manifest, tests, and architecture decision together;
4. increment the contract version or compatibility marker when appropriate;
5. determine which completed or active workers must rebase, revise, or restart;
6. validate the updated contract baseline;
7. commit the change-control update before resuming.

Do not patch providers and consumers independently until tests happen to pass. That defeats the boundary model.

### Implementation Phase 8 — Final implementation verification

After all approved units are integrated:

1. run the complete repository build, test, static-analysis, formatting, security, migration, generated-code, and packaging checks applicable to the plan as regression gates, not as authorization to expand the change;
2. run planned end-to-end, contract, resilience, accessibility, performance, backup/restore, and rollout checks feasible in the environment;
3. verify requirement, component, phase, contract, and one-commit-per-phase traceability;
4. verify every phase commit exists in deterministic integration order and contains its phase ID;
5. update the implementation ledger and manifest, including requested and actual profiles;
6. preserve evidence of pre-existing failures and approved deviations;
7. clean worker worktrees only when no unique work can be lost;
8. retain branches with unmerged or disputed work;
9. update `docs/implementation-plan/delivery-status.md`: set the **Implementation** row and current status, summarize completed phases and material deviations, name the review decision as the next operator action, and link to the execution manifest, implementation ledger, phase commits, and final validation evidence;
10. preserve the planning and formal-verification rows, keep the summary derived and concise, and do not copy worker prompts, logs, or full manifests;
11. rerun the planner and parallel-plan validators against the current repository so the updated orchestration package and human-status structure are checked;
12. commit the final ledger, manifest, and human-status update in a separate orchestration metadata commit; never amend a phase commit merely to carry the summary;
13. verify the branch is clean, buildable, and passing, then freeze that commit as the potential review baseline;
14. explicitly tell the operator that the human delivery status was updated, give its path, state the implementation status, and say that the review decision is required;
15. do not deploy or perform live migration without separate authorization.

Do not offer review until the repository is clean and every required implementation check passes.

If implementation stops blocked before Phase 8 can complete and control returns to the operator, update the same document with the blocker, safe completed work, detailed evidence links, and required operator action. Commit it with the corresponding orchestration records when the workflow is already committing delivery metadata; never sweep unrelated work into that commit. Then explicitly tell the operator where the summary is.
