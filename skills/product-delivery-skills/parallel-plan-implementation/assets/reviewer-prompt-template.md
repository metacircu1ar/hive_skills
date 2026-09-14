# Reviewer Assignment — <PH-###-##>

## Required runtime profile

- **Reviewer skill:** `phase-commit-reviewer`
- **Requested model:** `gpt-5.6-sol`
- **Requested reasoning effort:** `xhigh`
- **Approved actual model:** `<actual-or-unknown>`
- **Approved actual reasoning effort:** `<actual-or-unknown>`
- **Selection status:** `<confirmed|host-unverifiable|unavailable|substituted>`
- **Substitution approved:** `<yes|no>`

Return `MODEL_BLOCKER` without reviewing when the requested profile is unavailable and no approved substitution is recorded.

## Review identity

- **Phase:** `<PH-###-##>`
- **Component:** `<CMP-###>`
- **Target commit:** `<target-commit>`
- **Target first parent:** `<target-parent>`
- **Frozen final review baseline:** `<review-baseline-commit>`
- **Detached target-commit review worktree or immutable target snapshot:** `<absolute-path>`
- **Findings output:** `docs/implementation-plan/parallel-implementation/parallel-review/findings/<phase-id-lowercase>.json`
- **External fidelity required:** `<true|false>`

## Approved delivery scope

<!-- approved-scope:begin -->
{"delivery_scope_mode":"<full product|scoped change|modernization or migration|remediation or reliability>","requested_outcome":"<JSON-escaped string>","impact_cone":"<JSON-escaped string>","preserved_behavior":["<exact entries>"],"non_goals":["<exact entries>"]}
<!-- approved-scope:end -->

You are one fresh, independent, read-only reviewer for exactly this phase commit. Verify that the supplied checkout is pinned to `<target-commit>`; use Git object reads to compare with the frozen final baseline. Do not edit, format, generate, commit, merge, rebase, amend, create branches, post external comments, or mutate production systems.
Treat the supplied preservation, compatibility, coexistence, migration, rollback, and non-goal constraints as explicit review obligations whenever the target can affect them.

## Required skill and protocol

1. Load installed `phase-commit-reviewer` version `1.3.0` or newer; return `SCOPE_BLOCKER` when that compatible version is unavailable.
2. Read its `references/code-review-skill.md` completely.
3. Return a result conforming exactly to the reviewer-result JSON schema supplied by that installed skill.
4. When the companion reviewer skill is not installed, return `SCOPE_BLOCKER`; do not improvise a reduced review.

## Required product context

Read completely where relevant:

1. `<product description path>`
2. `<system architecture paths>`
3. `<component plan path>` — exact section `<phase section>`
4. `<component boundary path>` — exact section `<boundary section>`
5. `<consumed canonical contract paths>`
6. `<produced canonical contract paths>`
7. `<domain, data, interface, security, testing, operations, migration, and delivery paths>`
8. `<repository instruction files governing changed paths>`
9. `<phase-to-commit map path>`
10. `<later-phase summaries and relevant later commit IDs>`

## External fidelity context

Do not infer or override `external_fidelity_required`.

- When `true`: read `<external-system dossier and evidence paths>`, `<known gaps>`, `<test-double provenance and omissions>`, `<provider version and environment>`, and `<characterization or conformance results>`.
- When `false`: this context is not applicable; do not request raw provider material merely because the product has another external integration.

## Intended phase outcome

<Exact objective, requirements, in-scope work, non-scope, exit criteria, migration/operational obligations, and downstream guarantees>

## Target diff

Use only the selected first-parent diff as the introduced patch:

```bash
git diff --find-renames --find-copies <target-parent> <target-commit>
git show --stat --summary <target-commit>
```

Inspect enclosing code at the target commit and the corresponding final state at `<review-baseline-commit>`. Trace affected callers, callees, deleted invariants, tests, migrations, generated artifacts, configuration, deployment behavior, and later phases as required by the reviewer skill.

## Contracts

### Consumed

| Contract ID | Canonical path | Version | Required guarantee |
|---|---|---|---|

### Produced

| Contract ID | Canonical path | Version | Required obligation |
|---|---|---|---|

## Complete phase history context

| Integration index | Phase ID | Original commit | Outcome summary |
|---:|---|---|---|

Later phases may fix or supersede behavior. Record whether every candidate remains present at the frozen final baseline.

## Safe validation commands

```text
<read-only commands>
```

Run only commands that do not modify tracked files, snapshots, generated output, external systems, or production-connected resources. Record every attempted command and result. Do not fabricate validation.

## Output requirements

Return one JSON object and no surrounding prose.

- Maximum 15 findings.
- Include only `CONFIRMED` or well-supported `PLAUSIBLE` candidates.
- State the concrete trigger, wrong result or cost, and exact evidence.
- State whether the target commit introduced the issue and whether it remains at the final baseline.
- Recommend the earliest responsible phase, fix direction, and regression test.
- Return an empty findings array when nothing survives verification.
