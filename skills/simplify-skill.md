# simplify

Improve changed code for reuse, simplicity, efficiency, and the right level of
abstraction without changing intended behavior. Apply valid improvements in place
by default, or deliver proposed modifications without editing in `read-only` mode.
This is a cleanup workflow; use `code-review` for a dedicated correctness review.
Do not commit as part of this skill.

## Invocation

```text
/simplify [--reviewers N] [--delivery-mode in-place|read-only] [<target>]

/simplify                              # review and fix in place, with no workers
/simplify --reviewers 4                # up to 4 workers; invoking agent applies fixes
/simplify --reviewers 2 <target>       # share all four angles across 2 workers
/simplify --delivery-mode in-place     # explicitly select the default
/simplify --delivery-mode read-only    # propose improvements; leave the repository untouched
```

These examples are invocation shorthand: use the host's skill invocation mechanism
or provide this file and the same arguments directly. A target may be a pull-request
number, branch, or path. With no target, review the current diff.

`--reviewers` is a non-negative integer and defaults to **0**. It counts additional
review workers, excluding the invoking agent. Invalid counts require a corrected
invocation; do not guess. The count controls delegation only, not review coverage
or model settings. Every invocation covers all four angles below.

## Delivery mode

`--delivery-mode` accepts `in-place` (default) or `read-only`. An explicit no-edit
instruction selects `read-only` even when the flag is omitted. Invalid mode values
require a corrected invocation; do not silently fall back to editing.

- **`in-place`:** Apply valid, in-scope improvements to the working tree and verify
  them with checks appropriate to their risk.
- **`read-only`:** Treat the reviewed repository as immutable. Return an actionable
  list of proposed modifications in prose or code snippets for someone else to apply.
  Use non-mutating inspection only: do not edit or create repository files, apply
  patches, stage changes, or run builds, tests, formatters, or generators. Describe
  validation steps for later execution instead. Return proposals in the response;
  do not write a patch or report file into the repository.

The mode changes delivery, not review coverage or worker counts. It applies to the
invoking agent and every worker throughout the invocation. Neither mode authorizes
commits or pushes.

## Worker policy

**By default, launch no subagents. Review every angle, check the findings, and deliver
the valid improvements yourself in the selected mode.** Task size, available tools,
and references to other skills do not authorize delegation. Zero workers means local
execution of all the work.

An explicit positive count permits a pool of at most that many review workers through
the environment's available agent mechanism, subject to the caller's other constraints.
Distribute all angles and relevant files across the pool: a worker may cover several
angles, or workers may cover different parts of a large diff. Reuse workers; do not
create extra verifiers, fixers, or nested subagents. Use fewer workers when there is
less useful work and report any reduction from the requested count. Run independent
assignments concurrently within available capacity.

Pass each worker the absolute repository path, exact scope and diff, task requirements,
needed context paths, applicable instructions, selected delivery mode, assigned angles
or files, and expected output. Workers inspect and return findings only. They must not
edit files, post comments, spawn agents, or recursively invoke review or simplification
skills.

If delegation is unavailable or prohibited by the enclosing workflow, do the work
yourself and report the reduced count. Complete any work left unfinished by a failed
worker yourself. The invoking agent owns coverage, checks findings, and delivers the
improvements in the selected mode.

## Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there is no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope. If a pull-request number, branch name,
or file path was supplied, review that target instead. Treat this diff as the
review scope.

Read applicable repository instructions and conventions without assuming a particular
vendor's instruction filenames, home directory, or tool names.

## Phase 1 — Review

Review all four angles yourself when the count is zero; otherwise distribute them
across the requested pool. Each finding identifies its `file`, `line`, a one-sentence
`summary`, and the concrete cost: duplication, wasted work, or maintenance difficulty.

### Reuse

Find changed code that re-implements existing behavior. Search shared modules,
utilities, and nearby code, and name the existing helper to use instead.

### Simplification

Identify unnecessary complexity: redundant or derivable state, copy-paste with small
variations, deep nesting, and dead code. Describe a simpler equivalent.

### Efficiency

Identify redundant computation or I/O, independent operations unnecessarily serialized,
and blocking work added to startup or hot paths. Check whether long-lived closures
retain more state than needed; where the language's capture behavior causes retention,
suggest retaining only the required values. Name the cheaper alternative.

### Level of abstraction

Check whether the change addresses the underlying mechanism. Identify fragile special
cases where a change to the shared mechanism would solve the same problem more clearly.
Explain the concrete maintenance cost and preserve the task's scope.

## Phase 2 — Check and deliver improvements

Finish all local review passes or wait for all assigned worker results, then deduplicate
findings about the same location or mechanism. The invoking agent checks each finding
against the code and delivers valid improvements in the selected mode. Do not launch
additional agents for this phase.

Skip a fix that changes intended behavior, requires changes well outside the reviewed
scope, or proves to be a false positive. Explain the skip.

- **`in-place`:** Apply the improvements yourself and verify the resulting edits with
  checks appropriate to their risk. Report what was fixed, skipped, and checked.
- **`read-only`:** For each proposed improvement, name the file and symbol or line,
  explain the change and its benefit, and provide prose, a code snippet, or both that
  a later implementor can act on. Include any assumptions and validation steps to run
  after applying it. State that no files were changed and that proposed changes and
  checks have not been executed; do not claim the proposal is tested.

If no useful cleanup was found, say so. Disclose any incomplete coverage or reduced
delegation in either mode.
