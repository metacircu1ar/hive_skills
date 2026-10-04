---
name: test-quality-review
description: Review tests and their supporting code for meaningful assertions, missing risk coverage, realistic test doubles, determinism, isolation, maintainability, and effective execution in CI. Use for a focused test-quality pass on a diff, pull request, or code path in any language or framework, with in-place improvements or read-only proposals. Not a general production-code review or a test-deletion campaign.
---

# Test quality review

Evaluate how well tests distinguish correct behavior from realistic defects, and
whether their results are reliable and actionable. Strengthen, add, simplify, or
remove tests only when evidence supports the change. Test count, coverage percentage,
and lines deleted are not quality targets.

## Invocation

```text
/test-quality-review [--finders N] [--verifiers M] [--delivery-mode in-place|read-only] [--comment] [<target>]
```

Use the host's skill invocation mechanism or provide this file and the same arguments
directly. With no target, review the current diff and tests for the changed behavior,
even if no test file changed. A target may be a pull-request number, branch, commit
range, or file/directory path. A path selects that code and its relevant tests even
if unchanged; use `.` for a repository-wide pass.

`--finders` and `--verifiers` are non-negative integer worker counts, each defaulting
to **0**, excluding the invoking agent. `--delivery-mode` defaults to **`in-place`**.
Invalid counts or modes require a corrected invocation before proceeding; do not
guess or silently fall back to editing. Counts change delegation, not coverage or
model settings. An explicit no-edit instruction selects `read-only` even without
the flag.

### Example activations

```text
/test-quality-review
/test-quality-review --finders 3 --verifiers 2
/test-quality-review --delivery-mode read-only tests/
/test-quality-review --delivery-mode read-only src/storage/
/test-quality-review --delivery-mode read-only .
/test-quality-review --delivery-mode read-only --comment 123
```

## Delivery and worker policy

- **`in-place`:** Complete the review, then apply confirmed, in-scope improvements
  yourself. Validate changes using the repository's existing test tools and policies.
- **`read-only`:** Treat the reviewed repository as immutable. Inspect code and existing
  evidence without editing or creating files, applying patches, staging, or running
  tests, builds, mutation tools, formatters, or generators. Return proposals as prose
  or code snippets with validation steps for someone else to execute. Do not write
  a report or patch file into the repository.

Neither mode authorizes commits or pushes. Posting PR comments requires `--comment`;
in read-only mode it permits publishing proposals, not changing code.

**Launch no subagents by default.** With zero workers, perform all finding,
verification, and coverage checks yourself. Do not infer delegation permission from
task size or available tools. Positive counts permit at most `N` finder workers and
`M` verifier workers, subject to the enclosing workflow's restrictions:

- Reuse the requested pools across files and findings. Do not launch extra fixers,
  gap-check agents, or agents per test. Cover all relevant angles at every worker count.
- Workers perform static inspection and return findings only. They must not edit,
  run tests or builds, post comments, spawn agents, or recursively invoke review skills.
  A verifier worker must not verify its own findings. Local checking is not independent
  agent verification.
- Pass each worker the absolute repository path, exact scope, task requirements,
  relevant context paths, applicable instructions, delivery mode, assigned work, and
  expected output. Group assignments by behavior and fixtures, not just file count.
- Use fewer workers when useful work or capacity is limited, and disclose the reduction.
  If delegation is unavailable, prohibited, or fails, finish the affected work yourself.

Wait for assigned results before synthesis. The invoking agent owns final coverage,
deduplication, judgment, any permitted execution, edits, and comments.

## 1. Map the test surface

Resolve the diff or paths using non-mutating inspection. For the default diff, include
branch changes against the upstream or agreed base, staged and unstaged changes, and
relevant untracked files. State an unavailable base or empty scope rather than silently
choosing another range or claiming a repository-wide review.

Read applicable instructions, test configuration, fixtures/helpers, relevant production
behavior, and CI test selection. Determine the actual assertion semantics, setup and
teardown rules, async handling, skip behavior, and test tiers used by this codebase.
Do not impose another framework's conventions or assume filenames prove discovery.

For a diff, report quality problems introduced or re-exposed by the change, and missing
tests for its relevant risks or explicit task requirements. Read related unchanged
tests to avoid inventing gaps. For a path audit, existing problems in that test surface
are in scope. Keep unrelated production defects separate from test-quality findings.

## 2. Assess the evidence each test provides

For each relevant test or cohesive case group, identify the exercised behavior, input
conditions, actual execution path, and pass/fail observation. Relate the expected
outcome to a requirement or invariant rather than assuming current code is correct.
Use a concrete counterexample: what wrong result, lost effect, or forbidden effect
could still pass this test? A finding must explain that risk, not just name a pattern.

### Assertions and expected results

- Check that assertions execute and their failures reach the runner. Look for unawaited
  work, callbacks that never run, swallowed assertion failures, early exits, and loops
  that examine zero items while the test still passes.
- Match assertion strength to the requirement: presence, truthiness, or status alone
  may omit relevant contents, counts, ordering, persistent effects, or forbidden effects.
  A failure-path test should establish which operation failed and what state remained.
- Check numeric tolerances, unordered comparisons, text normalization, and ignored
  fields: they must not erase a distinction the contract requires.
- Use an expectation derived independently from the operation being checked. For
  generated tests, validate the property itself: a round trip can establish consistency
  without proving interoperability or correctness against an external specification.
- Assess snapshots and golden artifacts for meaningful selection, readable differences,
  and an accountable update process. Do not regenerate expectations simply to make a
  failing test green.

An explicit assertion call is not mandatory when the harness already enforces a
meaningful outcome, such as compilation failure, process exit, or a property violation.
Verify that enforcement exists rather than treating assertion syntax as quality.

### Scenario and risk coverage

- Connect changed behavior to important success, error, boundary, and recovery cases.
  Consider empty/absent values, limits, invalid input, partial failure, cancellation,
  timeouts, retries, idempotency, cleanup, and access boundaries where relevant.
- Check interactions and transitions, not only isolated examples: repeated operations,
  reordered events, restart after partial work, and concurrently accessed state can
  expose different risks. Do not demand concurrency tests for code with no such risk.
- For parameterized or generated cases, check that inputs vary the behavior under test.
  Review generators, filtering, preconditions, and shrinking for vacuous properties,
  erased edge cases, or counterexamples that cannot be reproduced.
- Use coverage and mutation results as supporting evidence, with their limitations.
  Executed lines do not imply checked outcomes; an equivalent mutant is not a defect.
  Propose a missing case only with a plausible failure and an observable assertion.

### Test doubles and environment fidelity

- Locate the real code that still executes under each mock, stub, fake, or simulator.
  Distinguish a test of a consumer against an internal interface from evidence that an
  adapter works with an external provider. One does not establish the other.
- Check whether doubles represent relevant error shapes, ordering, cancellation,
  serialization, transaction, and lifecycle behavior. For provider-facing claims,
  inspect available provider specifications, versions, recordings, or conformance tests;
  record evidence gaps instead of treating a mock as proof of compatibility.
- Look for fixtures that share mutable state with expected values, bypass the operation
  being checked, or inspect a different resource from the one the code uses. Setup must
  create the intended preconditions, not substitute for the behavior being tested.
- Evaluate test tier against the risk. A focused unit test and a broader integration
  test may provide complementary evidence; neither should automatically replace the
  other. Do not call live services or use credentials merely to validate a double.

### Reliability and isolation

- Check dependencies on wall-clock time, fixed sleeps, random seeds, test order, locale,
  timezone, filesystem layout, and scheduling. Prefer controllable inputs or observable
  synchronization appropriate to the behavior; simulated time alone cannot establish
  real scheduler or concurrency behavior.
- Check restoration of globals, environment variables, monkey patches, clocks, and
  singleton state. Verify cleanup of files, databases, sockets, threads, and async work
  even after an assertion fails; inspect parallel collisions and resource ownership.
- Investigate retries or enlarged timeouts masking a race. A repeated green result
  does not establish determinism. Retain seeds, ordering, and environment details needed
  to reproduce failures, without recording secrets.

### Execution and maintenance

- Verify discovery, filters, focused-test markers, skips, expected failures, platform
  gates, and CI job conditions. Check that the selected tests actually execute and a
  failed test fails the intended gate; a successful command with zero tests is not proof.
- Ensure failure messages and case names reveal the relevant inputs and broken
  expectation. Shared helpers should not hide assertions or make diagnosis depend on
  unrelated setup. Parameterization is useful only while cases remain understandable.
- Identify avoidable setup expense, unnecessary live dependencies, redundant fixtures,
  and overly broad end-to-end setup for local checks. Support performance claims with
  available timings or a concrete cost mechanism, not an invented benchmark.
- Check whether coupling to internal layout creates churn without protecting required
  behavior. Structural, protocol, security, and compatibility checks may intentionally
  constrain implementation. Dependency injection and test hooks are not inherently
  defects; identify the actual complexity or production exposure they introduce.

## 3. Verify findings and choose a safe improvement

Deduplicate candidates and actively seek counterevidence in other tests, harness
behavior, requirements, and available history. Check locally or with the requested
verifier pool, then classify each candidate:

- **CONFIRMED:** Evidence supports a missed defect, unreliable result, missing required
  case, or concrete maintenance cost.
- **PLAUSIBLE:** The mechanism is supported, but a requirement, runtime condition, or
  CI configuration remains uncertain; name the missing evidence.
- **REFUTED:** Existing checks address the risk or the criticism is only stylistic.

Omit refuted candidates. Recheck scope for missed behaviors and verify any new findings
before delivery. Do not cap findings according to worker count.

Prefer a targeted improvement that preserves distinct risks already covered. Before
deleting or merging a test, identify what coverage remains, whether it runs on the same
relevant platforms/gates, and why no unique failure case is lost. If that evidence is
missing, retain the test and propose investigation. Never remove a test simply because
it is slow, inconvenient, or currently failing; do not weaken a valid expectation to
hide a product defect.

Changes to production behavior are outside this pass unless separately authorized.
Removing a test-support seam also requires checking production callers and the supported
API, not just textual references. Keep uncertain removals or broad redesigns as proposals.

## 4. Deliver and validate

In **`in-place`** mode, complete the review and establish a baseline with documented
repository commands where practical before editing. Apply confirmed, bounded test/fixture
improvements, preserving unrelated user changes, then run affected tests and relevant
surrounding suites. Do not change files while those tests are running. Use isolated
test resources; do not touch live accounts, production data, or shared infrastructure
without authorization.

For a regression test, seek evidence that it rejects the known-bad behavior for the
intended reason and accepts the corrected behavior. A safe isolated historical case
or a targeted fault injection can supply that evidence when execution is permitted;
do not rewrite the user's working tree to recreate it. If unavailable, state that the
test's regression sensitivity has not been demonstrated. Distinguish baseline failures,
new failures, infrastructure problems, skipped cases, and tests never executed.

In **`read-only`** mode, propose concrete edits or snippets and validation commands;
do not execute them. State that no files changed and the proposals were not run.

Return distinct confirmed and plausible findings ranked by severity as a JSON array.
Each finding has `file`, `line`, `summary`, `failure_scenario`, `verdict`,
`proposed_change`, and `validation_plan`; add `test_name` when applicable and optionally
`suggested_code`. For a missing test, cite the affected behavior's location. Describe
the missed defect, false failure, or maintenance cost precisely; make uncertain
proposals conditional. If no findings survive, return `[]`.

Separately summarize the reviewed scope, edits or proposals, checks actually run,
coverage limitations, and any reduced delegation. Do not imply a full suite passed
from a focused run or static inspection. No additional report artifact is required.

With **`--comment`** and a GitHub PR target, post findings through an available
integration or CLI. Distinguish proposals from local fixes and use code suggestions
only for complete fixes. If `--comment` was requested but the target is not a PR or
posting is unavailable, explain why no comments were posted.

## Inspiration

[OpenClaw's test-audit](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md)
informed the emphasis on regression-detection value and evidence before deleting tests.
This pass is self-contained: it does not inherit that project's test runners, repository
layout, automatic delegation, or follow-up workflows. The link is attribution, not a
runtime dependency.
