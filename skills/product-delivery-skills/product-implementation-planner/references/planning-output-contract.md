# Planning Output Contract

## Delivery-scope metadata

In the top metadata of `00-product-description.md`, record exactly one canonical JSON object between these literal markers:

```text
<!-- delivery-scope:begin -->
{"schema_version":1,"delivery_scope_mode":"scoped change","requested_outcome":"Add account export without changing existing account workflows.","impact_cone":"Export endpoint, authorization, audit records, storage reads, API documentation, and regression tests.","preserved_behavior":["Existing account reads and writes remain compatible."],"non_goals":["Redesigning account storage."],"planned_phase_ids":["PH-001-00"],"authorized_phase_ids":["PH-001-00"],"applicable_documents":["03-interfaces-and-integrations.md","90-security-reliability-and-operations.md","91-testing-and-quality.md"],"preserved_document_sources":{"01-system-architecture.md":"docs/architecture.md remains authoritative; no topology change.","02-domain-and-data.md":"docs/data-model.md remains authoritative; export is read-only."}}
<!-- delivery-scope:end -->
```

Use one of the four lower-case modes: `full product`, `scoped change`, `modernization or migration`, or `remediation or reliability`. Keep the key set exact. `planned_phase_ids` names the phases in this delivery package; `authorized_phase_ids` is the subset approved to start. `applicable_documents` selects from `01`, `02`, `03`, `90`, and `91`; `preserved_document_sources` must cover every omitted concern document with an authoritative source or a concise reason its existing treatment remains valid. Every bounded mode requires at least one explicit `preserved_behavior` statement; the array may be empty only for `full product`. An explicit empty `authorized_phase_ids` array is valid; `non_goals` and `planned_phase_ids` are not empty. The prose sections and planning index explain this record but do not redefine it.

Planning sets that predate the canonical delivery-scope or decomposition-assessment records are not accepted through a legacy validation mode. Normalize them from repository and product evidence before validation, rerun the decomposition scenario comparison, and do not synthesize values, classifications, or scores merely to satisfy validation.

## Default directory tree

For `Full product`, create this structure and mark all five concern documents applicable. Never omit a relevant concern merely to reduce file count.

```text
docs/implementation-plan/
├── README.md
├── delivery-status.md
├── 00-product-description.md
├── 01-system-architecture.md
├── 02-domain-and-data.md
├── 03-interfaces-and-integrations.md
├── 04-external-system-evidence.md
├── external-systems/
│   └── <material-external-system>.md
├── components/
│   ├── <major-component-a>.md
│   ├── <major-component-b>.md
│   └── ...
├── 90-security-reliability-and-operations.md
├── 91-testing-and-quality.md
├── 92-delivery-roadmap.md
├── 93-implementation-units.md
└── 99-open-questions.md
```

All documents must use relative links and agree on names, IDs, boundaries, contracts, data ownership, and phase dependencies.

For a bounded mode, keep the same planning root but update or create only the artifacts needed by the approved scope and impact cone. `README.md`, `delivery-status.md`, `00-product-description.md`, `92-delivery-roadmap.md`, `93-implementation-units.md`, `99-open-questions.md`, and a component plan for every affected component are required. Create or update `01`, `02`, `03`, `90`, and `91` only when the change affects those concerns. Reuse authoritative existing architecture or operational documents by relative link when they remain valid, and identify them in the index; do not create placeholder documents or copy unaffected product design merely to resemble a full-product package. External-system evidence remains conditional on a material external dependency.

## Stable identifiers

Use stable identifiers consistently:

- functional requirement: `FR-001`;
- non-functional requirement: `NFR-001`;
- constraint: `CON-001`;
- architecture decision: `ADR-001`;
- deferred decision: `DEC-001`;
- component: `CMP-001`, `CMP-002`, or another stable numeric ID;
- component phase: `PH-001-00`, `PH-002-02`, or another component-qualified stable ID whose first numeric group matches the component;
- decomposition change scenario: `SCN-001`;
- dependency edge, when named explicitly: `DEP-001`;
- material external system: `EXT-001`;
- external behavior claim: `ECL-EXT-001-001`;
- external evidence item: `EVD-EXT-001-001`.

Never reuse an ID for a different meaning. Renaming a heading must not change its ID. Component-phase IDs are the canonical implementation-unit candidates used by the companion implementation skill.

## Global document metadata

At the top of every canonical planning document include:

- title;
- status: `Draft`, `Blocked`, or `Ready for implementation`;
- last updated date;
- source requirement IDs covered;
- related documents.

For component documents also include the component ID. For phase sections include the phase ID in the heading.

`delivery-status.md` uses its own derived-summary metadata contract below because its stage status continues beyond planning and is not a canonical planning status.

Use these labels consistently:

- **Requirement:** behavior or constraint from a source or user.
- **Decision:** a selected product or architecture choice.
- **Assumption:** an unconfirmed reversible premise tolerated for planning.
- **Deferred decision:** an unresolved choice with bounded impact and a latest responsible decision point.
- **Open question:** an unresolved item not yet accepted or classified.
- **Risk:** an uncertain condition that could harm delivery or operation.
- **Boundary candidate:** a provider-consumer guarantee that later implementation must formalize as a contract.
- **Write domain:** repository paths or artifact classes a phase is expected to own or modify.

## `README.md` — planning index

Required sections:

1. Planning status and phase-readiness statement
2. Source documents and repository evidence
3. Product summary
4. Delivery scope and impact cone
5. Goals and non-goals
6. Architecture summary
7. Major components and ownership table, including only in-scope `CMP-###` IDs for bounded work
8. System-wide delivery-phase summary, scoped to the approved change for bounded work
9. Component and phase identifier registry
10. Document index
11. Requirement-to-component-to-phase traceability summary
12. Blocking decisions, deferred gates, and highest risks
13. Implementation handoff readiness
14. How to use and maintain the plan

Use exactly one level-2 `## Planning status and phase-readiness statement` heading. Its section must contain exactly one parseable status field:

```markdown
- **Planning status:** Draft
```

Set it to `Draft`, `Blocked`, or `Ready for implementation`, explain why, and identify exactly which `PH-###-##` IDs are authorized. The human delivery-status Planning row must agree: `Draft` maps to `In progress`, `Blocked` maps to `Blocked`, and `Ready for implementation` maps to `Completed`.

## `delivery-status.md` — human operator summary

This is the one concise, cross-stage document for a human observing delivery. It is a derived navigation and status view, not a source of product scope, proof, implementation authority, or review truth. The canonical planning documents, formal-verification artifacts, manifests, ledgers, Git commits, validation results, and reviewer reports remain authoritative. When the summary disagrees with detailed evidence, correct the summary; never change evidence merely to make the summary look consistent.

At the top include these fields. `Summary type` must be exactly `Derived human-readable delivery status`, and `Authority` must begin with `Non-authoritative`:

```markdown
- **Summary type:** Derived human-readable delivery status
- **Authority:** Non-authoritative; follow the linked canonical evidence
- **Current stage:** Planning
- **Current status:** In progress
- **Last updated:** YYYY-MM-DD
- **Operator action required:** None
- **Related documents:** [Planning index](README.md)
```

Set **Current stage** to `Planning`, `Formal verification`, `Implementation`, `Review`, or `Delivery complete`. Set **Current status** to one of the explicit stage states below; when the current stage has a table row, the two statuses must match. Replace the example status, action, date, and links with current values. **Last updated** must be a valid ISO-8601 calendar date in `YYYY-MM-DD` form.

Required sections:

1. Scope at a glance
2. Stage status
3. What changed
4. Decisions and operator actions
5. Verification, implementation, and review summary
6. Risks and blockers
7. Evidence links

Use exactly one level-2 `## Stage status` heading. Under it, keep exactly one current row for each top-level stage, with non-empty outcome and detailed-evidence cells:

```markdown
| Stage | Status | Outcome | Detailed evidence |
|---|---|---|---|
| Planning | <status> | <one-sentence outcome> | <links> |
| Formal verification | <status> | <one-sentence outcome> | <links> |
| Implementation | <status> | <one-sentence outcome> | <links> |
| Review | <status> | <one-sentence outcome> | <links> |
```

Use explicit states such as `Not started`, `Not requested`, `In progress`, `Blocked`, `Completed`, `Completed with limitations`, `Declined`, or `Skipped`; do not use vague percentages or “mostly done.” Summarize only material changes since the previous stage update. Name any decision the operator must make, and write `None` when no action is required. Link to stable IDs and detailed evidence instead of copying requirements, manifests, logs, prompts, traces, or finding reports. Keep the document to roughly one human-readable page; the validator warns when it exceeds 1,500 words.

The main orchestrator for the active top-level stage owns this file. Implementor and reviewer subagents treat it as read-only. Update it when planning completes or blocks, formal verification converges or blocks, implementation reaches green or blocks, and review completes, is declined, or blocks. After every such update, explicitly tell the operator that the human status summary was updated, give the path, state the current stage/status, and say whether operator action is required.

## `00-product-description.md`

Create this before architecture documents. It is the normalized product contract whether the source began as a formal specification, rough idea, or user interview.

Its top metadata must include the canonical delivery-scope block. For a bounded mode, describe the requested change, current and target behavior, impact cone, preserved behavior, and explicit non-goals; requirements and acceptance criteria are scoped to that change rather than copied from the entire product.

Required sections:

1. Document purpose and source
2. Product vision and problem
3. Outcomes and success measures
4. Users, actors, and roles
5. Product surfaces and operating model
6. Delivery scope and release boundary
7. Primary and exceptional workflows
8. Functional requirements
9. Non-functional requirements
10. Business rules and invariants
11. Constraints and dependencies
12. Principal decision register
13. Assumptions and deferred decisions
14. Explicit non-goals
15. Acceptance model
16. Change history

Every requirement must be testable or have a clear validation method.

The principal decision register should include decision ID, area, status, selected option or open options, rationale or default, impact radius, owner when known, and latest responsible decision point.

## `01-system-architecture.md`

Required sections:

1. Architecture drivers
2. System context
3. Decomposition and abstraction choices by axis
4. Major components, stable IDs, and responsibility boundaries
5. Dependency direction
6. Critical runtime flows
7. Hosting, deployment topology, and environments
8. Trust boundaries and security overview
9. Reliability and consistency model
10. Scalability and cost model
11. Architecture decisions and alternatives
12. Deferred architecture decisions and gates
13. Evolution triggers

Include Mermaid system-context and component/deployment diagrams for non-trivial products. Include sequence diagrams when ordering, ownership, or failure behavior would otherwise remain unclear.

When this document is applicable, explain the selected domain partitioning, dependency topology, state and consistency model, code organization, deployment topology, and internal programming model. Link these choices to the canonical decomposition assessment rather than collapsing them into one pattern label.

## `02-domain-and-data.md`

Required sections:

1. Domain model and terminology
2. Entity and value-object lifecycle
3. Business invariants
4. Data ownership by component ID
5. Storage choices and rationale
6. Logical schemas and important indexes
7. Transaction and consistency boundaries
8. Caching and derived data
9. Data retention, deletion, export, and privacy
10. Migration, backfill, reconciliation, and archival
11. Backup, restore, recovery-point, and recovery-time objectives where relevant
12. Data risks and deferred decisions

Do not substitute a raw table list for a domain model.

Data ownership and authorized writers must agree with the canonical decomposition assessment in `93-implementation-units.md`.

## `03-interfaces-and-integrations.md`

Required sections:

1. Internal synchronous interfaces
2. Events, jobs, queues, and workflows
3. External integrations
4. Authentication and authorization at each boundary
5. Request, response, event, and error contracts
6. Idempotency, retries, timeouts, ordering, and duplicate behavior
7. Versioning and compatibility
8. Rate limits, quotas, and backpressure
9. Degraded-mode and reconciliation behavior
10. Integration test and sandbox strategy
11. Ownership and support model
12. Deferred interface decisions and compatibility boundaries
13. Boundary-candidate catalog

Every internal boundary candidate must name its provider `CMP-###`, consumer `CMP-###`, expected availability phase, compatibility rule, and source requirements. Exact executable contracts are produced only after implementation approval.

## `components/<component>.md`

Create one file for every in-scope component. For a full product this means every major component; for bounded work it means affected components and necessary shared foundations, using existing component boundaries when they remain sound. At the top include:

```markdown
- Component ID: `CMP-001`
```

Required sections:

1. Purpose and scope
2. Responsibilities
3. Explicit non-responsibilities
4. Architecture and internal modules
5. Dependencies and public contracts
6. Data and state ownership
7. Security and privacy
8. Reliability and failure modes
9. Observability and operational controls
10. Test strategy
11. Rollout, migration, rollback, and decommissioning
12. Phased implementation
13. Risks and open decisions

Under **Phased implementation**, use at least two phase headings for full-product or multi-stage work. A bounded change may use one phase when the document explains why it is an atomic reviewable increment:

```markdown
### PH-001-00 — Descriptive outcome

#### Atomicity rationale

<Required when this is the only planned phase in an in-scope component; explain why it is one independently reviewable increment.>

#### Objective

#### Prerequisites

#### In scope

#### Out of scope

#### Work

#### Deliverables

#### Dependencies

#### Boundary inputs

#### Boundary outputs

#### Expected write domains

#### Preliminary parallelization

#### Validation

#### Operational and migration work

#### Exit criteria

#### Risks and deferred work
```

Rules for phase sections:

- `Dependencies` must cite `PH-###-##`, `CMP-###`, and `DEC-...` IDs rather than vague prose.
- `Boundary inputs` must identify incoming guarantees, provider phase IDs, dependency type, and the concrete contract kind that could freeze the reliance.
- `Boundary outputs` must identify the guarantees, interfaces, schemas, symbols, behaviors, or artifacts later units may consume.
- `Expected write domains` must list at least one repository-relative path or future path pattern as a Markdown bullet whose first value is backticked, for example ``- `src/accounts/**` ``. Use likely existing paths when the repository exists; for greenfield work, use the planned module or artifact location rather than an unparseable artifact-class label.
- `Preliminary parallelization` must classify the phase as independent, contract-bound, implementation-bound, or decision-gated, explain why, and identify shared files, schemas, generated artifacts, global configuration, or semantic discovery that requires serialization.
- A bounded component with one planned phase must include a non-empty `Atomicity rationale`; the validator ignores unrelated historical phases and component plans outside `planned_phase_ids`.
- Tasks must name the artifact, capability, contract, or operational outcome being created.

## `90-security-reliability-and-operations.md`

Required sections:

1. Threat model and trust boundaries
2. Identity, authentication, and session model
3. Authorization and tenant isolation
4. Data classification, encryption, privacy, and audit
5. Abuse prevention and rate limiting
6. Dependency and supply-chain security
7. Reliability targets and failure budgets
8. Timeout, retry, idempotency, and backpressure standards
9. Backup, restore, disaster recovery, and business continuity
10. Logging, metrics, traces, audit records, dashboards, and alerts
11. Runbooks, support tooling, incident response, and ownership
12. Hosting-model-specific operational responsibilities
13. Production-readiness gates

Tie controls to component and phase IDs.

## `91-testing-and-quality.md`

Required sections:

1. Quality goals and release gates
2. Unit test strategy
3. Integration test strategy
4. Contract test strategy
5. End-to-end test strategy
6. Security test strategy
7. Accessibility and usability validation
8. Performance and capacity test strategy
9. Resilience, failure-injection, and recovery testing
10. Migration, backup/restore, and rollback testing
11. Test data and environment strategy
12. Continuous-integration quality gates and ownership
13. Requirement coverage approach
14. Decision-gate validation
15. Parallel-work contract validation

Define which tests block merge, deployment, phase completion, and launch. Identify where executable contract tests or test doubles will be needed for isolated worktree implementation.

## `92-delivery-roadmap.md`

Required sections:

1. Delivery principles
2. System-wide phases
3. Component and phase identifier registry
4. Cross-component dependency matrix
5. Component-phase dependency DAG
6. Dependency-type legend and rationale
7. Decision-gate schedule
8. Critical path
9. Candidate parallel waves
10. Hard sequential constraints
11. Milestones and objective exit gates
12. Environment and infrastructure sequencing
13. Data and integration migration sequencing
14. Release, rollout, rollback, and launch plan
15. Post-launch stabilization and ownership transfer
16. Decommissioning and cleanup
17. Risks, contingency paths, and decision deadlines

Every dependency must identify provider phase, consumer phase, reason, dependency type, boundary owner, and the concrete contract kind when contract-bound. The DAG must be acyclic. Candidate parallel waves may not contain a known implementation-bound edge between members. Use phase number only as a presentation aid; dependency order is authoritative.

## `93-implementation-units.md`

This document is the direct handoff input to `parallel-plan-implementation`. It does not contain final boundary contracts; it provides enough evidence for that skill to create them without re-inventing the plan.

Required sections:

1. Handoff status and authorized phases
2. Stable component and phase catalog
3. Decomposition decision and change-scenario analysis
4. Candidate execution units
5. Dependency edges
6. Provider-consumer boundary candidates
7. Expected write-domain ownership
8. Shared artifacts and conflict hotspots
9. Contract artifacts likely to be materialized
10. Parallelization candidates
11. Mandatory serialization constraints
12. Decision gates and excluded units
13. Suggested integration order
14. Handoff validation checklist

Under **Decomposition decision and change-scenario analysis**, include exactly one canonical `decomposition-assessment` JSON block using the markers, keys, enumerations, and conditional requirements in `references/decomposition-and-abstraction-selection.md`. The block is the machine-readable handoff for selected axes, affected-subsystem classifications, data writers, representative scenarios, and candidate measurements. Explain consequential choices and rejected alternatives in prose without redefining the record.

For each candidate execution unit include:

- phase ID and component ID;
- source component-plan file and heading;
- requirements delivered;
- prerequisites and dependency phase IDs;
- incoming and outgoing boundary candidates;
- expected write domains;
- shared paths or artifacts;
- whether it appears contract-parallelizable, wave-parallelizable, or sequential;
- reason for that classification;
- tests and exit criteria.

Do not claim a unit is safely parallelizable merely because it is in a different component. Shared database schemas, generated clients, root configuration, migrations, and cross-cutting abstractions can still require serialization.

## `99-open-questions.md`

Required sections:

1. Blocking product questions
2. Blocking architecture questions
3. Deferred decision gates
4. Non-blocking questions
5. Authorized assumptions
6. Decision log

For each item include ID, classification, owner when known, why it matters, options, recommendation, affected requirements/components/phases, safe work, latest responsible decision point, consequence of missing the gate, and status.

## Traceability and handoff requirements

The planning set must make it possible to answer:

- Which component and phase implement a requirement?
- Which tests validate it?
- Which interface, data, security, and operational controls apply?
- What exact earlier phase does a later phase depend on?
- What guarantee is expected across that dependency?
- Which repository areas are expected to be touched?
- Can that dependency be isolated by a stable contract, or must work be serialized?
- Which decomposition axes were selected, what repository or product evidence supports them, and how did each candidate perform against the same representative changes?
- Does any implementation unit write a persistent resource outside the data-owner registry or its explicit coordination mechanism?
- Which decision gates block each unit?
- What order is safe for integration?

Prefer concise traceability tables and links over copying full requirement text repeatedly.
