---
name: error-logging-review
description: Review code for unchecked or swallowed errors, missing or ineffective failure logs, and useful non-error events that lack operational visibility. Use for a focused error-handling and logging pass on a diff, pull request, or code path, with in-place fixes or read-only proposals. Not a general correctness or production-readiness audit.
---

# Error and logging review

Investigate whether every material failure in scope is checked, handled or propagated,
and recorded at an appropriate boundary, and whether useful non-error events are
observable. Apply valid fixes in place by default, or return proposals in `read-only`
mode. The goal is diagnosable behavior, not a log statement at every call site.

## Invocation

```text
/error-logging-review [--finders N] [--verifiers M] [--delivery-mode in-place|read-only] [--comment] [<target>]
```

Use the host's skill invocation mechanism or provide this file and the same arguments
directly. With no target, review the current diff. A target may be a pull-request
number, branch, commit range, or file/directory path. A path selects that code for
review even if unchanged; use `.` for a repository-wide pass.

`--finders` and `--verifiers` are non-negative integer worker counts, each defaulting
to **0**, excluding the invoking agent. `--delivery-mode` defaults to **`in-place`**.
Invalid counts or modes require a corrected invocation before proceeding; do not
guess or silently fall back to editing. Counts change delegation, not coverage or
model settings. An explicit no-edit instruction selects `read-only` even without
the flag.

### Example activations

```text
/error-logging-review
/error-logging-review --finders 3 --verifiers 2
/error-logging-review --delivery-mode read-only src/jobs/
/error-logging-review --delivery-mode read-only .
/error-logging-review --delivery-mode read-only --comment 123
```

## Delivery and worker policy

- **`in-place`:** Complete the review, then apply confirmed, in-scope fixes yourself
  and verify the resulting changes with checks appropriate to their risk.
- **`read-only`:** Treat the reviewed repository as immutable. Inspect code and
  available evidence without editing or creating files, applying patches, staging,
  or running builds, tests, formatters, or generators. Return proposed changes as
  prose or code snippets and describe checks for someone else to run. Do not write
  a report or patch file into the repository.

Neither mode authorizes commits or pushes. Posting PR comments requires `--comment`;
in read-only mode it permits publishing proposals, not changing code.

**Launch no subagents by default.** With zero workers, perform all finding,
verification, and coverage checks yourself. Do not infer delegation permission from
task size or available tools. Positive counts permit at most `N` finder workers and
`M` verifier workers, subject to the enclosing workflow's restrictions:

- Reuse the requested pools across files and findings; do not launch extra gap-check,
  fixer, or reporting agents. Cover all review angles regardless of worker count.
- Workers inspect and return findings only. They must not edit files, post comments,
  spawn agents, or recursively invoke review skills. A verifier worker must not verify
  its own findings. Local verification is not independent agent verification.
- Pass each worker the absolute repository path, exact scope, task requirements,
  relevant context paths, applicable instructions, delivery mode, assigned work, and
  expected output. The read-only restrictions apply to every worker too.
- Use fewer workers when useful work or capacity is limited, and disclose the reduction.
  If delegation is unavailable, prohibited, or fails, finish the affected work yourself.

Wait for assigned results before synthesis. The invoking agent owns final coverage,
deduplication, judgment, delivery, and any authorized comments.

## 1. Establish scope and logging conventions

Resolve the requested diff or paths using non-mutating inspection. For the default
diff, inspect branch changes against the upstream or agreed base together with staged,
unstaged, and relevant untracked source files. If the base cannot be established,
state that limitation; do not silently review an unrelated range. If the scope is
empty, say so rather than claiming the repository passed review.

Read enclosing functions, relevant callers and callees, async entry points, error
middleware, logger wrappers, and applicable repository instructions. Inspect available
logging configuration: enabled levels, handlers/sinks, filters, sampling, redaction,
and shutdown/flush behavior. Reuse the project's logging and error-handling conventions;
do not assume a particular language, provider, framework, or logging package.

For a diff, follow dependencies to establish the handling path, but report only defects
introduced or re-exposed by the change, or failures to meet explicit task obligations.
For a path audit, existing defects within that path are in scope. Identify missing
runtime or deployment evidence instead of assuming a logger call reaches production.

## 2. Trace errors from origin to outcome

Inventory fallible operations in scope and follow each failure to its handling and
recording boundary. Text searches are navigation aids, not proof of coverage.

- Check exceptions, error/result values, status codes, sentinel returns, subprocess
  exits, partial reads/writes, and per-item failures inside nominally successful batch
  responses. A success-shaped wrapper does not prove the operation succeeded.
- Check that futures, promises, tasks, streams, callbacks, and background jobs have
  their failures observed. Follow detached work beyond the request that launched it.
- Find empty or overly broad catches, ignored results, failed operations converted
  into success, fallback values hiding failure, and logs followed by unsafe continuation.
  Logging an error is not handling it: verify recovery, propagation, or termination.
- Follow retries, exhaustion, timeouts, cancellation, rollback, and cleanup. Preserve
  the original cause; a cleanup failure must not silently replace the primary failure.
  Distinguish expected cancellation or absence from actual operational failure.
- Identify who owns the failure record. Propagating an error to a boundary that logs
  it with sufficient context is valid; do not require logging and rethrowing at every
  layer. Conversely, do not assume an unseen caller or framework logs it.

Every material failure needs a usable record or an explicit, evidence-backed reason
why logging is intentionally omitted or replaced by an adequate existing signal.
Expected validation failures need not be error-level incidents. Keep required audit
records distinct from routine diagnostics; do not suppress them as noise.

## 3. Check useful non-error events

For each important operation, ask what an operator needs to reconstruct what happened,
where progress stopped, and why a behavior or state changed. Examine relevant events:

- Process/service/job start, readiness, completion, shutdown, and long-running progress.
- Meaningful domain transitions, durable commits, administrative/configuration changes,
  and security/audit actions required by the product.
- Retry scheduling, degraded operation, fallback selection, dependency recovery,
  circuit transitions, and skipped/deduplicated work when operationally significant.
- Safe correlation across requests, jobs, queues, and external calls, with outcomes,
  durations, or counts where they answer a concrete operational question.

For a missing event, name that question and show why existing logs, traces, metrics,
or audit records do not answer it. A metric may cover a rate but not explain one failed
job. Do not add routine function-entry, per-item, health-poll, or payload logs without
a demonstrated need. Choose levels and sampling according to local policy and volume;
do not sample away required audit events or the only evidence of a material failure.

Check event timing and meaning: attempted, queued, completed, and durably committed
are different states. Do not report success before the relevant operation succeeds.

## 4. Check log quality, safety, and effectiveness

- Prefer the existing structured logger and stable event names. Include safe operation,
  outcome, correlation, error class/cause, and retry context where useful. Preserve
  diagnostic detail without blindly serializing exceptions or entire objects.
- Verify effective levels, propagation, filters, and sink wiring where evidence is
  available. Check whether async shutdown or crash paths can lose the only failure
  record. Distinguish code-level evidence from unverified deployment behavior.
- Detect secrets, tokens, credentials, personal data, raw request/response bodies,
  or uncontrolled exception text reaching logs. Use allowlisted/redacted fields and
  safe identifiers; do not reproduce sensitive values in the review output. Check
  escaping or structured encoding of untrusted text to prevent forged log entries.
- Detect duplicate records, retry floods, excessive volume, expensive serialization,
  blocking sinks, and high-cardinality labels where logs generate metrics. Avoid
  diagnostics whose evaluation has side effects or changes application behavior.
- Check logger-failure handling and recursive error reporting. Preserve the documented
  failure policy: diagnostic logging should not unexpectedly break the application,
  while explicitly required durable audit logging may have stricter guarantees.

Do not introduce a telemetry platform, change deployment policy, or redesign recovery
semantics merely to add logging. Flag decisions needing wider authority separately.

## 5. Verify, deliver, and report

Deduplicate findings and check each against actual code and configuration, actively
looking for counterevidence such as an outer handler, existing event, redaction, or
documented suppression. Use the verifier pool if requested; otherwise check locally.
Classify each candidate:

- **CONFIRMED:** A concrete failure or operational blind spot is supported by evidence.
- **PLAUSIBLE:** The mechanism is supported, but a runtime/configuration condition is
  unresolved; name the missing evidence.
- **REFUTED:** Existing handling/visibility is sufficient, or no concrete need is shown.

Omit refuted candidates. Revisit the scoped operations and event paths for coverage
gaps, verifying any additional findings before reporting. Do not cap findings based
on worker count or claim that static inspection proves every runtime event is captured.

Return distinct confirmed and plausible findings ranked by severity as a JSON array.
Each finding has `file`, `line`, `summary`, `failure_scenario`, `verdict`,
`proposed_change`, and `validation_plan`; optionally include `suggested_code`.
For a missing log, explain the lost diagnostic or operational information. For a
plausible finding, make the proposal conditional on the missing evidence. If no
findings survive, return `[]` with a separate coverage/limitations note.

In **`in-place`** mode, apply only confirmed, bounded fixes after review. Preserve
intended behavior and existing user changes; explain deferred fixes or policy choices.
Use targeted tests where practical to exercise failure handling, event level/context,
redaction, non-duplication, and success timing. Report what changed and which checks
actually ran; never represent a proposed test as executed.

In **`read-only`** mode, return actionable proposals for a later implementor without
applying them. State that no files changed and that proposed changes and validation
steps were not executed.

In either mode, briefly identify the reviewed scope, traced boundaries, excluded or
unverified paths, and any reduced delegation. Do not generate a separate ledger or
report artifact unless requested.

With **`--comment`** and a GitHub PR target, post findings through an available
integration or CLI. Distinguish proposals from local fixes; include a code suggestion
only when it fully fixes the issue. If the target is not a PR or posting is unavailable,
return findings and explain why no comments were posted.
