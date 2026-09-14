---
name: product-plan-compiler
description: Use this skill after a detailed product, feature, modernization, migration, remediation, or system plan exists—especially one produced by product-implementation-planner—to extract a traceable formal domain model for the approved scope, select a complementary verification portfolio across Alloy, SMT, TLA+/TLC/Apalache/TLAPS, Lean, Rocq, or Arend, run the native tools, challenge external-system abstractions, and refine the plan and formalization until they agree before implementation.
metadata:
  version: "1.3.0"
  compatibility: "Requires a filesystem-enabled coding agent that can read and update planning documents and execute the native backends selected for checked claims. Missing tooling remains an explicit scoped gap; a fallback does not replace native verification. Human-status-aware delivery requires `product-implementation-planner` >= 2.5.0 upstream and `parallel-plan-implementation` >= 2.5.0 downstream."
  upstream-skill: product-implementation-planner
  upstream-version: ">=2.5.0"
  downstream-skill: parallel-plan-implementation
  downstream-version: ">=2.5.0"
  reviewer-skill: phase-commit-reviewer
  stage: plan-verification
---
<!--
COMPLETE SKILL DESCRIPTION
This planning-verification skill compiles a detailed product or change plan into a traceable formal intermediate representation and an obligation-driven portfolio of executable prover or model-checker programs. It verifies the approved domain and change—not merely the agents that authored the plan—by modeling relevant entities, relations, lifecycles, operations, permissions, failures, concurrency, safety, liveness, compatibility, and preserved behavior.
It selects complementary backends by obligation, including Alloy, SMT, TLA+/TLC/Apalache/TLAPS, Lean, Rocq, and Arend; runs the native tools; preserves commands, versions, bounds, assumptions, and traces; and translates every counterexample or failed proof obligation back into the language and requirement IDs of the source plan. It treats formal environment abstractions and test doubles as claims that require real-system evidence, not as evidence merely because they agree with one another.
The skill iteratively classifies defects in the plan, model, property, assumptions, bounds, or encoding, changes one layer at a time, and reruns affected checks plus regression, witness, non-vacuity, and mutation checks. Semantic plan changes require an explicit product decision and are never hidden inside a passing model.
Its normal upstream is `product-implementation-planner`. It remains planning-only, writes verification artifacts under `<plan-root>/formal-verification/`, updates the derived cross-stage `<plan-root>/delivery-status.md`, and tells the operator where that human summary is after the verification stage completes or blocks. It offers an explicit handoff to `parallel-plan-implementation` only after the plan, IR, formal programs, properties, assumptions, bounds, and native results converge for the documented scope.
-->
# Product Plan Compiler

Use this skill after a detailed product, change, or system plan exists—normally after `product-implementation-planner`. The artifact being compiled and checked is the **approved plan itself**: its in-scope domain entities, relationships, lifecycles, operations, permissions, constraints, failures, temporal behavior, and preservation obligations.

Do not silently substitute verification of the planning agents or development workflow. Agent orchestration is in scope only when it is explicitly part of the product being designed.

## Delivery-stage position

The intended product-delivery sequence is:

```text
product-implementation-planner
             |
             v
product-plan-compiler
             |
             v
parallel-plan-implementation
             |
             v
phase-commit-reviewer
```

Set `<plan-root>` to the directory containing the scope-complete planning corpus; it defaults to `docs/implementation-plan/`. Read `<plan-root>/delivery-status.md` only as a human navigation aid; canonical scope and requirements still come from their detailed sources. Place compiler output under `<plan-root>/formal-verification/` and record a non-default selected root in the verification scope and source record.

Read the planner's unique canonical delivery-scope block—including mode, outcome, impact cone, preserved behavior, non-goals, and planned phases—before choosing verification obligations; reject duplicate or contradictory scope declarations rather than selecting whichever is convenient. Full-product verification may cover the complete plan. For scoped change, modernization or migration, and remediation or reliability work, cover the changed rules, invariants that must remain true, compatibility and migration behavior, and affected interfaces or interactions. Unchanged product behavior outside the impact cone may be excluded with a recorded rationale and source baseline; discovering an unrelated concern does not silently expand the authorized scope.

This skill may revise planning documents only through explicit, traceable product decisions. It must not modify product source code, dependencies, migrations, infrastructure, or runtime configuration. It never starts implementation automatically.

## Objective

Given a detailed plan:

1. Extract a precise, traceable formal model.
2. Classify obligations and select the smallest complementary portfolio that covers their distinct evidence needs.
3. Implement executable/checkable specifications.
4. Run the native checker or prover.
5. Explain every failure in the vocabulary of the original plan.
6. Refine the plan, the model, or an explicit assumption.
7. Repeat until the accepted plan, formal model, properties, bounds, and results agree.

"Agreement" means traceable alignment under documented assumptions and scopes. It does not mean that a bounded model check proves the real implementation correct.

## Required output structure

Create or maintain:

```text
<plan-root>/
  delivery-status.md
  formal-verification/
    00-scope-and-sources.md
    01-normalized-plan.md
    02-formal-ir.yaml
    03-traceability.md
    04-open-questions.md
    models/
      <tool>/
    runs/
      <run-id>/
        command.txt
        versions.txt
        configuration.*
        stdout.txt
        stderr.txt
        result.md
    refinement-ledger.md
    verification-report.md
```

Never overwrite evidence from an earlier run. Use a new run directory and record the change that motivated it.
`delivery-status.md` is not run evidence and is not append-only; the main compiler agent updates its current human summary while preserving links to immutable runs and the refinement ledger.

## Core workflow

### 0. Confirm the compilation entry gate

Before formalizing, confirm that the plan corpus is sufficiently complete for the requested scope:

- the source files and plan version are identifiable;
- the planner-created `delivery-status.md` exists and identifies itself as derived and non-authoritative;
- normative requirements have stable IDs or can be assigned without changing meaning;
- the domain vocabulary, affected workflows and components, relevant data ownership, permissions, failures, lifecycle rules, compatibility, and preserved behavior are present;
- blocking product decisions are resolved or the verification scope explicitly excludes them;
- the plan states which implementation phases are intended to follow verification.

If the plan is materially incomplete, return it to `product-implementation-planner` or mark the compiler run `BLOCKED`. Do not fill semantic gaps by invention. A deliberately scoped partial compilation is allowed only when its exclusions are explicit.

### 1. Read and normalize the plan

Read the complete in-scope plan and the baseline evidence needed to understand its impact cone before formalizing. Build a stable glossary and identify every normative claim in that scope, especially words such as `must`, `shall`, `may`, `only`, `exactly`, `never`, `eventually`, `immediately`, and `at most`.

Normalize the plan without changing its meaning:

- assign stable IDs to requirements and rules;
- distinguish domain facts from examples and implementation suggestions;
- resolve synonyms into canonical entity and state names;
- preserve conflicting statements instead of silently choosing one;
- mark inferred assumptions as assumptions, not source requirements.

### 2. Build the formal intermediate representation

Populate `02-formal-ir.yaml` using `templates/formal-ir.yaml`.

Extract at least:

- entities and identity rules;
- attributes and value domains;
- relations, ownership, and cardinalities;
- lifecycle states and legal transitions;
- operations with triggers, preconditions, effects, and failure behavior;
- invariants and forbidden states;
- safety and liveness properties;
- authorization and delegation rules;
- concurrency, retries, idempotency, and ordering constraints;
- deletion, archival, retention, and referential-integrity rules;
- quantitative constraints and resource bounds;
- environmental assumptions and explicit abstractions, including the evidence and unknowns behind material external-system behavior.

Every formal item must cite one or more plan requirement IDs, or be labeled `derived`, `assumption`, or `verification-only`.

Before selecting tools, make a claim-to-evidence inventory: for each critical normative claim, record its quantification, the evidence mode it needs, whether it is included, and the IR items that encode it. This prevents a single-tool portfolio from appearing complete merely because incompatible claims were omitted.

### 3. Perform consistency checks before choosing a prover

Check the IR for obvious defects:

- duplicate entities with different names;
- incompatible cardinalities;
- state names used but never defined;
- operations that require unreachable preconditions;
- deletion rules that create dangling references;
- permissions that both grant and deny the same action without precedence;
- invariants that contradict required operations;
- liveness claims with no enabling path;
- undefined behavior after failure, timeout, retry, cancellation, or partial completion.

Do not treat this review as formal verification. It prepares the formalization.

### 3a. Audit external-system evidence

When the model depends on behavior controlled by another system, read `references/verification-portfolio-and-environment-fidelity.md`. Trace each material premise to the planner's external-system dossier or record an `ASSUMPTION_GAP`. A mock, fixture, generated client, current wrapper, or plan-authored schema is not independent provider evidence. Model unknown outcomes conservatively and carry a runtime characterization or adapter-conformance gate into implementation. Do not make external writes merely to complete formalization.

### 4. Choose the verification backend by obligation

Classify obligations before inspecting installed tools. Use the smallest faithful combination, not a favorite tool or an arbitrary tool-count target.

| Obligation | Preferred system | Typical result |
|---|---|---|
| Entity relations, ownership, cardinality, finite structural consistency | Alloy | Instance or bounded counterexample |
| Arithmetic, scheduling, permissions, policy constraints, satisfiability | SMT solver such as Z3 or cvc5 | `sat`, model, `unsat`, optional unsat core |
| Lifecycles, workflows, concurrency, retries, distributed behavior | TLA+ with TLC or Apalache | State trace or checked invariant/property |
| Mechanically checked TLA+ proof | TLAPS | Checked proof obligations |
| Unbounded inductive/dependent theorem, refinement, or certified definition | Lean, Rocq Prover (formerly Coq), or Arend | Kernel/type-checked theorem; optional extraction where supported |

A product can require multiple backends. Select more than one when critical claims require materially different evidence modes—for example relational structure, temporal interleavings, and an unbounded inductive or refinement theorem. Multiple tools count only when each owns a distinct claim, removes a material bound, checks a genuinely different abstraction, or provides an independent cross-check. Re-encoding the same bounded model merely to increase the tool count adds little assurance.

One backend is acceptable when the critical scope is genuinely homogeneous; record why. If a critical claim is intended to hold for arbitrary cardinalities, values, or inductive structures, a bounded Alloy, TLC, Apalache, or finite SMT run does not discharge it: add an unbounded proof obligation in TLAPS, Lean, Rocq, Arend, or an adequate deductive encoding, or record an explicit `BOUND_GAP`. Tool availability alone is not a selection rationale.

### 5. Write explicit verification obligations

At minimum, add:

1. **Satisfiability:** at least one valid initial/product state exists.
2. **Type and domain correctness:** every state stays inside declared domains.
3. **Invariant preservation:** every legal operation preserves required invariants.
4. **Reachability witnesses:** important allowed scenarios are reachable.
5. **Forbidden-state checks:** known bad combinations are unreachable.
6. **Non-vacuity:** key operations can be enabled and properties are not true only because behavior is impossible.
7. **Lifecycle completeness:** each terminal and recovery path is specified.
8. **Concurrency checks:** when concurrent execution is allowed, explore relevant interleavings.
9. **Liveness:** where the plan says "eventually", state fairness and environmental assumptions.
10. **Mutation sanity:** weaken or negate at least one important rule and confirm the checker can detect the defect.
11. **Portfolio coverage:** every included critical claim has an evidence mode and suitable backend, or an explicit gap.
12. **Environment fidelity:** every material external premise has evidence, conservative uncertainty, or an unresolved assumption plus a runtime conformance gate.

### 6. Implement the model

Prefer a minimal domain model that preserves the relevant semantics. Abstract implementation details that cannot affect the property, but document every abstraction.

For an external-system abstraction, record the represented and omitted outcomes, evidence provenance, confidence, provider version, and invalidation trigger. A formal proof establishes consequences of that abstraction; it does not prove that the real provider satisfies the premise.

Never silently strengthen the plan to make verification pass. Never delete or weaken a failing property without recording a plan decision.

Use stable IDs in comments, for example:

```text
REQ-ORD-014 -> invariant NoShipmentWhenCancelled
REQ-ORD-009 -> action Cancel
```

### 7. Execute the native tool

Record the exact tool version, command, configuration, bounds, solver, exit status, and output.

Common command shapes:

```bash
# TLA+/TLC
java -cp "$TLA2TOOLS_JAR" tlc2.TLC -config Model.cfg Model.tla

# Lean project
lake env lean Model.lean
# or
lake build

# Rocq Prover
rocq compile Model.v

# SMT-LIB with Z3
z3 Model.smt2
```

For Alloy, execute each `run` and `check` command in Alloy Analyzer or through a documented Analyzer API/automation wrapper, and save the generated instance or counterexample.

If the native tool is unavailable, do not report the model as verified. You may perform a fallback simulation or finite enumerator to debug the abstraction, but label it clearly as a fallback and preserve the native command for later execution.

### 8. Classify every result

For each failure, assign exactly one primary classification:

- `PLAN_DEFECT`: the source rules permit or require an invalid product state;
- `MODEL_DEFECT`: the formal translation does not faithfully encode the plan;
- `PROPERTY_DEFECT`: the asserted property is misstated or stronger/weaker than intended;
- `ASSUMPTION_GAP`: the result depends on an unstated environmental or fairness assumption;
- `BOUND_GAP`: a bounded scope is inadequate or misleading;
- `TOOL_OR_ENCODING_LIMIT`: the backend cannot express or decide the obligation adequately;
- `EXPECTED_COUNTEREXAMPLE`: a negative test or mutation behaved as intended.

Translate counterexamples into a domain narrative before proposing a repair.

### 9. Refine one layer at a time

For each iteration:

1. Freeze the failing model and run evidence.
2. Explain the counterexample using product terminology.
3. Identify whether the plan, model, property, assumption, or bound changes.
4. Change only the selected layer.
5. Update traceability and the refinement ledger.
6. Re-run all affected checks, plus regression checks.
7. Confirm that the repair did not make required behavior unreachable.

When a plan rule changes, produce a precise replacement statement suitable for insertion into the plan. A checker-generated repair is a proposal, not an accepted product decision: apply semantic plan changes only when the product owner or governing plan explicitly authorizes them. Model, property, assumption, and bound corrections must still be recorded and reviewed.

When new provider evidence changes an assumption, update the external-system dossier first. Use `refinement-ledger.md` to record the transition, invalidated models/runs/contracts, and required reruns; the ledger is history, not the current provider specification.

### 10. Stop only at the convergence gate

The verification cycle is complete only when:

- every normative plan claim within the documented verification scope is mapped, intentionally excluded, or marked non-formalizable;
- the model parses/type-checks in the selected native system;
- a valid initial state and key witness scenarios exist;
- all required checks pass for documented bounds/assumptions, or accepted exceptions are recorded;
- no counterexample is unresolved;
- important properties pass non-vacuity and mutation sanity checks;
- the plan, IR, model, and traceability matrix describe the same rules;
- the report distinguishes bounded checks from unbounded proofs;
- every critical claim's required evidence mode is covered by a suitable backend or an explicit accepted gap;
- every critical universal claim has unbounded evidence or an explicit `BOUND_GAP`;
- material external assumptions are evidence-linked or explicitly unresolved, with runtime conformance work carried into implementation;
- a human/domain owner has reviewed model fidelity.

Record one scoped status in `verification-report.md`: `Blocked`, `In refinement`, `Agreement reached — bounded`, `Agreement reached — proved`, or `Agreement reached — mixed`. Never use an unqualified claim such as "the product is proven correct."

### 10a. Update the human delivery status

Before yielding control because verification converged, remains in refinement, or is blocked, update `<plan-root>/delivery-status.md` as the main stage orchestrator:

- set the current stage and current status honestly;
- update the **Formal verification** row without changing the other stage histories;
- summarize the portfolio used, the most important result, any accepted bounds or gaps, and plan changes since the previous stage update;
- state the next operator decision or write `None`;
- link to `verification-report.md`, `03-traceability.md`, `refinement-ledger.md`, and the relevant run directories instead of copying proofs, traces, logs, or matrices;
- preserve the document's derived, non-authoritative authority statement.

After writing it, rerun the planner validator against the selected root and fix any human-status errors:

```bash
python3 <planner-skill-root>/scripts/validate_plan.py <repository-root> --plan-root <plan-root>
```

Then explicitly tell the operator that the human delivery status was updated, give the path, state the verification status, and say whether operator action is required.

### 11. Offer the implementation handoff

After the convergence gate passes, do not begin implementation automatically. Report the verified scope, unchecked or accepted residual risks, native tool evidence, the exact plan revision aligned with the formal models, and the path to the updated human delivery status. Then ask one direct handoff question:

**“The approved plan and formal models are aligned for the documented scope. Should I proceed with implementation using the `parallel-plan-implementation` skill?”**

Offer that direct handoff only when `<plan-root>` is the canonical `docs/implementation-plan/` expected by the downstream skill. For a non-default root, first offer normalization through `product-implementation-planner`; do not copy or relocate the verified corpus silently, and do not start parallel implementation until the normalized canonical plan is revalidated.

If convergence is blocked or unresolved, do not offer unrestricted implementation. State which phases, if any, remain safe and which decisions or obligations block the rest.

## Reporting language

Use exact claims:

- Good: "TLC explored the complete finite state space of this abstraction and found no violation of INV-003."
- Good: "Alloy found no counterexample within 6 users, 4 teams, and 8 projects."
- Good: "Rocq accepted theorem `delete_preserves_referential_integrity` with no admitted obligations."
- Bad: "The product is proven correct."
- Bad: "No bugs exist."

## Guardrails

- A prover checks the formal model, not the prose directly.
- A faithful model can still omit an unstated requirement.
- Several tools can repeat the same mistranslated rule or external-system assumption; tool diversity does not replace fidelity review.
- A mock or generated client is not evidence of provider behavior merely because tests pass against it.
- Passing a bounded check is not an unbounded proof.
- An over-constrained model can pass vacuously.
- Liveness depends critically on fairness and environment assumptions.
- The formal model must remain smaller and clearer than the implementation plan.
- The human delivery status is a concise derived view; never use it instead of the plan, traceability matrix, run evidence, refinement ledger, or verification report.
- Never use `Admitted`, `sorry`, unchecked axioms, or equivalent escape hatches in a final proof without prominently reporting them.

## Package references

Read `README.md` for the full pipeline and worked example. Read `references/verification-portfolio-and-environment-fidelity.md` before choosing backends or trusting a material external-system abstraction. Start new projects from the templates under `templates/`.
