# External-System Fidelity During Implementation

Use this reference only for approved phases that materially depend on a third-party API, a separately operated internal service, a legacy service being replaced, hardware, a queue, or a file exchange. Purely internal phases do not need provider material.

The goal is to prevent an adapter, its test double, and its tests from agreeing with the same unsupported assumption.

## Preflight

Before freezing an external-adapter boundary, locate the planner's current external-system dossier and identify:

- the provider behaviors this phase must implement and the evidence supporting them;
- provider/API version, environment, contradictions, unknowns, and revalidation triggers;
- the product-owned normalized port and its mapping from provider outcomes;
- test-double provenance, omissions, and known differences;
- characterization or conformance checks and the external access they require.

If material behavior lacks evidence, return a contract or decision blocker rather than inventing provider semantics. Public documentation and repository-owned evidence may be researched read-only; update the dossier when that research changes the current truth.

## Keep two boundaries separate

```text
provider evidence -> uncontrolled provider protocol -> real adapter
    -> product-owned normalized port -> consumer
```

A fake of the normalized port may enable consumer work in parallel. It proves only consumer conformance to the product contract. The consumer should receive that contract, the fake's limitations, and shared contract tests—not raw provider details that would couple it to the adapter.

A provider-protocol emulator may support adapter tests only when it records the independent evidence it follows, represented provider version/environment, normal and failure behavior, omissions, and known differences. It remains an evidence consumer, not evidence of provider behavior.

The adapter phase stays implementation-bound or decision-gated until independent characterization or conformance can distinguish real-adapter behavior from mock behavior. Mock-only green tests are insufficient.

## Implement and check

Use the strongest safe evidence appropriate to the phase:

- tests derived from versioned documentation or machine-readable provider contracts;
- legacy-client characterization, treated as evidence of prior product dependence;
- sanitized request/response/error replay;
- authorized read-only sandbox or staging observations;
- the same normalized-port contract suite against the fake and real adapter;
- differential comparison at the normalized-port boundary;
- dry-run, shadow, bounded canary, or controlled writes only when separately authorized.

Record which provider claims each check exercises and what remains untested. If a real-provider check is unavailable, preserve the gate with a risk owner and compensating control rather than reporting adapter fidelity.

## Authorization

Private documentation, credentials, and live systems must be inside the approved scope. Read authorization never implies write authorization. Do not create, mutate, delete, submit, merge, upload, publish, consume material quota, or perform destructive cleanup merely because credentials or a sandbox exist. Sanitize captures and keep secrets, personal data, and confidential payloads out of prompts, fixtures, dossiers, and ledgers.

## Discrepancies and ledgers

The external-system dossier is the current source of truth. The implementation ledger records how execution responded to changes; it is not a second provider specification.

When implementation or a safe observation contradicts the dossier:

1. stop affected adapter integration and newly enabled writes;
2. update the dossier's claim, evidence, confidence, contradictions, and revalidation trigger;
3. identify affected contracts, test doubles, adapters, consumer assumptions, formal results, phase results, and rollout gates;
4. apply contract change control and rerun affected characterization, conformance, contract, and product checks;
5. record the discrepancy, invalidations, decisions, and rerun evidence in the implementation ledger.

Never preserve a green result by updating only the mock.
