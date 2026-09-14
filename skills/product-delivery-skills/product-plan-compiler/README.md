# Product Plan Compiler

A companion Agent Skill that runs after `product-implementation-planner` and before `parallel-plan-implementation`.

It treats a detailed product, feature, modernization, migration, remediation, or system plan as source code for a higher-level compiler: the skill extracts a formal domain model for the approved scope, projects that model into relevant prover/model-checker systems, executes the native tools, translates diagnostics back into product language, and iterates on the plan and model until they are traceably aligned.

The object being checked is the **product design itself**: entities, relationships, state transitions, business rules, permissions, failure behavior, concurrency, deletion and retention rules, quantitative constraints, and temporal requirements. It is not merely the protocol used by the agents that authored the plan.

## Delivery-stage placement

```text
product-implementation-planner
              |
              | implementation plan complete for its approved scope
              v
     product-plan-compiler
              |
              | plan-model agreement and verification evidence
              v
 parallel-plan-implementation
              |
              | integrated phase commits
              v
    phase-commit-reviewer
```

`product-plan-compiler` does not implement product code. It creates a verification gate between architecture/planning and implementation.

## Formal compilation pipeline

```text
                    Detailed product plan
                             |
                             v
                  Normalized requirement set
              (stable IDs, glossary, assumptions)
                             |
                             v
                    Formal domain IR
                             |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
   Entity model         State/interaction      Properties
                         model

   entities             states                 invariants
   relations            operations             safety
   ownership            preconditions          liveness
   cardinality          effects                authorization
   retention            failures               non-vacuity
        |                    |                    |
        +--------------------+--------------------+
                             |
                             v
                    Backend selection
                             |
      +-------------+--------+--------+-------------+
      |             |                 |             |
      v             v                 v             v
  Alloy / SMT    TLA+ / TLC       Lean          Rocq

  structure      lifecycle,       unbounded     unbounded
  constraints    concurrency,     inductive     inductive
  finite worlds  temporal rules   proofs        proofs/extraction
      |             |                 |             |
      +-------------+--------+--------+-------------+
                             |
                             v
                    Native tool execution
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
             counterexample          checked result
                 |                       |
                 v                       v
       explain in plan language     coverage review
                 |                       |
                 +-----------+-----------+
                             |
                             v
             refine plan / model / property /
                  assumption / verification bound
                             |
                             +------ repeat ------+
                             |
                             v
              Traceable plan-model agreement
                             |
                             v
                    Implementation agents
```

This is intentionally compiler-like:

```text
prose plan -> formal intermediate representation -> prover backends -> diagnostics
```

The central engineering artifact is the formal IR. It lets the same product rules be projected into multiple formal systems without allowing each backend model to drift into a different product definition.

## What the skill produces

When used with the canonical planner output, a run leaves behind:

```text
<plan-root>/
  delivery-status.md             concise derived operator view
  formal-verification/
    00-scope-and-sources.md       source baseline, plan version, included scope
    01-normalized-plan.md         canonical terminology and requirement IDs
    02-formal-ir.yaml             entities, operations, properties, assumptions
    03-traceability.md            plan <-> IR <-> model <-> result links
    04-open-questions.md          unresolved semantic choices
    models/                       native formal source files by backend
    runs/                         immutable commands, versions, output, traces
    refinement-ledger.md          why each iteration changed
    verification-report.md        final scoped conclusion and handoff status
```

`<plan-root>` defaults to `docs/implementation-plan/`. For a plan stored elsewhere, the skill places `formal-verification/` and `delivery-status.md` under that selected root, records the choice, and invokes the planner validator with `--plan-root <plan-root>`.
At the end of the verification stage, the main compiler agent updates the **Formal verification** row in `<plan-root>/delivery-status.md` and explicitly tells the operator its path, current status, and any required decision. The detailed verification report and immutable run evidence remain authoritative.
Direct handoff to `parallel-plan-implementation` requires the canonical default root; a verified non-default corpus must first be explicitly normalized there through the planner and revalidated.

## Formal intermediate representation

The IR is not intended to be a universal formal language. It is a disciplined, reviewable bridge between prose and backend-specific models.

It captures:

- **Entities:** identity, attributes, existence, ownership, retention.
- **Relations:** source, target, cardinality, uniqueness, lifecycle behavior.
- **States:** legal values, initial states, terminal states.
- **Operations:** trigger, parameters, preconditions, effects, failure behavior, idempotency.
- **Properties:** invariants, forbidden states, required reachability, safety, liveness.
- **Authorization:** actors, capabilities, grants, denies, inheritance, revocation.
- **Concurrency:** atomicity boundaries, ordering, locks, races, retries.
- **Assumptions:** environment, fairness, clocks, delivery, uniqueness, trusted components.
- **Bounds:** finite scopes used by model checkers.
- **Traceability:** stable source requirement IDs for every formal element.

See `templates/formal-ir.yaml`.

## Selecting a formal system

| System | Use it primarily for | What success means |
|---|---|---|
| Alloy | Relational structures, cardinalities, ownership, finite structural consistency; Alloy 6 can also express temporal behavior | No counterexample in an explicit scope, plus useful witness instances |
| SMT, such as Z3 or cvc5 | Satisfiability, arithmetic, allocation, scheduling, policy combinations, bounded transition encodings | `sat` with a model, or `unsat` under stated constraints; optionally an unsat core |
| TLA+ with TLC | Lifecycle interactions, concurrency, retries, failure interleavings, safety and liveness over an abstract state machine | TLC explores the configured state space and reports traces or no violation |
| TLA+ with Apalache | Symbolic bounded checking and inductive invariant work for suitable finite-data specifications | Solver-backed result under encoded bounds and assumptions |
| TLAPS | Mechanically checked proofs written in TLA+ | All proof obligations accepted |
| Lean | Inductive proofs, refinement, executable mathematical definitions, unbounded arguments | Kernel accepts required theorems without unreported `sorry` or axioms |
| Rocq Prover, formerly Coq | Inductive/dependent proofs, certified definitions, optional extraction to executable code | Kernel accepts required theorems without `Admitted` or unreported axioms |

Use multiple tools when the plan has different classes of obligations. A common combination is:

```text
Alloy or SMT  -> structural and constraint consistency
TLA+          -> behavior and interleavings
Lean or Rocq  -> strongest critical invariants and refinement theorems
```

## Iterative verification protocol

### Phase A — Baseline and extract

1. Read the complete in-scope planning set and the baseline evidence needed to understand its impact cone.
2. Record source files, versions, scope, exclusions, and existing decision gates.
3. Assign stable IDs to normative claims.
4. Build a glossary.
5. Extract entities, relations, lifecycles, operations, permissions, assumptions, and properties.
6. Preserve ambiguities and contradictions instead of silently resolving them.
7. Review the IR against the source plan.

### Phase B — Challenge the model before proving it

Check:

- Is there at least one valid initial state?
- Are key allowed scenarios reachable?
- Can each important operation ever execute?
- Are forbidden scenarios actually expressible in the model?
- Are failure, retry, cancellation, deletion, retention, and revocation represented?
- Is concurrency modeled wherever the plan permits it?
- Could an invariant pass only because behavior is over-constrained?
- Did the abstraction erase a product distinction that matters to the property?

### Phase C — Implement and run

1. Decompose the plan into explicit verification obligations.
2. Select the backend for each obligation.
3. Implement the smallest faithful model.
4. Add source requirement IDs to model comments.
5. Run the native parser/checker/prover.
6. Save commands, versions, configuration, bounds, output, and exit status.
7. Convert traces or failed proof goals into product-language explanations.

### Phase D — Refine

Each failure is classified as a defect in one primary layer:

```text
plan | translation/model | property | assumption | bound | tool/encoding
```

Only that layer is changed in the next iteration. Earlier run evidence remains immutable.

For a product-plan defect, the model is not silently patched. The skill writes the exact replacement requirement, records the product decision, updates the plan, then reruns the model and all affected regressions.

### Phase E — Converge

Stop only after:

- all included normative requirements are mapped or explicitly excluded;
- all selected native tools accept the final models/proofs for documented scopes;
- witness, non-vacuity, and negative/mutation tests behave as intended;
- no counterexample or proof obligation remains unexplained;
- plan text and formal semantics use the same rules;
- bounded results and unbounded proofs are clearly distinguished;
- a domain owner or responsible decision-maker approves model fidelity.

The final report uses one of these scoped statuses:

```text
Blocked
In refinement
Agreement reached — bounded
Agreement reached — proved
Agreement reached — mixed
```

## Small worked example: order cancellation

### Product plan, version 0

```text
REQ-001  A customer may cancel any order that has not been delivered.
REQ-002  The warehouse may create a shipment after the order is paid.
REQ-003  A cancelled order must not have a shipment.
REQ-004  Shipment records are immutable and cannot be deleted.
```

The entities are ordinary product-domain objects:

```text
Order
Shipment
```

The extracted state is:

```text
Order.status      in {Created, Paid, Shipped, Delivered, Cancelled}
Order.paid        in Boolean
Order.hasShipment in Boolean
```

The extracted operations are:

```text
Pay
CreateShipment
Deliver
Cancel
```

The key invariant from `REQ-003` is:

```text
Order.status = Cancelled  =>  Order.hasShipment = false
```

### Why TLA+ is selected

The suspected inconsistency depends on an operation sequence rather than only a static entity graph. TLA+ with TLC is therefore a natural first backend.

The initial cancellation rule directly follows `REQ-001`:

```tla
CancelBad ==
    /\ status \in {"Created", "Paid", "Shipped"}
    /\ status' = "Cancelled"
    /\ UNCHANGED <<paid, hasShipment>>
```

The invariant is:

```tla
NoShipmentWhenCancelled ==
    status = "Cancelled" => ~hasShipment
```

The full model is in:

```text
examples/order-cancellation/OrderLifecycle_Buggy.tla
```

### Counterexample

The shortest violating product history is:

```text
1. Pay
   status = Paid, hasShipment = false

2. CreateShipment
   status = Shipped, hasShipment = true

3. CancelBad
   status = Cancelled, hasShipment = true
```

`REQ-001` permits cancellation because the order has not been delivered. `REQ-003` forbids the resulting state, and `REQ-004` prevents repairing it by deleting the shipment record.

This is a **product-plan defect**, not an implementation defect.

### Refine the plan

A minimal product decision is:

```text
REQ-001-v2  A customer may cancel an order only before a shipment has been
            created. After shipment creation, the customer must use the
            return/refusal workflow instead of cancellation.
```

The corrected operation becomes:

```tla
Cancel ==
    /\ status \in {"Created", "Paid"}
    /\ ~hasShipment
    /\ status' = "Cancelled"
    /\ UNCHANGED <<paid, hasShipment>>
```

The corrected model is:

```text
examples/order-cancellation/OrderLifecycle_Fixed.tla
```

For this finite abstraction, exhaustive exploration finds six reachable states and no violation of `NoShipmentWhenCancelled` after the repair. The bundled fallback checker reproduces that result:

```bash
python3 scripts/check_example.py
```

Expected output:

```text
Buggy model
  reachable states before/including first violation: 7
  shortest invariant-violating trace:
  1. Pay: status=Paid, paid=True, hasShipment=False
  2. CreateShipment: status=Shipped, paid=True, hasShipment=True
  3. CancelBad: status=Cancelled, paid=True, hasShipment=True

Fixed model
  reachable states: 6
  invariant violation: no
```

The Python checker is only a portability fallback mirroring this tiny state machine. It does not replace native TLC evidence.

### Run the example with TLC

With `tla2tools.jar` available:

```bash
export TLA2TOOLS_JAR=/absolute/path/to/tla2tools.jar
./scripts/run_tla_example.sh
```

The script expects the buggy model to fail its invariant and the fixed model to pass.

## What "all is in agreement" means

Convergence is not merely a green checker result. These artifacts must agree:

```text
source plan
    <-> normalized requirements
    <-> formal IR
    <-> backend models
    <-> checked properties and assumptions
```

The following are failures of agreement:

- the plan says cancellation is allowed but the model silently disables it;
- the model proves an invariant that was never required by the plan;
- an operation in the plan has no formal transition;
- a model checker finds no issue because the initial state is unsatisfiable;
- a liveness property passes under a fairness assumption absent from the plan;
- a bounded result is reported as an unbounded proof;
- a plan fix exists only in a model while contradictory plan prose remains;
- Lean or Rocq accepts a required theorem through an unreported escape hatch.

## Suggested evidence ledger

Each iteration should record:

| Field | Example |
|---|---|
| Iteration | `ITER-003` |
| Trigger | `INV-007 failed` |
| Counterexample | `Paid -> Shipped -> Cancelled` |
| Classification | `PLAN_DEFECT` |
| Plan change | `REQ-001 replaced by REQ-001-v2` |
| Model change | `Cancel precondition requires no shipment` |
| Tool and version | `TLC ...` |
| Scope/bounds | finite single-order abstraction |
| Result | invariant passes; reachability regression passes |
| Remaining risk | return workflow not yet modeled |

## Native command examples

```bash
# TLA+/TLC
java -cp "$TLA2TOOLS_JAR" tlc2.TLC -config Model.cfg Model.tla

# Lean
lake env lean Model.lean

# Rocq Prover; source files conventionally use .v
rocq compile Model.v

# Z3 / SMT-LIB
z3 Model.smt2
```

Alloy Analyzer uses `run` commands to find satisfying instances and `check` commands to search for assertion counterexamples. Save the exact scope and generated instance/counterexample with the run evidence.

## Quality controls that prevent false confidence

1. **Witness checks:** demonstrate allowed states and scenarios, not only absence of bad states.
2. **Mutation checks:** weaken a critical guard or negate a property and confirm failure is detected.
3. **Operation coverage:** confirm every important operation is enabled in at least one reachable state.
4. **Traceability:** every formal rule points to the plan; every normative plan rule maps back.
5. **Assumption review:** clocks, fairness, network delivery, uniqueness, and trust boundaries are explicit.
6. **Scope review:** state counts, entity bounds, integer bounds, and trace depths are reported.
7. **No proof escapes:** no admitted theorem, unreported axiom, or fallback-only run is hidden in a passing conclusion.
8. **Independent fidelity review:** a domain reviewer checks that the abstraction matches the intended product.

## Package contents

```text
SKILL.md
README.md
manifest.txt
templates/
  formal-ir.yaml
  normalized-plan.md
  traceability.md
  open-questions.md
  run-result.md
  verification-report.md
  refinement-ledger.md
examples/
  order-cancellation/
    PLAN.md
    OrderLifecycle_Buggy.tla
    OrderLifecycle_Buggy.cfg
    OrderLifecycle_Fixed.tla
    OrderLifecycle_Fixed.cfg
    RESULTS.md
scripts/
  check_example.py
  run_tla_example.sh
```

## Installation path in hive_skills

```text
skills/product-delivery-skills/product-plan-compiler/
```

A repository-ready archive in this delivery also contains the updated top-level `README.md`, so it can be unpacked at the root of `hive_skills`.

## References

- Rocq Prover documentation: <https://rocq-prover.org/docs>
- Rocq command reference: <https://rocq-prover.org/doc/v9.2/refman/practical-tools/coq-commands.html>
- TLA+ tools: <https://lamport.azurewebsites.net/tla/tools.html>
- TLA+ command-line tools repository: <https://github.com/tlaplus/tlaplus>
- Alloy documentation: <https://alloytools.org/documentation.html>
- Alloy 6 temporal modeling: <https://alloytools.org/alloy6.html>
- Lean reference manual: <https://lean-lang.org/doc/reference/latest/>
- Z3 guide: <https://microsoft.github.io/z3guide/>
