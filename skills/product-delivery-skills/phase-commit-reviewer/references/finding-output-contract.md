# Reviewer Finding Output Contract

## Result identity

The result must identify:

- phase and component;
- target commit and selected parent;
- frozen final review baseline;
- requested and actual reviewer profile;
- review completion status and timestamp.

## Status values

- `COMPLETED`: review completed without material limitations.
- `COMPLETED_WITH_LIMITATIONS`: review completed, but listed missing tools or optional context reduced coverage.
- `MODEL_BLOCKER`: required model/reasoning profile was unavailable without an approved substitute.
- `SCOPE_BLOCKER`: target identity, unique approved-scope data, external-fidelity classification or required evidence, or required plan/boundary/contract context was missing, malformed, duplicated, or inconsistent. An explicit empty preserved-behavior list is valid.
- `FAILED`: the reviewer could not complete for another stated reason.

Blocked or failed results normally contain no findings unless the orchestrator explicitly permits partial evidence; limitations must explain the state.

## Finding identity

Use IDs in this form:

```text
RVW-PH-001-02-001
```

The embedded phase must match the report phase. IDs are unique within the report.

## Finding fields

Each finding contains:

- `verdict`: `CONFIRMED` or `PLAUSIBLE`;
- `severity`: `critical`, `high`, `medium`, or `low`;
- `category`: one allowed schema category;
- `target_location`: path and line in the target commit;
- `final_location`: corresponding final-baseline location or `null`;
- `summary`: concise defect statement;
- `failure_scenario`: concrete trigger and wrong result/cost;
- `evidence`: exact reasoning grounded in code and context;
- `references`: plan, boundary, contract, architecture, rule, test, or code references;
- `introduced_by_target_commit`: attribution result;
- `present_at_review_baseline`: whether the defect survives at final baseline;
- `later_commit_status`: `not-fixed`, `fixed`, `superseded`, or `unknown`;
- `recommended_owner_phase`: earliest likely root-cause phase;
- `recommended_fix`: direction, not an applied patch;
- `recommended_test`: failing-before/passing-after test proposal;
- `confidence_notes`: remaining uncertainty and what would resolve it.

## Profile fields

The requested profile is:

- model `gpt-5.6-sol`;
- reasoning effort `xhigh`.

The actual profile and selection status must be recorded honestly. Use `unavailable` with `MODEL_BLOCKER` when the requested profile cannot be provisioned. A substitution requires explicit user approval.

## Empty results

An empty `findings` array is correct when every candidate was refuted or no actionable candidate was found. Never add speculative filler.

## Read-only guarantee

The result itself is evidence that the reviewer did not edit the repository. The reviewer must not create or modify tracked files, snapshots, generated output, branches, commits, external comments, or production-connected resources.
