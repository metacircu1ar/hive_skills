# Product Description Intake

## Purpose

Use this reference during Planning Phase 0. The goal is to turn a rough product idea, change request, or existing specification into a normalized product-or-change description that can safely drive architecture and implementation planning.

The intake must improve clarity without forcing the user to know every technical answer upfront.

## Entry behavior

### Description supplied

When the invocation includes a substantive description or names a clear source document:

1. read it completely;
2. preserve it as source evidence;
3. identify gaps and contradictions;
4. ask only consequential questions that remain unanswered;
5. synthesize the normalized description in `docs/implementation-plan/00-product-description.md`.

### Description absent

When the invocation contains no substantive description and names no unambiguous source document, ask the user for one before architectural planning.

Use a prompt similar to:

> Describe the product or change you want to deliver in any format. A rough idea is enough. Please include the desired outcome, affected users and workflows, what is in and out of scope, behavior that must remain unchanged for an existing product, and any known constraints or integrations.

Do not ask the user to fill a long questionnaire before they can begin. Obtain the free-form description first, then ask targeted questions based on it.

## Minimum viable product description

A description is usable for the next planning step when it gives enough information to identify:

- the problem or opportunity;
- intended users, customers, operators, or external actors;
- the primary value-producing workflows;
- the intended product surfaces;
- the delivery scope mode and a plausible release or change boundary;
- current and target behavior, the impact cone, and preserved behavior for existing products;
- known business rules, data, integrations, or constraints;
- which major facts are confirmed versus uncertain.

It does not need to contain every architecture decision. Missing decisions can be clarified, assumed, or deferred according to their impact.

## Principal decision interview

After reading the initial description, perform one focused pass over the decisions with the largest architectural impact. Ask only relevant, unanswered questions.

| Decision area | Examples of choices | Why it can be principal |
|---|---|---|
| Delivery scope | Full product; scoped change; modernization or migration; remediation or reliability | Determines what completeness means, which baseline evidence is required, and which artifacts and components are in scope |
| Hosting and operating model | Product-owner-managed service; dedicated managed deployment; customer-managed or on-premises; hybrid; local-only | Changes topology, trust boundaries, upgrade delivery, observability, support, storage, data residency, and vendor choices |
| Product surfaces | Responsive web; native mobile; desktop; public interface; embedded; internal tools | Changes client architecture, release channels, compatibility, offline behavior, and testing |
| Tenancy | Single organization; multi-tenant shared; isolated tenant resources; dedicated deployment | Changes identity, data partitioning, authorization, provisioning, cost, and operations |
| Identity and administration | Product-owned identity; enterprise SSO; social login; customer identity provider; delegated administration | Changes trust boundaries, user lifecycle, authorization, audit, and support |
| Data and compliance | Public data; confidential business data; personal data; health, payment, child, or regulated data; residency constraints | Changes storage, encryption, audit, retention, deletion, vendor eligibility, and review gates |
| Scale and reliability | Early pilot; mass consumer; enterprise critical; global low-latency; offline-first; strict recovery objectives | Changes capacity model, failure design, topology, testing, and cost |
| Integrations and systems of record | Standalone product; imports; public interface; payments; enterprise systems; hardware; third-party data | Changes contracts, idempotency, reconciliation, failure handling, and ownership |
| Existing product and migration | New build; replacement; coexistence; incremental migration; hard cutover | Changes compatibility, data migration, rollout, rollback, and decommissioning |
| Commercial model | Free; subscription; usage-based; licensed deployment; marketplace; internal cost center | Changes entitlements, metering, billing, licensing, and reporting |
| Team and technology constraints | Mandated stack; cloud restriction; small team; existing platform; operational skill limits; budget ceiling | Changes feasible architecture, service choices, ownership, and delivery sequencing |

For each question include:

1. the decision being requested;
2. why it changes the plan;
3. realistic options;
4. a recommended default when justified;
5. the response choices: decide now, accept the recommendation, or defer.

## Deferral protocol

A user may defer an answer. Deferral is acceptable when a clean boundary can prevent the uncertainty from contaminating work that starts earlier.

For each deferred decision, record:

- **Decision ID:** stable identifier such as `DEC-001`;
- **Status:** `Deferred`;
- **Question:** the exact choice still open;
- **Options:** viable alternatives;
- **Provisional default:** optional, clearly labeled;
- **Invariant constraints:** what the design must not assume while the decision is open;
- **Impact radius:** requirements, components, data, contracts, security controls, and delivery phases affected;
- **Safe work before decision:** tasks that remain valid under every live option;
- **Latest responsible decision point:** the phase prerequisite or objective trigger before commitment is required;
- **Owner:** decision-maker when known;
- **Revision path:** documents and work that must change if the final choice differs from the provisional default.

Do not use deferral to avoid decisions that are required for safety, legal compliance, approved-scope semantics, or the next executable phase.

## Status rules

- Use `Blocked` when the product cannot be modeled safely or coherently.
- Use `Draft` when material decisions remain open and the plan is still being shaped.
- Use `Ready for implementation` only when the phases authorized to begin have no unresolved prerequisites.

The overall plan may contain later decision gates while early phases are ready. State phase readiness explicitly rather than reducing the entire product to a single misleading status.

## Normalized document content

`00-product-description.md` should capture:

- source documents and user answers;
- the unique canonical delivery-scope record defined by `planning-output-contract.md`, plus current and target behavior and supporting prose;
- product vision, problem, users, and intended outcomes;
- delivery scope and release boundary;
- product surfaces and hosting or operating model;
- primary, exceptional, and recovery workflows;
- functional and non-functional requirements with stable IDs;
- business rules and invariants;
- constraints and external dependencies;
- a principal decision register;
- assumptions and deferred decisions;
- acceptance model and change history.

This document is the product or change contract for the rest of the planning set. Later plans must link back to it rather than silently redefining the approved scope.
