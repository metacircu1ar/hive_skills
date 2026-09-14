# Boundary Contract Standard

## Purpose

A boundary document tells an implementation worker exactly what it may rely upon and what it must deliver without revealing or requiring another worker's private implementation.

Create one boundary document for every component plan in the approved scope. The boundary document is consumer-oriented and phase-specific. Canonical interface definitions remain in their natural source files; the boundary document links to them and explains their semantics.

## Boundary directory and naming

For a component plan:

```text
docs/implementation-plan/components/backend-service.md
```

create:

```text
docs/implementation-plan/parallel-implementation/boundaries/backend-service.md
```

Use the same filename so plan-to-boundary mapping is unambiguous.

## Document metadata

Every boundary document begins with:

- title;
- status: `Draft`, `Blocked`, `Frozen`, or `Superseded`;
- component ID;
- source component plan;
- contract-baseline commit, or `pending` in the self-contained launch-baseline copy until the separate dispatch record is committed;
- last updated;
- canonical contract IDs covered;
- related documents.

`Frozen` means workers may rely on the document and canonical contract artifacts at the recorded baseline commit. It does not mean the boundary can never evolve; changes must follow change control.

## Component-level sections

Include:

1. Boundary purpose
2. Component ownership and non-ownership
3. Canonical contract registry
4. Shared invariants
5. Path ownership policy
6. Phase boundaries
7. Cross-component compatibility rules
8. Change-control owner
9. Known blockers and deferred decisions

## Canonical contract registry

Assign every contract a stable ID such as `CTR-001`.

For each contract record:

- contract ID;
- name and kind;
- owner component and owner phase;
- consumer phase IDs;
- canonical repository path;
- source planning documents;
- version or compatibility marker;
- status: `Draft`, `Frozen`, `Implemented`, `Deprecated`, or `Retired`;
- validation command;
- change-control rules.

Applicable contract kinds include:

- language-level interface, protocol, abstract type, module export, or function signature;
- HTTP, GraphQL, RPC, command-line, callback, or plugin interface;
- event, queue message, job payload, file, import, or export format;
- database ownership, schema, migration, view, or read-model boundary;
- configuration, environment variable, feature-flag, or secret contract;
- user-interface component contract;
- observability, audit, health, or operational command contract;
- product-owned normalized-port fake, fixture, generated client, or contract-test suite;
- evidence-backed provider-protocol emulator, when the phase must simulate an uncontrolled external system.

## Required phase-boundary section

Use one section per `PH-###-##` implementation unit.

### Phase identity

Record:

- phase ID and title;
- implementation status;
- plan section link;
- execution-manifest unit;
- worker-prompt path;
- base commit and wave;
- predecessor and consumer phase IDs.

### Inbound guarantees

List only guarantees that are frozen and available at the phase's base commit.

For each guarantee include:

- provider phase or contract ID;
- canonical path;
- exact name or operation;
- version;
- behavioral meaning;
- validation or contract test;
- failure behavior when unavailable.

Do not write “the server exists,” “authentication is ready,” or “the previous phase is done.” State the exact boundary.

### Exact interface surface

Specify applicable details:

- module and package path;
- public symbol names;
- parameters, types, defaults, return values, and error types;
- endpoint method, route, request, response, status, error envelope, pagination, filtering, ordering, and rate limits;
- event name, producer, consumers, schema, partition or ordering key, delivery semantics, idempotency key, retry and dead-letter behavior;
- command name, arguments, standard input/output, exit codes, and error handling;
- file name or pattern, encoding, schema, atomicity, locking, retention, and compatibility;
- configuration key, type, source, default, validation, secrecy, and reload behavior;
- persistence object ownership, transaction boundary, migration order, and read/write permissions.

For a persistent resource named in the planning decomposition assessment, cite its resource name, owner component, authorized writer components, and coordination mechanism. Do not grant a unit broader write authority than that immutable planning record.

When the stack is dynamic, signatures still need semantic precision. When the stack is static, include exact declarations or canonical declaration-file paths.

## Behavioral contract

A signature alone is insufficient when behavior affects consumers. Define where relevant:

- preconditions and input validation;
- postconditions and invariants;
- normal result semantics;
- domain and transport errors;
- side effects;
- transaction and consistency behavior;
- idempotency and duplicate handling;
- concurrency and reentrancy;
- ordering;
- timeout, cancellation, retry, and backpressure;
- authorization and audit behavior;
- performance or capacity expectations;
- observability emitted;
- compatibility and deprecation.

### Example: language-level dependency

A phase implementing `cube` may rely on:

```text
CTR-017
Canonical path: src/math/square.ts
Export: square(value: number): number
Preconditions: value must be a finite number
Result: value multiplied by itself using normal JavaScript number semantics
Errors: RangeError for non-finite input
Side effects: none
Concurrency: pure and reentrant
Contract test: tests/contracts/square.contract.test.ts
```

The consumer may import and call `square` by that path and name. It may not rely on the multiplication algorithm, local helpers, caching, or private file layout.

### Example: client-to-service dependency

A client boundary should name the canonical service contract rather than saying “the service will provide endpoints.” For example:

```text
CTR-021
Canonical path: contracts/openapi.yaml
Operation ID: createProject
Method and route: POST /v1/projects
Authentication: bearer session token with projects:create permission
Idempotency: required Idempotency-Key header, scoped to tenant and operation
Success: 201 with Project representation
Validation errors: 422 with canonical problem-details schema
Conflicts: 409 when the external key already exists
Contract mock: tools/mock-service configuration generated from contracts/openapi.yaml
Contract tests: tests/contracts/projects-api/
```

The service worker and client worker consume the same canonical definition and tests.

## Outbound obligations

Describe what the phase must make true for later workers:

- contracts implemented or advanced to a new status;
- public artifacts created at exact paths;
- behavior and compatibility guaranteed;
- migrations or generated artifacts produced;
- tests that later workers may reuse;
- operational readiness provided;
- new constraints imposed on consumers.

A phase is not complete until its outbound obligations and contract tests pass.

## Test doubles and provider absence

A consumer may start before its provider only when the product-owned normalized port is frozen and a deterministic internal-port substitute exists. This proves consumer conformance to the normalized port, not provider behavior or real-adapter fidelity.

The boundary must identify:

- whether the substitute is an internal-port fake or a provider-protocol emulator, and its path;
- how it is generated or started;
- which contract version it implements;
- how contract tests prevent drift;
- behavior intentionally not simulated;
- conditions requiring later integration tests against the real provider.

For a provider-protocol emulator, also record the evidence provenance, represented provider version/environment, and known differences from declared or observed provider behavior. Do not permit worker-authored ad hoc stubs that redefine the provider contract or treat a provider emulator as independent provider evidence.

## Path ownership

For each phase identify:

- **Owned paths:** worker may create or modify them.
- **Read-only paths:** worker may inspect and import but not modify.
- **Shared paths:** changes require the named owner or main-agent reconciliation.
- **Generated paths:** worker may update only through the canonical generator.
- **Forbidden paths:** worker must not modify.

Use the narrowest practical patterns. A whole repository or top-level `src/` directory is rarely acceptable ownership for one unit.

### Common shared-path hazards

Treat these as shared until proven otherwise:

- dependency manifests and lockfiles;
- central route, dependency-injection, plugin, or feature registries;
- database migration directories and schema snapshots;
- generated interface clients and types;
- global configuration examples;
- monorepo workspace definitions;
- continuous-integration pipelines;
- infrastructure state and shared modules;
- localization catalogs;
- root documentation and changelogs.

Assign one writer per wave or serialize the affected units. The main agent may own final regeneration and reconciliation.

## Cross-component boundary rules

- The provider owns implementation and conformance.
- The consumer owns correct use, error handling, and degraded behavior.
- Both use the same canonical contract version.
- Authentication, authorization, tenancy, and data-classification requirements are part of the boundary.
- Contract evolution must state backward and forward compatibility expectations.
- Direct access to another component's private data or internals is forbidden unless the architecture explicitly defines that access as public.

## Boundary completeness test

A boundary is complete enough for parallel execution only when an isolated worker can answer:

1. What exact names and paths may I import, call, publish, read, or write?
2. What behavior may I assume, including errors and side effects?
3. What contract artifacts exist in my base commit?
4. How can I build and test while the provider implementation is absent?
5. Which files may I modify?
6. What must I deliver for downstream phases?
7. Which assumptions are forbidden?
8. What must I report as a blocker instead of guessing?
9. Does every persistent write agree with the plan's data owner and authorized-writer record?

When any answer is missing and material, keep the boundary `Draft` or reclassify the dependency as implementation-bound.
