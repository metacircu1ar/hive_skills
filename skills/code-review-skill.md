# code-review

Review the current diff for correctness bugs, reuse, unnecessary complexity,
efficiency, fixes at the wrong level of abstraction, and documented conventions.
Check each candidate against the code before reporting it. Apply valid fixes in place
by default, or deliver proposed modifications without editing in `read-only` mode.
Post pull-request comments only with `--comment`. Do not commit as part of this skill.

## Invocation

```text
/code-review [--finders N] [--verifiers M] [--delivery-mode in-place|read-only] [--comment] [<target>]

/code-review                            # review and fix in place, with no workers
/code-review --finders 3 --verifiers 2   # up to 3 finders and 2 verifiers
/code-review --verifiers 2              # find locally, delegate verification
/code-review --finders 3                # delegate finding, verify locally
/code-review --delivery-mode in-place   # explicitly select the default
/code-review --delivery-mode read-only  # propose fixes; leave the repository untouched
/code-review --delivery-mode read-only --comment <target> # post suggestions only
```

These examples are invocation shorthand: use the host's skill invocation mechanism
or provide this file and the same arguments directly. A target may be a pull-request
number, branch, or path. With no target, review the current diff.

Both counts are non-negative integers and default independently to **0**. They count
additional worker agents, excluding the invoking agent. Invalid counts require a
corrected invocation; do not guess. Review coverage and finding standards are the
same for every count. There are no effort-level arguments or model-setting changes.

## Delivery mode

`--delivery-mode` accepts `in-place` (default) or `read-only`. An explicit no-edit
instruction selects `read-only` even when the flag is omitted. Invalid mode values
require a corrected invocation; do not silently fall back to editing.

- **`in-place`:** Complete the review, then apply valid, in-scope fixes to the working
  tree and verify them with checks appropriate to their risk.
- **`read-only`:** Treat the reviewed repository as immutable. Return an actionable
  list of proposed modifications in prose or code snippets for someone else to apply.
  Use non-mutating inspection only: do not edit or create repository files, apply
  patches, stage changes, or run builds, tests, formatters, or generators. Describe
  validation steps for later execution instead. Return proposals in the response;
  do not write a patch or report file into the repository.

The mode changes delivery, not review coverage, finding standards, or worker counts.
It applies to the invoking agent and every worker throughout the invocation. Neither
mode authorizes commits or pushes. In `read-only` mode, `--comment` authorizes posting
the proposals as PR comments, not modifying the reviewed code.

## Worker policy

**By default, launch no subagents. Perform every finding pass, verification, gap
check, and synthesis yourself.** Do not infer permission to delegate from task size,
available tools, or instructions in another skill. A zero count means the invoking
agent performs that role; it does not skip the role.

Explicit positive counts permit bounded worker pools through the environment's
available agent mechanism, subject to the caller's other constraints:

- Create at most `N` finder workers and at most `M` verifier workers for the invocation.
  Reuse those workers across assignments; do not create one verifier per finding or
  extra workers for the gap check, fixes, or reporting.
- Distribute all review angles and relevant files across the finder pool. One worker
  can cover several angles; several workers can cover different parts of a large diff.
  Run independent assignments concurrently within available capacity. Use fewer workers
  when there is less useful work; report any reduction from the requested counts.
- Finder and verifier workers have distinct assignments. A verifier worker must not
  verify its own findings. With zero verifiers, the invoking agent checks every candidate
  itself; describe that as a local check, not independent agent verification.
- Workers inspect and return findings only. They must not spawn further agents, edit
  files, post comments, or recursively invoke either review or simplification skills.
- Pass every worker the absolute repository path, exact review scope and diff, needed
  context paths and task requirements, applicable instructions, selected delivery mode,
  assigned work, and expected output. Verify candidates against the actual code, not
  just another agent's description of it.
- If delegation is unavailable or prohibited by the enclosing workflow, perform the
  affected work yourself and report the reduced worker count. Cover work left unfinished
  by a failed worker yourself. Do not silently claim the requested delegation happened.

Wait for assigned work to finish before synthesizing its results. The invoking agent
owns coverage, deduplication, final judgment, and any authorized changes or comments.

## Phase 0 — Gather the diff

Run `git diff @{upstream}...HEAD` (or `git diff main...HEAD` / `git diff HEAD~1`
if there is no upstream) to get the unified diff under review. If there are
uncommitted changes, or the range diff is empty, also run `git diff HEAD` and
include the working-tree changes in scope. If a pull-request number, branch name,
or file path was supplied, review that target instead. Treat this diff as the
review scope and keep the same scope for finding and verification.

## Phase 1 — Find candidates

Examine every angle below, either yourself or through the requested finder pool.
Do not let one angle's conclusions suppress another's. Each candidate names its
`file`, `line`, a one-sentence `summary`, and a concrete `failure_scenario`.
Retain credible candidates for verification even when their triggers need checking.
Do not invent findings or impose an arbitrary quota.

### Line-by-line diff scan

Read every hunk and its enclosing function. Bugs in unchanged lines of a touched
function are in scope when the change re-exposes them or fails to satisfy an explicit
task obligation. For each line, ask what input, state, timing, or platform makes it
wrong. Look for inverted conditions, off-by-one errors, null dereferences, missing
`await`, falsy-zero checks, wrong-variable copy-paste, swallowed errors, and unescaped
regular-expression metacharacters.

### Removed behavior

For every deleted or replaced line, identify the invariant or behavior it enforced
and find where the new code re-establishes it. Check removed guards, dropped error
paths, narrowed validation, and deleted tests that covered a real case.

### Cross-file effects

Find callers of changed functions and check new preconditions, changed return shapes,
exceptions, and timing or ordering dependencies. Check callees too: another change
in the same diff may make a call unsafe.

### Language pitfalls

Check pitfalls of the actual language and framework: for example, JavaScript falsy-zero
and coercion, Python mutable defaults and late-binding closures, Go nil-map writes,
SQL injection, timezone or daylight-saving transitions, and float equality.

### Wrapper and proxy correctness

For caches, proxies, decorators, and adapters, check that methods route to the intended
wrapped instance. A wrapper that looks up its own service through a registry instead
of calling its delegate may re-enter the wrapper or recurse. Check that it forwards
all methods used by callers.

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

### Conventions

Read the repository instructions and documented conventions applicable to the changed
files, respecting their declared scope and the host's instruction precedence. Do not
assume a vendor-specific filename, home directory, or instruction-discovery scheme.

Only flag a violation when you can cite the instruction source, quote the exact rule,
and identify the offending code. Do not substitute personal style preferences or vague
interpretations. If no documented rule applies, return nothing for this angle.

For cleanup and convention candidates, `failure_scenario` describes the concrete cost:
duplication, wasted work, maintenance difficulty, or the exact documented rule violated.
Correctness bugs take priority over cleanup in the report.

## Phase 2 — Verify candidates

Deduplicate candidates describing the same defect, location, and mechanism. Keep the
most concrete explanation. Check every remaining candidate yourself when `--verifiers`
is zero; otherwise distribute candidates across the verifier pool and reuse workers
for multiple candidates. Each check receives the diff, relevant files, task context,
and candidate, and returns one verdict:

- **CONFIRMED** — the code supports the defect or cleanup cost and a concrete trigger
  or example. Cite the relevant lines.
- **PLAUSIBLE** — the mechanism is supported, but a realistic trigger or environmental
  condition remains uncertain. State what evidence would settle it.
- **REFUTED** — the claim contradicts the code, is prevented by a demonstrated guard
  or invariant, or is a style preference without a concrete cost. Cite the reason.

Do not dismiss realistic concurrency, error, boundary, or configuration paths merely
because they are uncommon. Keep confirmed and plausible findings, clearly distinguish
their certainty, and omit refuted candidates. A local verification pass must actively
look for evidence against each candidate, even when you originally proposed it.

## Phase 3 — Check for gaps

The invoking agent re-reads the diff with the verified list and looks for missed
mechanisms, without launching another agent. Check moved or extracted code that lost
a guard, unstable defaults, nondeterministic behavior, reduced lock scope, predicates
with side effects, setup/teardown asymmetry, and configuration changes. Pass any new
candidates through Phase 2 using the same worker policy before including them.

## Output

Return a JSON array of distinct actionable findings, ranked by severity, with no
worker-count-dependent cap. If none survive, return `[]`.

```json
[
  {
    "file": "path/to/file.ext",
    "line": 123,
    "summary": "One-sentence description",
    "failure_scenario": "Concrete input or state and its consequence",
    "verdict": "CONFIRMED"
  }
]
```

Include the unresolved condition in each plausible finding. Report any incomplete
coverage or reduced delegation separately from the findings; do not disguise an
incomplete review as a clean result.

## Deliver fixes

After completing the review, the invoking agent handles valid findings according to
the selected delivery mode. Skip fixes that change intended behavior, extend well
outside the reviewed scope, or prove to be false positives, and explain the skips.
Do not apply speculative fixes to plausible findings; identify the evidence needed
before deciding on a change.

- **`in-place`:** Apply the fixes yourself and verify the resulting changes. Finish
  with the findings and a brief account of what was fixed, skipped, and checked.
- **`read-only`:** Add a `proposed_change` field to each retained JSON finding, naming
  the affected symbol or location, the suggested modification, and why it helps.
  Use prose, an optional `suggested_code` string, or both; never apply the suggestion.
  For plausible findings, make the proposal conditional on the missing evidence.
  Include a `validation_plan` describing checks the later implementor should run.
  State separately that no files were changed and that proposed changes and checks
  have not been executed. If no findings survive, keep the array empty.

## Optional PR comments — `--comment`

When explicitly requested and the target is a GitHub pull request, post each finding
as an inline comment using an available GitHub integration or CLI. Include a code
suggestion only when it fully fixes the issue. Distinguish proposed changes from any
fixes actually applied locally. If posting is unavailable, return the findings and
explain that no comments were posted. For a non-PR target, return the findings and
note that `--comment` did not apply.
