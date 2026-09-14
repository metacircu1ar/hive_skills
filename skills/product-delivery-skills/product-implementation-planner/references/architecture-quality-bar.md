# Architecture Quality Bar

Use this as a mandatory review checklist. Apply only the items relevant to the product, but never omit a relevant concern silently.

## 1. Right-sized architecture

- Choose the least complex architecture that satisfies the requirements and expected scale.
- Prefer clear module boundaries before separate deployable services.
- Use microservices only when independent scaling, ownership, deployment, isolation, or regulatory boundaries justify their operational cost.
- Use event-driven designs only when asynchronous decoupling, durability, fan-out, or workflow requirements justify them.
- Record scaling triggers that would cause the architecture to evolve.

## 2. Hosting and operating model

- State who deploys, operates, upgrades, monitors, backs up, and supports the product.
- Distinguish shared managed service, dedicated managed deployment, customer-managed or on-premises deployment, hybrid deployment, and local-only operation when relevant.
- Tie topology, trust boundaries, storage, telemetry, upgrade delivery, support tooling, and disaster recovery to the chosen operating model.
- Treat customer-managed and disconnected environments as distinct operational products when their requirements materially differ.
- Do not claim cloud or vendor portability unless dependencies, data movement, configuration, observability, and operational procedures support it.
- When the operating model is deferred, isolate provider- or topology-specific commitments, define the invariant contracts, and establish a decision gate before dependent work.

## 3. Boundaries and ownership

- Every component has a clear responsibility and explicit non-responsibilities.
- Each business invariant has one authoritative owner.
- Each persistent data set has one authoritative write owner.
- Components do not reach into another component's private database or internal state.
- Dependency direction is intentional and free of cycles where practical.
- Shared libraries contain stable cross-cutting primitives, not hidden domain coupling.

## 4. Contracts

- Interfaces, events, files, callbacks, and external integration contracts are explicit.
- Validation, error models, pagination, filtering, ordering, concurrency behavior, and idempotency are defined where relevant.
- Versioning and backward-compatibility rules are defined.
- Contract evolution and deprecation are planned.
- Critical flows have sequence diagrams or equivalent step-by-step interaction descriptions.

## 5. Domain and data design

- Entities, value objects, relationships, lifecycle states, and invariants are defined.
- Transaction boundaries follow business invariants.
- Consistency requirements are explicit rather than accidental.
- Schema migrations are forward-safe, observable, and reversible or compensatable.
- Backfills, reconciliation, retention, deletion, export, archival, and legal-hold needs are planned.
- Indexing and query patterns are derived from access patterns.
- Cache ownership, invalidation, staleness, and fallback behavior are specified.
- Files and media have lifecycle, validation, scanning, access-control, and cleanup rules.

## 6. Security and privacy

- Trust boundaries and threat assumptions are visible.
- Authentication and authorization are separate concerns and both are designed.
- Authorization is enforced server-side at the resource or action boundary.
- Secrets are stored and rotated through an appropriate secret-management mechanism.
- Sensitive data is minimized, classified, encrypted where required, redacted from logs, and governed throughout its lifecycle.
- Input validation, output encoding, request forgery, injection, file-upload, rate-limit, abuse, and account-recovery risks are addressed where relevant.
- Administrative actions and sensitive data access are auditable.
- Dependency, image, and supply-chain controls are included.

## 7. Reliability and failure handling

- Timeouts exist on remote calls.
- Retries are bounded, backoff-aware, and limited to retry-safe operations.
- Side-effecting operations are idempotent or protected against duplication.
- Queues have capacity limits, retry policy, dead-letter handling, monitoring, and replay procedures.
- Partial failure and degraded-mode behavior are specified.
- Reconciliation exists where two systems can diverge.
- Backups, restore tests, recovery-point objectives, recovery-time objectives, and disaster-recovery responsibilities are defined when relevant.
- Single points of failure are accepted only when their risk is explicit and proportionate.

## 8. Client architecture and user experience

- Navigation, state ownership, server-state caching, local state, and persistence are separated deliberately.
- Loading, empty, error, permission-denied, offline, stale-data, conflict, and recovery states are designed.
- Accessibility is built into component and test strategy.
- Client validation improves usability but never replaces server enforcement.
- Interface compatibility, feature rollout, telemetry, crash reporting, and update strategy are covered.
- Sensitive client storage and transport are minimized and protected.

## 9. Performance, scale, and cost

- Capacity assumptions and peak behavior are stated.
- Critical latency budgets identify expensive hops.
- Query, cache, batch, streaming, or asynchronous strategies are tied to measured or expected access patterns.
- Hot keys, fan-out, repeated queries, large payloads, unbounded lists, and long-running requests are addressed.
- Scaling is observable and has explicit triggers.
- Cost drivers and guardrails are described.

## 10. Observability and operations

- Logs, metrics, traces, audit records, and business indicators have clear purposes.
- Correlation identifiers or equivalent context connect critical flows.
- Service-level indicators and alert thresholds reflect user impact.
- Dashboards, runbooks, ownership, escalation, and incident response are planned.
- Health checks distinguish process health, dependency health, and readiness.
- Operational actions are safe, permissioned, and auditable.
- Support and administration tooling is included when manual diagnosis would otherwise require direct database edits.

## 11. Testing and quality

- Unit tests protect domain rules and state transitions.
- Integration tests cover persistence, queues, caches, and third-party adapters.
- Contract tests protect component and external boundaries.
- End-to-end tests cover a small set of critical workflows.
- Security, accessibility, performance, resilience, migration, backup/restore, and rollback tests are included where relevant.
- Test data and environment strategy avoids production-data leakage and brittle fixtures.
- Release gates are tied to objective evidence.

## 12. Delivery, migration, and rollback

- Continuous integration validates formatting, static analysis, tests, dependency risk, build reproducibility, and artifacts as appropriate.
- Environments and configuration are reproducible.
- Infrastructure changes and product-software changes are sequenced safely.
- Database and interface changes support rolling deployment when required.
- Feature flags have owners, lifecycle, observability, and removal plans.
- Data migration includes rehearsal, validation, reconciliation, rollback or compensation, and cleanup.
- Launch includes monitoring, support readiness, incident criteria, and rollback authority.
- Old systems, schemas, flags, and compatibility paths have decommission plans.
- Every deferred decision has a gate before irreversible or high-rework work begins.

## 13. Maintainability and decision quality

- Important choices are recorded as architecture decisions with rationale and alternatives.
- Public abstractions reflect domain concepts rather than implementation accidents.
- Modules have stable interfaces and high internal cohesion.
- Generated code, frameworks, and third-party services do not obscure ownership of critical behavior.
- Documentation identifies what must remain true, not only how the first version is built.
- Optionality is preserved by boundaries and delayed commitment, not by building speculative parallel implementations.

## 14. Parallel implementation readiness

- Every component and phase has a stable identifier that can be assigned to one implementation worker.
- The dependency graph distinguishes independent, contract-bound, implementation-bound, and decision-gated edges.
- A contract-bound edge names a concrete interface, symbol, schema, protocol, file format, or behavioral contract rather than relying on prose such as “provider completed.”
- Boundary semantics include preconditions, postconditions, errors, side effects, consistency, idempotency, concurrency, compatibility, and performance where relevant.
- Shared-file ownership, generated code, shared schemas, migrations, and infrastructure state are visible because they frequently prevent safe parallel writes.
- Candidate parallel waves contain no known implementation-bound edge between members.
- Client and provider work may run together only when both consume the same frozen canonical contract and contract tests or deterministic test doubles exist.
- Later phases may rely on earlier phases only through named public boundaries; they must not assume private implementation details.
- The plan identifies which boundary artifacts must be materialized in a contract baseline before workers start.
- Parallelism is an optimization, not a correctness requirement. Keep a unit sequential when freezing its boundary would create more complexity or rework than waiting for the predecessor.

## Disallowed shortcuts

Do not recommend any of the following as part of a production-ready phase:

- hardcoded secrets, tokens, tenant IDs, or environment-specific behavior;
- disabled or client-only authorization;
- direct production database edits as a routine workflow;
- in-memory persistence for data that must survive restart or scale beyond one process;
- a shared database used as an undocumented integration interface between independently owned components;
- unbounded retries, queues, concurrency, payloads, queries, or result sets;
- long-running synchronous requests when durable asynchronous execution is required;
- non-idempotent callback, job, payment, or message processing without duplicate protection;
- schema changes without migration, compatibility, and rollback planning;
- “temporary” production paths with no owner and no removal gate;
- generic error swallowing or silent data loss;
- security-, privacy-, or integrity-critical placeholders deferred beyond the phase that exposes the feature;
- manual deployment or configuration steps that cannot be audited or reproduced;
- a technology choice justified only by popularity;
- treating an unresolved principal decision as though it were already selected;
- implementing every possible deferred option merely to postpone a decision.

Development scaffolding is acceptable only when isolated from the production path, clearly labeled, and removed before the phase exit criteria are met.
