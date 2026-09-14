# Verification Portfolio and Environment Fidelity

Use this reference before choosing formal backends and whenever a model consumes behavior controlled by a real external or separately operated system.

Two questions are independent:

1. Which evidence mode is appropriate for each product claim?
2. Is the model's environment grounded in evidence about the real system?

More tools do not repair a shared mistranslation or false provider assumption.

## Choose tools from obligations

Inventory the critical normative claims before selecting tools. For each claim, record its source ID, quantification, required evidence mode, formal IR items, selected backend, bounds or assumptions, and any explicit gap.

Typical choices are:

| Evidence need | Suitable systems | Important limitation |
|---|---|---|
| Relational structure, ownership, and cardinality | Alloy | Results are bounded by the selected scope |
| Arithmetic, allocation, scheduling, and policy constraints | Z3 or cvc5 | Finite encodings remain bounded; a general formula may be deductive |
| Lifecycles, concurrency, retries, safety, and liveness | TLA+/TLC or Apalache | TLC is complete for its configured finite abstraction, not arbitrary data domains |
| Mechanically checked temporal proofs | TLAPS | Fidelity still depends on the TLA+ specification |
| Unbounded inductive, dependent, or refinement theorems | Lean, Rocq, or Arend | Final claims must not hide admitted goals or unchecked axioms |

Use multiple backends when critical claims require materially different evidence modes. Each backend should contribute something concrete: own a distinct claim, remove a material bound, check a meaningfully different abstraction, establish refinement, or provide a justified independent cross-check.

Do not add tools ceremonially. One backend is legitimate for a genuinely homogeneous scope when the report explains why. Conversely, if a claim is intended to hold for arbitrary cardinalities, values, or inductive structures, bounded exploration alone is insufficient: add an unbounded proof obligation or retain an explicit `BOUND_GAP` with residual risk and ownership.

Choose the portfolio before checking local tool availability. Missing tooling leaves the obligation blocked, motivates a suitable alternate backend, or becomes an explicit reviewed exception; it must not silently narrow the verified scope.

## Ground environment abstractions

For each material external premise, trace the abstraction to the planner's current external-system dossier and record:

- the provider behavior represented and evidence supporting it;
- success, failure, timeout, retry, ordering, partial-success, duplicate, stale-read, and ambiguous-write outcomes where applicable;
- behavior omitted and why it cannot affect the checked property;
- confidence, provider version/environment, and invalidation triggers;
- the formal obligations that depend on it;
- the runtime characterization or real-adapter conformance check that must occur later.

Unknown behavior should normally be modeled conservatively or retained as an `ASSUMPTION_GAP`. A formal tool can prove consequences of an environmental assumption; it cannot prove that an uncontrolled provider satisfies that assumption.

Keep these distinct:

- a formal environment abstraction used by a prover or model checker;
- a runtime mock, fake, fixture, emulator, or generated client;
- provider evidence such as documentation, schemas, legacy behavior, sanitized captures, or safe observations.

The first two consume evidence. Agreement between them is not independent confirmation of provider behavior.

## Evidence changes and implementation handoff

When new provider evidence changes a claim, update the external-system dossier first. Then record in `refinement-ledger.md` which assumptions, models, runs, normalized contracts, test doubles, and implementation gates were invalidated and which checks must rerun.

Carry unresolved provider assumptions into implementation as named characterization or conformance gates. Do not perform a live write merely to close a formalization gap; preserve the limitation unless the exact external action is authorized.

## Portfolio review

Before claiming agreement, ask:

- Does every included critical claim have the evidence mode it actually needs?
- Did tool availability bias the claim inventory or backend choice?
- Are bounded results reported with their real domains and assumptions?
- Do universal claims have unbounded evidence or an explicit gap?
- Does each additional backend make a distinct contribution?
- Could several tools share the same mistranslated rule or provider premise?
- Are proof-assistant results free of admitted goals and unreported axioms?
- Does every material external premise have a downstream real-system conformance gate?
