# Decomposition and Abstraction Selection

Use this reference when selecting or changing component boundaries, dependency structure, state ownership, or an internal abstraction style. Choose each concern on its own axis; do not treat OOP, FP, Clean Architecture, GRASP, DDD, vertical slices, and services as interchangeable alternatives.

## Decision axes

| Axis | Representative choices |
|---|---|
| Domain partitioning | capability, bounded context, workflow, resource, invariant or data owner, pipeline stage |
| Dependency topology | layered, ports and adapters, plugin, pipeline, event-driven |
| State and consistency | current state or event history, strong or eventual consistency, snapshot or log, transaction ownership |
| Code organization | vertical feature slices, horizontal technical layers, packages, modules, crates |
| Deployment topology | modular monolith, service, worker, function, embedded process |
| Internal programming model | object-oriented, functional, actor or process based, data-oriented, procedural |

Responsibility assignment, information locality, cohesion, and coupling evaluate choices across these axes; they are not another style to select. A design may combine choices from several rows.

## Existing-code path

Infer the architecture of each affected subsystem from repository evidence rather than classifying the repository as one homogeneous design. Inspect module and package graphs, dependency direction, public extension seams, invariant and data ownership, state and effect handling, runtime processes, deployment units, tests, and recurring change patterns. Distinguish documented intent from observed structure.

Classify every affected subsystem with exactly one value:

- `coherent-compatible`: extend its established architecture and idioms;
- `defective-but-compatible`: preserve the boundary, isolate the new work, and keep unrelated remediation outside scope;
- `incompatible-with-change`: authorize a scoped architecture change with coexistence, migration, and rollback;
- `no-discernible-local-architecture`: create only a boundary local to the approved change and do not present it as a repository-wide architecture.

One impact cone may contain subsystems with different classifications. Do not use a global majority style to override a locally coherent subsystem.

## Greenfield path

Let product shape influence the initial decomposition before applying a generic architecture pattern. Rule-heavy domains often benefit from capability and invariant ownership; interactive products often benefit from vertical feature slices; data-processing systems may fit typed pipelines; extensible tools may fit commands and plugins. Start with the least complex deployment topology that satisfies the requirements, normally explicit modules in a modular monolith, and extract services only for justified operational boundaries.

## Language and ecosystem constraints

Domain and ownership evidence usually select components; language idioms usually select their realization. Treat that as a default, not a fiction. When a language or runtime constrains expressible boundaries—such as import-cycle rules, ownership and borrowing, supervision trees, effect systems, framework lifecycle, or generated-code boundaries—record the constraint and let it influence dependency or component topology.

Do not translate a familiar paradigm mechanically. A Haskell component may use modules, algebraic data types, pure transitions, and explicit effects; a Java component may still use immutable data and a functional core. Preserve the selected domain and ownership semantics while expressing them idiomatically.

## Selection hierarchy

Apply these as near-gates:

1. keep each business invariant under one authoritative owner;
2. give each persistent resource one authoritative write owner, with additional writers only through an explicit migration or serialization mechanism;
3. keep operations requiring one transaction inside a valid transaction boundary.

Compare surviving designs primarily by:

- change locality: common changes remain inside few components and contracts;
- coupling: boundaries do not create unnecessary coordination or chat;
- cohesion: grouped behavior changes for related reasons.

Use testability, team capability, evolution cost, ecosystem fit, and implementation parallelism as tiebreakers. Never distort the product architecture merely to create more parallel workers.

## Change-scenario comparison

Make representative change scenarios the main comparison evidence. Include ordinary changes plus relevant rule, integration, data, failure, or scale changes. For each candidate, record how many components and contracts each scenario crosses and whether that blast radius is acceptable. Reject a selected design when a small likely change requires broad coordination without a requirement that justifies it.

For `reuse`, use two to six scenarios and at least one candidate. For `local-extension`, `boundary-change`, or `greenfield`, use four to six scenarios and at least two candidates. Every alternative must differ from the selected candidate on a named decision axis and be measured against the identical scenario set; a prose strawman is not an alternative.

This moves a signal already found during implementation—path conflicts and implementation-bound edges collapsing candidate waves—into planning, where changing the decomposition is cheaper.

## Canonical handoff record

In `93-implementation-units.md`, place exactly one JSON object between these markers:

```text
<!-- decomposition-assessment:begin -->
{"schema_version":1,"context":"existing","decision_kind":"local-extension","axes":{"domain_partitioning":"Existing account capability boundary.","dependency_topology":"Feature slice behind the account module API.","state_and_consistency":"Current-state store with one transactional writer.","code_organization":"Repository-standard feature modules.","deployment_topology":"Existing modular monolith.","internal_programming_model":"Language-idiomatic immutable values and services."},"language_constraints":["The package graph must remain acyclic."],"affected_subsystems":[{"name":"account-core","classification":"coherent-compatible","architecture_scope":"existing-subsystem","evidence":["src/accounts/","docs/architecture.md"],"response":"Extend the existing account module through its public API.","coexistence":null,"migration":null,"rollback":null}],"data_ownership":[{"resource":"account-store","owner_component_id":"CMP-001","authorized_writer_component_ids":["CMP-001"],"write_paths":["src/accounts/storage/**"],"coordination":null}],"scenarios":[{"id":"SCN-001","description":"Add another account export field."},{"id":"SCN-002","description":"Change export authorization."},{"id":"SCN-003","description":"Replace the export sink."},{"id":"SCN-004","description":"Reconcile a partially completed export."}],"candidates":[{"name":"selected-feature-slice","selected":true,"differs_on_axes":[],"scenario_impacts":[{"scenario_id":"SCN-001","components_crossed":1,"contracts_crossed":0,"acceptable":true,"rationale":"The change remains in the account module."},{"scenario_id":"SCN-002","components_crossed":1,"contracts_crossed":0,"acceptable":true,"rationale":"Authorization remains owned by the account capability."},{"scenario_id":"SCN-003","components_crossed":2,"contracts_crossed":1,"acceptable":true,"rationale":"The sink changes behind one port."},{"scenario_id":"SCN-004","components_crossed":1,"contracts_crossed":0,"acceptable":true,"rationale":"Reconciliation shares the account transaction owner."}]},{"name":"new-export-service","selected":false,"differs_on_axes":["deployment_topology","dependency_topology"],"scenario_impacts":[{"scenario_id":"SCN-001","components_crossed":2,"contracts_crossed":1,"acceptable":false,"rationale":"A small field change crosses a new service boundary."},{"scenario_id":"SCN-002","components_crossed":2,"contracts_crossed":1,"acceptable":false,"rationale":"Authorization semantics would be duplicated across services."},{"scenario_id":"SCN-003","components_crossed":2,"contracts_crossed":2,"acceptable":true,"rationale":"The sink is isolated but adds another contract."},{"scenario_id":"SCN-004","components_crossed":2,"contracts_crossed":2,"acceptable":false,"rationale":"Reconciliation becomes distributed."}]}]}
<!-- decomposition-assessment:end -->
```

Keep every shown key. Use `context` values `existing` or `greenfield`; use `decision_kind` values `reuse`, `local-extension`, `boundary-change`, or `greenfield`. For greenfield work, use `decision_kind: greenfield` and an empty `affected_subsystems` array. For existing work, record at least one affected subsystem.

`architecture_scope` is `existing-subsystem` for compatible classifications, `scoped-migration` for `incompatible-with-change`, and `local-to-change` for `no-discernible-local-architecture`. An incompatible subsystem requires non-empty coexistence, migration, and rollback statements. A local boundary must remain local to the approved change.

Every data-ownership record names repository-relative write paths. The owner must appear among the authorized writers. Multiple authorized writer components require a non-empty `coordination` mechanism. An empty data-ownership array is valid when the scope owns no persistent resource.

The selected candidate must mark every scenario acceptable. Record consequential selection in the architecture decision register; explain system-wide implications in `01-system-architecture.md` when that document is applicable. The implementation ledger records later discoveries and approved deviations, not the original selection rationale.

## Replanning gate

During boundary materialization, compare actual unit write paths and implementation-bound edges with this record. Stop and amend the plan when another component would write a declared resource without authorization, an assumed contract cannot be frozen, or actual path and dependency evidence invalidates the selected scenario analysis. Serialization may resolve an execution collision; it must not conceal incorrect domain or data ownership.
