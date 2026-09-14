# Clarification and Decision Checklist

Use this checklist after the initial product-description intake to find material unknowns before finalizing architecture. Ask only questions that are genuinely unanswered and consequential.

## How to ask

Use one consolidated, numbered message. For each question include:

1. **Question** — a precise decision the user can answer.
2. **Why it matters** — the architecture or product behavior affected.
3. **Options** — realistic choices when useful.
4. **Recommended default** — the option you would choose if the user asks for a recommendation.
5. **Deferral path** — whether the choice can be postponed and, if so, the latest responsible decision point.

Allow the user to answer each item by deciding now, accepting the recommendation, or deferring.

Classify each item as:

- **Blocking now:** different answers materially change work that must begin next, and no safe boundary can isolate the choice.
- **Decision-gated:** planning can continue, but named phases or components cannot begin until the choice is made.
- **Non-blocking:** a conservative, reversible assumption can be recorded without likely material rework.

Do not ask for information already available in the product description, repository, or prior user answers.

## Principal decision pass

Before using the detailed checklist, confirm that the following architecture-shaping areas are either answered, deliberately assumed, or decision-gated:

- hosting and operating model;
- product surfaces and supported platforms;
- tenancy and isolation;
- identity, authorization, and administration;
- data sensitivity, residency, privacy, and compliance;
- scale, availability, latency, recovery, and geography;
- integrations and systems of record;
- existing-product migration and backward compatibility;
- commercial model or licensing when relevant;
- team, stack, budget, operational ownership, and delivery constraints.

Do not mechanically ask all of them. Ask only what is relevant and unresolved.

## Product and scope

- What problem is the product or change solving, and what outcome defines success?
- Is this full-product, scoped-change, modernization-or-migration, or remediation-or-reliability work?
- Which capabilities are required for the approved delivery scope or first production release?
- Which tempting adjacent capabilities are explicitly out of scope?
- Is this a new product, a replacement, or an extension of an existing system?
- For an existing system, which callers, interfaces, data, operations, tests, and compatibility guarantees form the impact cone, and what behavior must remain unchanged?
- Are there fixed launch, contractual, or migration deadlines?

## Hosting and operating model

- Is the product operated as a shared managed service, a dedicated managed deployment, customer-managed or on-premises software, a hybrid, or a local-only product?
- Who owns deployment, upgrades, monitoring, backup, incident response, and support?
- Are specific clouds, regions, hardware, networks, or air-gapped environments required or prohibited?
- Must the design support more than one operating model, or is one model sufficient for the first production release?
- What portability commitments are contractual rather than merely desirable?

## Users, roles, and workflows

- Who are the user types, operators, administrators, and external actors?
- What permissions and approval rules apply to each role?
- Which workflows are business-critical?
- Which exceptional, cancellation, retry, dispute, or recovery flows are required?
- Is multi-tenancy required? If so, what is the isolation model?

## Platforms and experience

- Which clients are required: responsive web, native mobile, desktop, public interface, embedded experience, or administration interface?
- Which browsers, operating systems, devices, and accessibility standards must be supported?
- Are offline operation, real-time collaboration, push notifications, background execution, localization, or time-zone correctness required?
- Are there design-system or brand constraints?

## Identity and security

- Who owns identity: the product, an enterprise identity provider, a social login provider, or another system?
- Are multi-factor authentication, single sign-on, automated provisioning, delegated administration, service accounts, impersonation, or audit trails required?
- What authorization model is needed: roles, permissions, attributes, resource ownership, or policy rules?
- What data is sensitive, regulated, confidential, or tenant-isolated?
- What threat model, security review, or certification obligations apply?

## Domain and data

- What are the authoritative entities and business invariants?
- Which system is the source of truth for each important data category?
- What consistency guarantees are required?
- What data volume, growth, retention, deletion, export, residency, and backup requirements apply?
- Is historical reconstruction, auditability, versioning, or legal hold required?
- Is there existing data to migrate, reconcile, or clean?

## Integrations

- Which third-party or internal systems must be integrated?
- Are their contracts, rate limits, environments, callbacks, sandboxes, and service expectations known?
- What happens when an integration is unavailable or returns conflicting data?
- Which side owns retries, idempotency, reconciliation, and support?
- Are import/export formats or public interfaces part of the product contract?

## Scale, reliability, and performance

- What are the expected users, tenants, requests, jobs, data size, file size, and geographic distribution?
- What peak-to-average traffic ratio and burst behavior are expected?
- What latency targets apply to critical interactions?
- What availability, recovery-point, recovery-time, durability, and support-hour requirements apply?
- Which operations may be eventually consistent or asynchronous?
- What cost ceiling or infrastructure constraints apply?

## Compliance and governance

- Which privacy, health, payment, security, child-safety, financial, employment, accessibility, or regional obligations are relevant?
- Are consent, data-subject rights, audit evidence, retention schedules, age restrictions, or content moderation required?
- Are there country, cloud, data-residency, or vendor restrictions?

## Delivery constraints

- Is a technology stack already mandated?
- What skills and operational capabilities does the team have?
- What environments, continuous delivery, cloud accounts, observability, secrets management, and support processes already exist?
- Is backward compatibility required for current clients or interfaces?
- Can the product be launched incrementally, or is a coordinated cutover required?
- Who owns post-launch operations and incident response?

## Business and monetization

- Is billing, subscription management, usage metering, entitlements, trials, refunds, taxes, invoicing, or license enforcement required?
- What is the authoritative source for plans and entitlements?
- Are analytics, attribution, experimentation, or regulatory reporting required at launch?

## Stop condition

The gate is complete when every material item is one of:

- answered;
- represented by an authorized, reversible assumption; or
- deferred with a documented decision gate and latest responsible decision point.

A plan with unresolved blocking-now questions must be marked `Blocked`. A decision-gated question does not block unrelated phases, but every dependent phase must list that gate as a prerequisite.
