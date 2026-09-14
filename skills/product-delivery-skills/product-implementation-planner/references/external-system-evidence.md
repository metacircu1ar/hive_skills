# External-System Evidence

Use this reference when the product materially depends on behavior controlled by a third-party API, a separately operated internal service, a legacy service being replaced, hardware, a queue, or a file exchange.

The purpose is to prevent the plan, formal abstraction, adapter, and mock from agreeing with the same unsupported assumption while disagreeing with the real system.

## Research rule

A mock, fixture, generated client, current wrapper, or plan-authored schema is not independent evidence when it was derived from the behavior being checked.

For each material provider behavior, seek the strongest applicable combination of:

- versioned authoritative documentation or machine-readable contracts;
- source for the supported SDK version;
- inspected legacy adapter behavior and tests, treated as evidence of what the old product depended on rather than what the provider guarantees;
- sanitized requests, responses, errors, logs, or traces;
- authorized read-only sandbox or staging observations.

Record contradictions and unknowns. A single observation proves only that one occurrence happened in one environment; it is not automatically a general guarantee.

Record each evidence gap as a structured entry with the missing behavior, affected claims/phases, owner, and closure trigger or due gate. Do not use bare `TBD` or `TODO` markers for an intentionally unresolved provider behavior.

## Where the evidence lives

Use `docs/implementation-plan/04-external-system-evidence.md` as a small registry plus one dossier per material system under `docs/implementation-plan/external-systems/`. Stable IDs such as `EXT-###` for a system, `ECL-...` for a behavior claim, and `EVD-...` for an evidence item make downstream traceability easier, but the important invariant is the claim-to-evidence link rather than a particular file format.

The dossier is the current source of truth. It should state:

- provider, protocol/API version, environment, and product operations that depend on it;
- authentication, request/response shapes, defaults, nullability, units, timestamps, pagination, and ordering where relevant;
- errors, partial success, side effects, idempotency, retries, timeouts, rate limits, consistency, and ambiguous writes where relevant;
- declared behavior, observed behavior, legacy dependency, and intended adapter behavior without collapsing them into one claim;
- evidence source, freshness, confidence, contradictions, unknowns, and revalidation triggers;
- affected phases and the characterization, parity, or conformance gate required before integration or real writes.

Use planning, verification, and implementation ledgers only to record changes: what new evidence appeared, what assumption changed, which artifacts became invalid, and which checks must rerun. Update the dossier first; otherwise the ledger becomes a competing and eventually stale provider specification.

## Provider protocol and product port

Keep these boundaries separate:

1. the uncontrolled provider protocol;
2. the product-owned normalized port consumed by domain code.

A deterministic fake of the normalized port may unblock consumer work. It proves only that the consumer conforms to the product-owned port. It does not prove provider behavior or that the real adapter maps the provider correctly.

A test double that purports to emulate the provider must identify its evidence, represented version, normal and failure behavior, omissions, and known differences. Plan a shared characterization or conformance suite that compares the real adapter and substitute at the normalized port where feasible.

## Readiness and authorization

An adapter phase may be planned with open evidence, but it remains decision-gated or implementation-bound before it would need to guess material behavior. Mock-only green tests never discharge the adapter-fidelity gate.

Public documentation and repository-owned evidence may be researched read-only. Private documentation, credentials, and live environments require applicable authorization. Read access does not imply write access; sandbox writes, production writes, quota-consuming operations, and destructive actions require their own authority. Store only sanitized evidence and never copy secrets or personal/confidential payloads into planning artifacts.

If real-provider checks are infeasible, record the missing evidence, risk owner, compensating control, and latest point at which the gap must close.
