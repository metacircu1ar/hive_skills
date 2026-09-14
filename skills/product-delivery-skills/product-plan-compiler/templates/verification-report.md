# Product Plan Compilation and Verification Report

## 1. Executive conclusion

- Agreement status: `Blocked` | `In refinement` | `Agreement reached — bounded` | `Agreement reached — proved` | `Agreement reached — mixed`
- Accepted plan version:
- Summary:

State exactly what was checked, with which tools, under which assumptions and bounds. Do not claim that the implementation or whole product is proven correct unless that exact claim is justified.

## 2. Plan and scope

- Source plan/root:
- Source version/commit:
- Included scope:
- Excluded scope:
- Abstractions:
- Domain owner/reviewer:

## 3. Formal backends

| Backend | Version | Purpose | Native command | Scope/bounds |
|---|---|---|---|---|

## 4. Traceability coverage

| Plan requirement | Formal item(s) | Model symbol(s) | Check/proof | Status |
|---|---|---|---|---|

## 5. Results

| Obligation | Result | Evidence run | Interpretation |
|---|---|---|---|

## 6. Counterexamples and refinements

For each issue, include the product-language trace, classification, changed layer, exact plan/model change, responsible decision, and regression result.

## 7. Non-vacuity and mutation checks

Document witness scenarios, operation coverage, and deliberately broken variants that the checker successfully rejected.

## 8. Assumptions and bounds

List fairness, environment, trust, clock, delivery, uniqueness, integer, entity-count, and trace bounds.

## 9. Implementation obligations

List formal invariants, contracts, state transitions, or generated test obligations that implementation must preserve.

## 10. Residual risks and accepted exclusions

List omissions, undecided requirements, unsupported properties, state-space reductions, accepted exceptions, and the gap between model and implementation.

## 11. Final agreement gate

- [ ] Every included normative requirement is mapped or explicitly excluded.
- [ ] Native tools parsed/type-checked all final models.
- [ ] Required checks/proofs pass for documented scope.
- [ ] No counterexample remains unresolved.
- [ ] Witness and non-vacuity checks pass.
- [ ] Mutation checks detect deliberately introduced defects.
- [ ] Plan, normalized requirements, IR, model, and properties agree.
- [ ] Bounded checks and unbounded proofs are distinguished.
- [ ] No unreported proof escape hatch is present.
- [ ] Domain owner reviewed model fidelity.
- [ ] Implementation handoff is explicitly approved or not yet authorized.
