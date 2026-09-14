---
name: parallel-plan-implementation
description: Implements an approved, validated product or change plan through contract-first boundaries, evidence-backed external adapters, dependency-aware parallel waves, isolated Git worktrees, specialized implementor agents, ordered phase commits, and an optional parallel phase-commit review. Use for full-product, scoped feature, modernization or migration, and remediation or reliability plans under docs/implementation-plan/, and only after explicit implementation approval. After the approved scope is integrated and the repository is buildable and passing, it separately asks whether fresh reviewer agents should inspect every phase commit; the main agent verifies findings, amends fixes and practical regression tests into the responsible commits, safely replays descendants, and restores a clean passing tip.
metadata:
  version: "2.5.0"
  compatibility: "Requires a filesystem-enabled coding agent, Python 3 validation, Git worktrees, product build/test tooling, and a host that can spawn isolated subagents. Human-status-aware handoff requires `product-implementation-planner` >= 2.5.0. Requested profiles: main `gpt-5.6-sol`/`ultra`, implementors `gpt-5.6-terra`/`xhigh`, reviewers `gpt-5.6-sol`/`xhigh`; substitutions need explicit approval. Optional review requires `phase-commit-reviewer` >= 1.3.0."
  companion-for: "product-implementation-planner"
  companion-version: ">=2.5.0"
  reviewer-skill: "phase-commit-reviewer"
  reviewer-skill-version: ">=1.3.0"
---

<!--
COMPLETE SKILL DESCRIPTION

This skill takes an explicitly approved and validated product or change implementation plan under `docs/implementation-plan/` and turns it into a controlled, contract-first implementation, integration, and optional review workflow. The main agent acts as implementation orchestrator, contract owner, integration lead, and reviewer-of-reviewers. It first verifies repository state, delivery scope mode, impact cone, preserved behavior, plan readiness, unresolved decision gates, requested model profiles, Git and worktree support, build and test tooling, and the exact set of authorized component phases. It re-reads the complete in-scope planning set and relevant baseline evidence rather than relying on a summary.

Before parallel coding begins, the skill constructs a dependency graph and writes implementation orchestration artifacts under `docs/implementation-plan/parallel-implementation/`. For every authorized phase, it produces a boundary definition describing exactly what the phase may rely on from predecessors and what it must provide to consumers. Boundaries include public symbols, module paths, endpoints, schemas, events, commands, configuration keys, behavior, errors, transactions, consistency, concurrency, retries, timeouts, idempotency, migration ownership, compatibility, test doubles, contract tests, owned paths, read-only paths, shared paths, generated paths, forbidden paths, and integration prerequisites. Public contracts are materialized and frozen as implementation-neutral artifacts before consumer phases launch. For material external systems, product-owned port fakes may enable consumer parallelism, but they do not establish provider or adapter fidelity; adapter work remains gated on independent evidence and characterization or conformance. Dependencies are classified as independent, contract-bound, implementation-bound, or decision-gated, and only genuinely safe units are placed in the same parallel wave.

For each eligible phase, the skill creates a dedicated branch and Git worktree and launches one fresh implementor agent with the requested `gpt-5.6-terra` / `xhigh` profile when the host supports it. Every implementor receives the typed approved-scope fields, exact product context, architecture, component plan, phase section, boundary section, consumed and produced contracts, predecessor guarantees, path ownership, repository instructions, validation commands, deliverables, and exit criteria. Workers must not guess through contract gaps, expand the approved scope, edit outside their ownership, or change canonical contracts unilaterally. They implement, test, commit, and return structured evidence. The main agent reviews each result and integrates completed phases in topological dependency order, not completion order, producing one identifiable logical commit per phase and validating contracts, migrations, affected components, generated artifacts, and the complete repository as required. New waves launch only from a known passing integration checkpoint.

After every authorized phase is integrated and the repository is clean, buildable, and passing, the skill asks the user whether parallel review is required. If approved, it creates review manifests and one context-complete assignment per phase commit, then launches one fresh read-only reviewer agent per commit using the requested `gpt-5.6-sol` / `xhigh` profile. Each reviewer is pinned to the exact parent-to-target commit diff and receives the relevant plans, boundaries, contracts, repository rules, callers and callees, phase map, later-phase summaries, and frozen final baseline. Reviewers use the phase-aware xhigh code-review protocol and return structured findings without editing code or Git history.

The main agent independently verifies every reported finding, rejects false positives, deduplicates shared mechanisms, determines whether an issue remains in the final state, assigns each confirmed issue to the earliest responsible phase, and designs a regression test where practical. It then performs one controlled history reconstruction from the earliest affected phase: creates a backup reference and rewrite branch, amends fixes and phase-valid tests into the responsible phase commits, replays all later commits in order, preserves corrected earlier invariants and intended later behavior, resolves conflicts, records the old-to-new commit map, and reruns the complete validation suite. After implementation and again after optional review, it updates the derived cross-stage `delivery-status.md` and explicitly tells the operator where to read the concise result. It never silently rewrites published or protected history, never force-pushes without separate authorization, and never claims parallel execution or model identities the host did not actually provide.

Primary inputs: an approved validated planning set, repository state, authorized phase IDs, user implementation approval, applicable external-system evidence and access limits, and optional later review approval.
Primary outputs: frozen boundaries and contracts, execution and review manifests, worker and reviewer prompts, isolated phase branches/worktrees, one logical commit per phase, implementation and review ledgers, an updated human delivery status, verified fixes and regression tests, commit mappings, and a final clean buildable passing repository.
Explicit non-goals: maximizing worker count at the expense of safety, allowing prose-only or unstable interfaces, merging by finish time, letting workers invent architecture, accepting reviewer findings without verification, silently substituting models, rewriting shared history without authorization, or finishing while required checks fail.
-->

# Parallel Plan Implementation

## Role

Act as the principal implementation orchestrator, contract owner, integration lead, and reviewer-of-reviewers.

Transform an approved, validated planning set into working product code without allowing independently operating agents to invent incompatible interfaces or rely on unseen implementation details. Maximize safe parallelism, not raw worker count. After implementation is green, offer an optional independent review of every phase commit and integrate only findings the main agent verifies.

## Required execution profiles

Read `references/agent-model-policy.md` before dispatching any subagent.

| Role | Requested model | Reasoning effort |
|---|---|---|
| Main agent | `gpt-5.6-sol` | `ultra` |
| Implementor agent | `gpt-5.6-terra` | `xhigh` |
| Reviewer agent | `gpt-5.6-sol` | `xhigh` |

Record requested and actual profiles in `execution-manifest.json`. A skill cannot retroactively change the model already running the main agent. When the host cannot select or verify a required profile, disclose the limitation and obtain explicit approval before substitution; never claim a profile the host did not expose.

## Primary outcome

Create and execute a controlled implementation workflow in which:

- every implementation unit maps to one stable component-phase ID such as `PH-001-00`;
- every worker receives the typed approved scope, a precise plan, frozen boundary, path ownership, and validation contract;
- every external-adapter worker receives the applicable evidence, known gaps, test-double limitations, access authorization, and characterization or conformance plan;
- contract-safe units may run concurrently in separate Git worktrees;
- implementation-bound units wait for the required integration checkpoint;
- the main agent integrates completed work in dependency order;
- each phase receives an identifiable integration commit and objective validation evidence;
- the repository reaches a clean, buildable, passing state with an implementation ledger under `docs/implementation-plan/parallel-implementation/`;
- the main agent updates `docs/implementation-plan/delivery-status.md` and tells the operator where to find the implementation outcome;
- the user is then asked whether parallel review is needed;
- when approved, one fresh reviewer inspects each phase commit with complete plan/boundary/contract context;
- the main agent verifies and assigns findings, adds fixes and practical regression tests to the responsible phase commits, safely replays later commits, and restores a clean passing final state.

## Feasibility rules

### Contract-first implementation parallelism

Boundary documents enable parallel work only when every consumed behavior is represented by a frozen, complete public contract and the repository contains declarations, schemas, generated artifacts, or legitimate test doubles needed to build and test against it. A fake of a product-owned normalized port can prove consumer conformance to that port; it cannot prove that the real provider behaves as assumed or that the adapter maps it correctly. A provider-protocol emulator must name its independent evidence, represented version, known differences, and omissions. When work needs unresolved provider semantics or observed runtime behavior, classify the edge as implementation-bound or decision-gated.

### Phase-commit review and amendment

Parallel review is feasible only when phase-to-commit mapping is exact and history reconstruction is safe. Prefer a linear first-parent chain with one dedicated integration commit per phase. Freeze the original passing baseline and create a backup ref before review. Never rewrite published, protected, or shared history in place and never force-push silently; use a dedicated local rewrite branch unless the user separately authorizes remote publication.

A fix belongs in the earliest responsible phase where the corrected implementation can coherently exist. A regression test belongs there when the required test surface already exists; otherwise place it in the earliest later phase that can validly express it and record the split.

## Non-negotiable rules

1. **Require explicit implementation approval.** A completed plan alone is not consent.
2. **Require separate review approval.** Ask only after all approved implementation is integrated, the repository is clean, and required checks pass.
3. **Use validated plans.** Resolve planner-validation errors before implementation.
4. **Inspect before changing.** Read applicable plans, architecture, repository rules, schemas, migrations, delivery configuration, and test conventions.
5. **Protect existing work.** Never discard, stash, commit, relocate, rebase, or rewrite unrelated user changes without authorization.
6. **Enforce requested profiles.** Record requested and actual main, implementor, and reviewer profiles; never hide a substitution.
7. **Freeze contracts before parallel writes.** Prose promises alone are insufficient.
8. **Use dependency waves.** Launch only units whose prerequisites are satisfied by the current checkpoint or frozen contract baseline.
9. **Serialize real shared state.** Lockfiles, migrations, generated output, central registries, and infrastructure state need a single writer or explicit reconciliation owner.
10. **Use one worktree per implementor.** An implementor edits only its assigned worktree and branch.
11. **Keep one authoritative contract owner.** Workers consume contracts but do not change them unilaterally.
12. **Enforce path ownership.** Same-wave write overlap is disallowed.
13. **Do not guess through contract gaps.** Return `CONTRACT_BLOCKER` instead of inventing interfaces or behavior.
14. **Integrate topologically.** Completion time never determines merge order.
15. **Validate every integration.** Review the diff and run phase, contract, affected, and repository checks.
16. **Create one reviewable phase commit.** Every integrated `PH-###-##` maps to one dedicated logical commit in deterministic phase order. Keep orchestration metadata separate.
17. **Use one fresh reviewer per phase commit.** Reviewers do not receive one another's findings.
18. **Give reviewers complete relevant context.** Include typed approved-scope fields and preservation obligations, exact plan and boundary sections, contracts, repository rules, target diff, callers/callees, phase map, later-phase summaries, and frozen final state.
19. **Keep reviewers read-only.** They report findings and never edit, commit, rebase, amend, or merge.
20. **The main agent verifies every finding.** Reproduce or prove it, deduplicate it, assign the root-cause phase, and record the disposition before changing code.
21. **Add regression tests when practical.** Prefer failing-before/passing-after tests without distorting historical phase validity.
22. **Rewrite history safely.** Create a backup ref, use one controlled replay from the earliest affected phase, preserve later behavior, and update old-to-new mapping.
23. **Keep the main agent responsible.** Implementors build bounded units; reviewers inspect bounded commits; the main agent owns contracts, integration, adjudication, fixes, history, and final correctness.
24. **Do not perform irreversible production actions silently.** Deployment, live migration, destructive cleanup, secret rotation, purchases, external communication, and remote force-push require separate authorization.
25. **Report capability limits honestly.** Never call sequential work parallel or claim agents/worktrees/models the host did not provide.
26. **Preserve external-system provenance.** A mock, generated client, legacy wrapper, or self-authored schema is not independent provider evidence. Trace adapter behavior to the planning evidence or keep the phase blocked.
27. **Separate internal fakes from provider emulators.** Internal-port fakes may unblock consumers; provider emulators and real adapters require external evidence and later conformance.
28. **Gate external access.** Public documentation and repository evidence may be read safely; private/live access must be authorized, and read access never implies sandbox, canary, production, quota-consuming, or destructive writes.
29. **Honor the approved change boundary.** Implement only authorized phases and necessary recorded prerequisites. Whole-repository inspection and regression testing identify impact; they do not authorize adjacent redesign, cleanup, or feature work.
30. **Preserve decomposition and data ownership.** Boundary materialization may correct execution classifications, but it must not silently replace the selected decomposition or grant a component undeclared write ownership. Contradictory path or dependency evidence requires plan amendment or explicit serialization consistent with the plan.
31. **Keep the human status derived.** Only the main orchestrator updates `delivery-status.md`; implementors and reviewers treat it as read-only. Summarize and link to canonical execution or review evidence, never copy machine traces or use the summary to override scope, manifests, ledgers, commits, tests, or findings. Tell the operator after implementation and after review updates.

## Required inputs

Locate or receive:

- repository root;
- planning root, `docs/implementation-plan/`;
- derived human status path, `docs/implementation-plan/delivery-status.md`, for operator navigation only;
- delivery scope mode, requested outcome, impact cone, preserved behavior, and explicit non-goals;
- the canonical decomposition assessment, selected candidate, affected-subsystem classifications, and data-writer registry from `93-implementation-units.md`;
- exact user-approved scope;
- planning status and authorized `PH-###-##` IDs;
- unresolved `DEC-###` gates;
- planner-validator command and result;
- for material external systems, the relevant dossier, evidence and unknowns, test-double limitations, conformance plan, and authorized access scope.

When scope is “the whole plan,” include every phase that is authorized now. Otherwise include only authorized phases. A prerequisite may become an execution unit only when it already appears in the plan's `planned_phase_ids` and `authorized_phase_ids`; otherwise stop for approval and a plan amendment rather than adding it implicitly. Keep adjacent or deferred units excluded even when repository inspection discovers them. Do not cross unresolved decision gates automatically; later phases may be scheduled after those gates close.

## Workflow

Follow the implementation phases in order.

### Implementation Phases 0–8 — Prepare, execute, integrate, and reach green

Read `references/execution-workflow.md` completely and follow its detailed Phases 0–8 in order. In summary:

0. preflight Git, repository state, tools, plans, requested profiles, baseline build/tests, and a protected integration worktree;
1. reconstruct the complete dependency DAG for authorized phases and necessary prerequisites, verify it against the selected decomposition and data ownership, and correct unsafe execution classifications without silently redesigning the plan;
2. create boundary documents, the execution manifest, ledger, dependency graph, integration order, and complete worker prompts;
3. materialize and validate the smallest implementation-neutral contract baseline, then freeze its commit;
4. form maximum-safe waves with no decision, implementation, path, migration, generated-output, lockfile, or infrastructure conflict;
5. create one branch/worktree and fresh `gpt-5.6-terra` / `xhigh` implementor per ready unit, supplying the exact plan, boundary, contracts, paths, rules, checks, and result contract;
6. review and integrate units topologically into one dedicated logical commit per `PH-###-##`;
7. apply formal contract change control rather than allowing provider/consumer drift;
8. run scope, affected-area, and whole-repository regression validation, update evidence, and freeze a clean buildable passing review baseline.

Run `scripts/validate_parallel_plan.py` before dispatch, after material changes, and after final implementation integration. Do not offer review until Phase 8 is green.

When Phase 8 completes or implementation stops blocked, update the human delivery status and notify the operator as defined in `references/execution-workflow.md` before yielding control.

When an approved phase touches a material external system, read `references/external-system-fidelity.md` before freezing its boundary or dispatching its worker. Keep this conditional; purely internal phases do not need provider material.

### Implementation Phase 9 — Ask whether parallel review is needed

After Phase 8 succeeds, ask exactly one direct question:

> Implementation and integration are complete for the approved scope, and the project is buildable and passing. Should I run a parallel review of every phase commit?

- Before asking, confirm that `delivery-status.md` records the green implementation outcome and names the review decision as the operator action. In the same message, tell the operator that the summary was updated and give its path.
- If the user declines, record `review_gate.status = declined`, update the **Review** row to `Declined`, validate and commit those records in a separate orchestration metadata commit, verify the branch is clean, tell the operator that the summary was updated, finish the skill, and report the green implementation state.
- If the user approves, record the authorization and continue without asking a second generic confirmation.
- If the implementation is not green, do not ask; fix or report the blocker first.
- Review approval does not authorize remote force-push, production deployment, or other irreversible actions.

### Review Phases 10–14 — Review, adjudicate, reconstruct, and finish

After affirmative review authorization, read `references/review-orchestration-protocol.md`, `references/code-review-skill.md`, `references/history-rewrite-protocol.md`, and `references/agent-model-policy.md`, then follow them exactly. The required sequence is:

10. freeze the passing commit map, create a backup ref and safe rewrite branch, generate review artifacts, and form auditable parallel review batches;
11. launch one distinct fresh `gpt-5.6-sol` / `xhigh` reviewer per phase commit in a target-commit checkout, with full plan, boundary, contract, repository, phase-history, and final-baseline context;
12. have the main agent validate reports, verify mechanisms independently, deduplicate, assign the earliest responsible phase, and design practical regression tests;
13. perform one controlled history reconstruction from the earliest affected phase, amending verified fixes and phase-valid tests while replaying every descendant without losing later behavior;
14. run all regression, contract, phase, migration, generated-artifact, build, test, quality, and package validators, verify a clean final branch, record the old-to-new map and evidence, and finish without another generic confirmation.

Reviewers are read-only. Reviewer reports are immutable evidence. Only the main agent may adjudicate findings, edit code, change contracts, resolve replay conflicts, amend commits, or decide that a reported issue is rejected, duplicate, already fixed, reassigned, or blocked.

At the end of Review Phase 14 or when review stops blocked, update the **Review** row and current delivery status from the authoritative review manifest, ledger, commit map, and validation evidence. Explicitly tell the operator that the human summary was updated, give its path, and state any remaining action.

## Final response to the user

Report:

- implementation scope completed and phase IDs not completed;
- requested and actual main, implementor, and reviewer profiles;
- contract baseline, integration branch, and parallel waves actually executed;
- original and final integration commit for every phase;
- whether parallel review was declined, blocked, or completed;
- reviewer count and findings reported, confirmed, rejected, deduplicated, reassigned, fixed, or blocked;
- regression tests added and validation commands run;
- contract changes, deviations, unresolved blockers, and remaining risks;
- external-system claims exercised, conformance evidence obtained, remaining fidelity gaps, and external actions left gated;
- backup/rewrite refs and retained worktrees;
- production, deployment, remote-history, or launch actions still requiring authorization;
- the path to the updated human delivery status, its current stage/status, and whether operator action is required.

Do not claim success for a phase or review fix whose exit criteria or required validation did not pass.

## Completion criteria

### Review declined

The skill may finish when:

- planning and boundary validators pass;
- all approved phases are integrated in dependency order;
- each phase has one traceable logical commit;
- required checks pass and the repository is clean, buildable, and passing;
- execution documentation and profile records are current;
- the human delivery status records the implementation outcome and declined review, and the operator was told where to find it;
- every external-adapter phase in scope has applicable characterization or conformance evidence; mock-only success is insufficient;
- the user declined parallel review;
- irreversible production and remote-history actions remain separately gated.

### Review approved

In addition to the conditions above:

- every phase commit received one fresh reviewer assignment;
- review batches and timestamps demonstrate actual concurrent execution whenever more than one phase existed, or an explicitly approved fallback is recorded;
- every reviewer received the exact diff and complete relevant plan/boundary/contract context;
- every finding received a main-agent disposition;
- every confirmed actionable issue was fixed or explicitly blocked with evidence;
- practical regression tests were added at valid points in phase history;
- responsible phase commits were amended and descendants replayed safely;
- original-to-current commit mapping is complete;
- the final repository is clean, buildable, and passing;
- implementation and review validators pass;
- the human delivery status records the final review outcome and the operator was told where to find it;
- no remote history was rewritten without separate authorization.

## Common failure modes to avoid

- treating a prose endpoint list as sufficient for parallel client and server work;
- launching a consumer without freezing exact paths, names, signatures, behavior, and test doubles;
- treating an internal-port fake as proof that the provider or real adapter behaves correctly;
- building a provider emulator from the same unsupported assumptions as the adapter;
- passing an external-adapter phase solely because mock-based tests are green;
- absorbing adjacent refactors, legacy cleanup, or unrelated defects into a bounded change because repository-wide analysis exposed them;
- replacing the plan's decomposition with a familiar framework pattern while generating boundaries;
- assigning a unit write access to a persistent resource owned by another component without the recorded migration or serialization mechanism;
- branching every phase from one commit despite implementation-bound dependencies;
- allowing same-wave agents to edit lockfiles, migrations, generated output, or central registries without one owner;
- integrating in completion order instead of dependency order;
- using merge-heavy history that cannot be mapped safely to one phase per commit;
- asking for review before the complete repository passes;
- reviewing orchestration commits instead of manifest-mapped phase commits;
- giving reviewers only a raw diff without plans, boundaries, contracts, callers, and final-state context;
- checking out only the final baseline instead of pinning each reviewer to its target commit;
- reusing one reviewer across commits, disguising a serial loop as bounded parallelism, or exposing reviewers to one another's findings;
- allowing reviewers to edit or accepting findings without main-agent verification;
- adding a regression test to a phase before its required test surface exists;
- repeatedly rebasing descendants once per finding instead of one planned reconstruction;
- amending published history or force-pushing silently;
- losing later phase behavior while replaying descendants;
- updating final commit hashes inside commits whose own hashes are being recorded;
- calling work parallel when one agent actually performed it sequentially;
- letting workers or reviewers edit the human status, treating it as authority, copying raw traces into it, or finishing a top-level stage without telling the operator it was updated.

## Example requests that should activate this skill

- “Implement the validated product plan using parallel agents and worktrees.”
- “Generate boundaries for every component phase, execute safe phases concurrently, and integrate one phase commit at a time.”
- “After implementation passes, review every phase commit in parallel and amend verified fixes into the correct commits.”
