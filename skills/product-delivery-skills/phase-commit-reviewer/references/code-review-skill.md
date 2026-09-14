# Phase Commit Code Review Protocol

## Purpose

Review one implementation-phase commit for defects introduced by that commit, using the phase plan, frozen boundaries, canonical contracts, surrounding repository code, and the final integrated checkpoint as evidence.

This protocol adapts the supplied `code-review-skill.md` into a phase-aware, read-only `xhigh` workflow. It preserves the original emphasis on line-by-line review, removed guards, caller tracing, language hazards, wrapper correctness, cleanup, independent verification, and a final gap sweep. It adds plan compliance, boundary compliance, security, migration, reliability, test adequacy, and cross-phase attribution.

## Required reviewer profile

- **Model:** `gpt-5.6-sol`
- **Reasoning effort:** `xhigh`
- **Isolation:** one fresh reviewer context for one phase commit
- **Mutation policy:** read-only
- **Finding cap:** 15 surviving findings

When the requested profile is unavailable and no user-approved substitution exists, return `MODEL_BLOCKER` rather than silently reviewing with another profile.

## Required inputs

The assignment must provide:

- phase ID and component ID;
- target commit and selected first parent;
- frozen final review-baseline commit;
- isolated checkout pinned to the target commit, or an immutable target snapshot;
- one unambiguous approved-scope record containing delivery mode, requested outcome, impact cone, preserved behavior, and non-goals;
- an explicit `external_fidelity_required` value and, when true, the applicable dossier, evidence gaps, test-double provenance, provider version/environment, and conformance results;
- exact component plan and phase section;
- exact component boundary and phase section;
- consumed and produced canonical contracts;
- relevant product description, architecture, data, interface, security, testing, operations, migration, and delivery documents;
- repository instruction files governing changed paths;
- phase-to-commit map and summaries of later phases;
- safe validation commands;
- required JSON output schema.

Missing identity, diff, approved-scope data, plan, boundary, required contract context, or external-fidelity classification is a `SCOPE_BLOCKER`. A malformed, duplicated, or contradictory scope record also blocks. An explicit empty preserved-behavior list is valid. When external fidelity is required, missing material provider evidence blocks; when it is false, do not infer external scope. Optional missing context is recorded as a limitation.

## Review scope

The primary scope is the introduced patch:

```bash
git diff --find-renames --find-copies <target-parent> <target-commit>
git show --stat --summary <target-commit>
```

Also inspect:

- the complete enclosing functions, classes, modules, migrations, schemas, and configuration at the target commit;
- callers and callees affected by changed public or internal behavior;
- deleted or replaced behavior;
- tests and fixtures that claim to cover the change;
- the same relevant code at the frozen final baseline, to identify later fixes or supersession;
- governing repository rules such as `AGENTS.md`, `CLAUDE.md`, local instruction files, linters, and contribution policies.

Do not turn the review into an unrestricted audit of pre-existing code. A finding must be attributable to the target commit, or clearly explain why the target commit re-exposes or fails an explicit phase obligation.

## Review method

Run each angle as an independent pass. Do not let a conclusion from one angle suppress another before candidate deduplication.

### Angle A — Line-by-line diff scan

Read every hunk and its enclosing implementation. For every changed line ask which input, state, timing, platform, deployment mode, or failure path makes it wrong.

Check for:

- inverted conditions, off-by-one errors, wrong-variable copy/paste, and stale values;
- null, undefined, nil, empty, zero, and false conflation;
- missing `await`, lost errors, swallowed exceptions, or incorrect cancellation;
- unsafe parsing, encoding, escaping, regular expressions, path handling, and numeric conversion;
- incorrect resource ownership or lifecycle;
- assumptions that are absent from the plan or boundary.

### Angle B — Removed-behavior and invariant audit

For every deleted or replaced line, identify the invariant, validation, authorization check, cleanup, ordering guarantee, compatibility behavior, or error path it previously enforced. Find where the new code re-establishes it. Missing re-establishment is a candidate.

### Angle C — Cross-file caller and callee tracing

For every changed callable, schema, command, event, configuration key, and data shape:

- find direct and indirect callers;
- inspect changed preconditions, return values, exceptions, timing, ordering, and side effects;
- inspect callees whose assumptions may no longer hold;
- check generated clients, serialization, mocks, fixtures, and adapters;
- check whether later phases rely on a guarantee the commit fails to provide.

### Angle D — Language and framework hazards

Apply the concrete hazards of the repository's language and framework, including where relevant:

- closure capture, mutable defaults, object aliasing, and lifetime bugs;
- nil-map writes, iterator invalidation, use-after-free, ownership mistakes, or unsafe concurrency;
- timezone, locale, floating-point, Unicode, and platform path behavior;
- ORM transaction boundaries, lazy loading, N+1 queries, stale entities, and migration traps;
- framework lifecycle, dependency injection, middleware ordering, and configuration precedence;
- SQL, shell, template, URL, header, and regular-expression injection.

### Angle E — Wrapper, adapter, cache, and proxy correctness

When the commit adds or changes a wrapper:

- ensure calls are forwarded to the intended delegate rather than a registry, global, or wrapper entry point that causes recursion or bypass;
- verify all required methods and semantics are preserved;
- verify cache keys, invalidation, error caching, TTLs, concurrency, and partial failures;
- verify adapters preserve units, identifiers, pagination, ordering, nullability, and errors.

### Angle F — Phase-plan compliance

Compare the implementation against the exact phase:

- objective, scope, and non-scope;
- requirements delivered;
- architecture decisions and invariants;
- migration, rollout, observability, testing, and documentation obligations;
- exit criteria and downstream obligations.

Report omitted or contradicted behavior only when the plan is explicit enough to establish the requirement.

### Angle G — Boundary and contract compliance

Compare code against every consumed and produced `CTR-###` contract and the phase boundary:

- exact paths, names, signatures, schemas, status codes, events, and configuration keys;
- authentication, authorization, tenancy, idempotency, retries, timeouts, pagination, and error model;
- transaction, consistency, ordering, versioning, compatibility, and deprecation guarantees;
- mock, generated-client, and contract-test behavior;
- path ownership and forbidden-path rules.

Flag undocumented contract drift, private-detail coupling, and behavior that a parallel consumer could not safely rely upon.

### Angle H — Security, identity, privacy, and data integrity

Trace trust boundaries and sensitive operations:

- authentication and session handling;
- authorization at every resource and tenant boundary;
- confused-deputy, IDOR, privilege escalation, and cross-tenant access;
- secret handling, logging, data minimization, encryption, retention, deletion, and residency obligations;
- validation before persistence or external side effects;
- transaction atomicity, uniqueness, replay, double-submit, and partial failure;
- dependency, deserialization, file-upload, SSRF, injection, and unsafe redirect risks.

### Angle I — Concurrency, reliability, and operational behavior

Inspect:

- races, lock scope, deadlocks, duplicate work, lost updates, and non-atomic check-then-act;
- retries without idempotency, retry storms, missing backoff/jitter, and unbounded queues;
- timeouts, cancellation, connection and file descriptor leaks, shutdown ordering, and cleanup asymmetry;
- circuit breakers, reconciliation, poison messages, partial outages, and recovery behavior;
- migration/rollback order, mixed-version deployment, and zero-downtime compatibility;
- metrics, logs, traces, alerts, and runbook-relevant signals required by the plan.

### Angle J — Tests and failure-path adequacy

Tests are reviewed as executable claims, not merely counted.

Check:

- whether each phase exit criterion has a meaningful test or validation;
- boundary values, malformed inputs, permission failures, duplicates, retries, timeouts, and partial failures;
- setup/teardown symmetry and isolation;
- deterministic behavior and avoidance of false-positive assertions;
- contract tests between parallel providers and consumers;
- whether deleted tests removed real coverage;
- whether a regression test can be proposed for each correctness finding.

Missing tests alone are reported only when the omitted case leaves a concrete phase obligation or high-risk failure path unverified.

### Angle K — Reuse, simplification, efficiency, and architectural altitude

Review changed code for concrete maintenance or runtime cost:

- reimplementation of an existing helper or abstraction;
- redundant state, duplicated logic, deep nesting, dead code, or unnecessary indirection;
- repeated I/O, avoidable hot-path work, unbounded memory, and blocking operations;
- captured large environments or long-lived closures;
- fragile special cases applied above the layer that owns the invariant;
- architectural shortcuts that contradict the product plan.

Correctness and security findings outrank cleanup findings when the cap is reached.

### Angle L — Repository conventions

Read all instruction files that govern changed paths. Report a convention finding only when you can identify:

- the exact instruction file and rule;
- the exact changed line that violates it;
- the concrete resulting cost or failure.

Do not report personal style preferences.

## Candidate verification

After candidate generation:

1. deduplicate candidates with the same mechanism and location;
2. re-check each against the exact target state, enclosing code, callers/callees, plan, boundary, contracts, tests, and final baseline;
3. classify it:
   - `CONFIRMED`: a reachable input/state and wrong result, exposure, corruption, or concrete cost can be demonstrated;
   - `PLAUSIBLE`: the mechanism is real and the trigger is realistic but environment-, timing-, or configuration-dependent;
   - `REFUTED`: contradicted by code, type, invariant, guard, contract, or later evidence;
4. drop `REFUTED` candidates;
5. run one fresh gap sweep looking only for mechanisms not already represented;
6. verify sweep candidates the same way;
7. rank survivors by severity, blast radius, exploitability/data risk, frequency, and recovery difficulty;
8. keep at most 15.

Do not reject realistic races, rare error paths, boundary values, or partial failures merely because they are uncommon. Do not retain speculation without a concrete mechanism.

## Cross-phase attribution

For every survivor record:

- whether the target commit introduced it;
- whether it remains present at the final baseline;
- whether a later commit fixed or superseded it;
- the earliest phase that owns the root cause;
- the earliest phase where a valid regression test can exist.

A reviewer recommends attribution. The main agent makes the final disposition and phase assignment.

## Severity

- **Critical:** likely exploitable security failure, cross-tenant exposure, irreversible data corruption/loss, or broad service failure.
- **High:** serious correctness, authorization, integrity, migration, availability, or contract failure with meaningful blast radius.
- **Medium:** reachable user-visible or operational defect, bounded reliability issue, or material plan/contract violation.
- **Low:** concrete limited defect or maintenance/convention cost likely to cause drift or future errors.

## Output

<!-- Deliberately package-local: the standalone reviewer ships assets/reviewer-result.schema.json. -->
Return one JSON object conforming to `assets/reviewer-result.schema.json`.

Every finding must include:

- stable ID;
- verdict, severity, and category;
- target and final locations;
- concise summary;
- concrete failure scenario;
- exact evidence;
- plan, boundary, contract, code, test, or repository-rule references;
- target-commit and final-baseline attribution;
- recommended owner phase, fix direction, and regression test;
- confidence notes.

An empty `findings` array is correct when nothing survives verification. Never add filler.

## Reviewer prohibitions

The reviewer must not:

- edit files or generated artifacts;
- invoke a fix mode;
- create, amend, rebase, merge, or delete commits or branches;
- change plans, contracts, manifests, or ledgers;
- post comments to external systems;
- mutate production-connected resources;
- broaden scope silently;
- claim a command ran when it did not.
