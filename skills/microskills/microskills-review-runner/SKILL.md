---
name: microskills-review-runner
description: >-
  Run a directory of microskills (narrow, project-specific review checklists written by
  microskills-review-generator) as independent micropasses, in parallel across a chosen
  number of agents, then merge their findings into one deduplicated, verified list of
  fixes. Use after /microskills-review-generator, or with any directory of microskill
  files. Fixes in place by default, or proposes them in read-only mode.
---

# Microskills review runner

A **micropass** runs one microskill over the target and checks *every* site on its
list. A general review finds what catches the eye; a micropass checks everything it
was told to check. Micropasses are independent, so with `--finders N` they can run in
parallel, each in its own fresh agent. One merge then removes duplicates and assembles a single list of
fixes.

## Invocation

```text
/microskills-review-runner --skills DIR [--finders N] [--verifiers M] [--only NAME,...]
                           [--delivery-mode in-place|read-only] [--comment] [<target>]
```

| Option | Meaning |
| --- | --- |
| `--skills DIR` | **Required.** The microskills directory: one microskill per `DIR/<name>/SKILL.md`, as written by `/microskills-review-generator`. |
| `--finders N` | At most `N` finder agents run at once, one micropass each, capped at the host's own concurrent-agent limit; see Agents. Each micropass gets its own fresh agent; one agent never runs two microskills. The default is **0**: launch no agents, and the invoking agent runs every pass itself, one at a time. Set `N` explicitly to run passes in parallel. |
| `--verifiers M` | Up to `M` independent verifier agents for the merged findings, run after the passes and capped at the host's concurrent-agent limit. The default is `0`: the invoking agent verifies locally. |
| `--only NAME,...` | Run only these microskills. |
| `--delivery-mode` | `in-place` (default) applies confirmed fixes; `read-only` only proposes them. |
| `--comment` | Post the merged findings to the pull-request target. |

A target may be a pull-request number, a branch, a commit range, or a file or
directory path. With no target, review the current diff. A path selects that code even
if unchanged; use `.` for a repository-wide pass.

Refuse to start, and ask for a corrected invocation, when:

- `--skills` is missing;
- a count is not a non-negative integer;
- an `--only` name is unknown;
- the skills directory holds no valid microskill.

Do not guess. An explicit no-edit instruction selects `read-only` even without the
flag.

### Example activations

```text
/microskills-review-runner --skills .microskills .
/microskills-review-runner --skills .microskills --finders 12 .
/microskills-review-runner --skills /reviews/hive-microskills --finders 8 --verifiers 2 src/
/microskills-review-runner --skills .microskills --only errors-and-logging,async-lost-failures
/microskills-review-runner --skills .microskills --finders 6 --delivery-mode read-only --comment 123
```

## Delivery and agent policy

- **`in-place`:** apply confirmed, in-scope fixes after the merge, and verify them with
  checks appropriate to their risk.
- **`read-only`:** treat the reviewed repository as immutable: no edits, new files,
  patches, staging, builds, tests, formatters or generators. Return fixes as prose or
  code snippets, with checks for someone else to run.

Neither mode authorizes commits or pushes. Posting PR comments requires `--comment`.

**Agents** are whatever the host provides for delegation: Claude Code subagents, Codex
subagents, or another runtime's equivalent. The method needs only an independent fresh
context per pass.

- **Launch no agents by default.** Only an explicit `--finders N` above 0 permits
  finder agents: one fresh agent per selected microskill, at most `N` at once.
  Only `--verifiers M` permits verifier agents. Do not infer permission from the
  number of microskills, the task size or the tools available. Launch no other agents:
  no fixers, no gap-checkers, no agents per file.
- **Find the host's limit first.** Before launching any, determine how many subagents
  this host runs concurrently. Use its tool descriptions, documentation or
  configuration, such as a maximum on parallel subagent or task calls, or Hive's
  `runtime` limits.
- **Set the maximum from it.** Finder concurrency is the smaller of `--finders N`
  and the host's available capacity; verifier concurrency is the smaller of
  `--verifiers M` and the host's available capacity. Report the values used and
  where the capacity limit came from.
- **When the limit is unknown,** use the requested value. If the host refuses or queues
  launches, lower concurrency to what it accepted, without counting that as a failed
  pass.
- **Keep the pool full.** Start a new pass as each one finishes, up to the maximum.
  When a host can only run subagents in its foreground, launch each wave together and
  wait for all of it before the next.
- Finder and verifier agents inspect and return results only. They do not edit, run
  builds or tests, post comments, spawn agents or invoke other skills.
- A verifier must not verify findings from a pass it ran. Local checking is not
  independent verification.
- If delegation is unavailable, prohibited or fails, run the affected passes or
  verification checks yourself, and say so.
- With `--finders 0`, the default, run the passes sequentially. Re-read the code for
  each pass with only that microskill in mind, and never let one pass's findings stand
  in for another's checks. Parallel fresh agents give each pass full independence;
  suggest `--finders N` in the report when many passes ran sequentially.

**On Hive:** use joined `hivectl batch` or `hive_batch` reviewer spawns, one per
microskill. Use one-shot spawns where available. Split the spawns to fit Hive's batch
limits, which are an operation count and a request size. Take the maximum from the
daemon's `runtime` limits, such as `max_active_turns` and `max_providers`, and hold it
across all batches. Collect every batch's join result before merging.

The invoking agent owns loading, scheduling, the merge, final judgment, edits and
comments.

### Complete worker results

Give finders and verifiers these delivery rules along with their output contract:

- Return the complete JSON through the host's result channel. Do not cap findings or
  replace them with a summary to fit an inline response.
- Before parsing or merging, the caller retrieves the worker's final output in full.
  Follow host-provided artifact links, full-output references and pagination to the
  end; an inline preview or valid JSON alone does not establish completeness.
- If the host cannot retain or retrieve the full result, request smaller complete
  batches from the same worker, with an explicit final batch and total result count.
  Account for every batch before merging. Do not rerun the same oversized response
  as though truncation were malformed JSON. If complete delivery remains unavailable,
  use the local fallback and report any coverage still incomplete.
- Use host-managed output storage; these rules do not authorize writing report files
  into the reviewed repository.

On Hive, a join member shares a 64 KiB inline budget between output and its completion
summary. Follow any `read_target` for the result with `hive_read` or
`hivectl read artifact:ID --after 0 --limit 65536`, then continue from `next_offset`
until the artifact is fully read. Inspect each member's outcome and `output_partial`;
a completed join can contain unsuccessful members. Provisional output and completion
summaries are not substitutes for a successful worker's full review JSON.

## 1. Load the microskills and resolve the scope

- **Read the microskills.** Read `DIR/INDEX.md` if present, then every
  `DIR/<name>/SKILL.md`.
  - A valid microskill has YAML frontmatter that parses, a `name` matching its
    directory, a `description`, and a numbered **Look for** list.
  - Report malformed files and skip them. Never repair them.
- **Check freshness.** Note the repository commit recorded in `INDEX.md`. When the code
  has moved far from it, such as renamed modules or a removed stack, say that the
  microskills may be stale. Still run them.
- **Resolve the target.** Use non-mutating inspection. For the default diff, compare
  against the upstream or agreed base, including staged, unstaged and relevant
  untracked files.
  - State an unavailable base or an empty scope; never claim a pass over code that was
    not reviewed.
  - Intersect the target with each microskill's own **Scope**. A pass with nothing in
    scope reports zero sites; it is not skipped silently.
- **What counts.** For a diff, report defects introduced or re-exposed by the change.
  For a path audit, existing defects in that path are in scope.

## 2. Run the micropasses

Give each micropass agent:

- the absolute repository path and the exact scope;
- the absolute path of its one microskill file, to read first. Include the full text
  only when the agent cannot read that directory;
- the applicable repository instructions and the delivery mode;
- this contract.

Each micropass:

1. **Inventories every candidate site** in scope that the microskill's recognizers
   match. Text search is only navigation: also follow wrappers, aliases, callers and
   detached work that a grep misses.
2. **Checks every site against every Look-for item.** The point is completeness, not
   sampling. Read enough context, such as callers, error boundaries and config, to
   decide.
3. **Reports only its own family.** It respects the microskill's **Not a finding**
   list, and puts out-of-family observations in one short `notes` field.
4. **Looks for counterevidence** before reporting: an outer handler, an existing log, a
   documented suppression, or a test proving the behavior.
5. **Returns JSON:**

```json
{
  "microskill": "errors-and-logging",
  "coverage": {"sites": 214, "checked": 214, "skipped": [{"where": "vendor/", "why": "out of scope"}]},
  "findings": [
    {"file": "src/jobs/runner.rs", "line": 88, "check": 1,
     "summary": "Send failure is discarded with `let _ =`",
     "failure_scenario": "A closed channel drops the job result silently; the caller reports success.",
     "verdict": "CONFIRMED",
     "proposed_change": "Propagate the error to the job boundary, which logs it once.",
     "validation_plan": "Test that a closed receiver fails the job and logs one error.",
     "suggested_code": "optional"}
  ],
  "notes": "optional"
}
```

`check` is the number of the Look-for item the finding violates.

**Verdicts:**

- **CONFIRMED:** the defect is supported by the code itself.
- **PLAUSIBLE:** the mechanism is real but depends on an unresolved runtime or
  configuration condition; name the missing evidence.
- **REFUTED:** dropped before returning.

Wait for every pass and retrieve its complete result before merging. If a pass fails
or its fully retrieved output is malformed, rerun it once in the same execution mode:

- **With delegation in use:** rerun it in a fresh agent, within the `--finders` limit.
- **With `--finders 0`, or when delegation is prohibited or unavailable:** rerun it
  yourself, and launch no agent.

If it fails again, report that pass as not run.

## 3. Merge, verify, deliver

1. **Merge duplicates.** Merge findings with the same root cause at the same location,
   even when found by different microskills. Keep one finding with `found_by: [names]`
   and the strongest scenario. Keep two independent defects at one site separate.
2. **Reconcile fixes.** When passes propose different changes to the same code, choose
   one coherent fix that satisfies all of them, or explain the conflict. Order fixes so
   that dependent changes come after their prerequisites.
3. **Verify.** Re-check every merged finding using the [verifier contract](#verifier-contract)
   below, with the verifier pool if requested. Drop REFUTED findings and downgrade
   unresolved CONFIRMED findings to PLAUSIBLE when the mechanism remains supported.
   Report checks that could not be completed; never apply their proposed fixes.
4. **Return one list** of fixes ranked by severity, as a JSON array of the step 2
   finding objects with `microskill` replaced by `found_by`.
   - Add a coverage table per microskill: sites, checked, findings, skips, and passes
     not run.
   - Name the passes that found nothing.
   - If no findings survive, return `[]` with the coverage table.
5. **In-place mode.**
   - Apply only confirmed, bounded fixes, preserving intended behavior and existing
     user changes.
   - Run targeted checks for the failure paths you changed.
   - Report what changed and which checks actually ran; never present a proposed test
     as executed.
   - List deferred fixes that need wider authority.
6. **Read-only mode.** Return the list as proposals, and state that no repository files
   changed and nothing was executed.
7. **Comments.** With `--comment` and a GitHub PR target, post the merged findings
   through an available integration. Otherwise explain why nothing was posted.

### Verifier contract

After merging, assign each finding a stable `finding_id` for this invocation, such as
`F1`. Split the IDs into disjoint assignments, grouping related files or mechanisms
where useful. Assign every finding to one verifier; reuse up to `M` verifiers across
batches within available capacity. Launch none when there are no findings. With
`--verifiers 0`, perform the same checks locally.

Give each verifier the absolute repository path, exact review scope and diff/base,
its assigned IDs and complete finding objects, the originating microskill paths (or
text if inaccessible), relevant context paths and task requirements, repository
instructions, delivery mode, and the static-only and complete-result rules above.

Read the actual code and relevant callers, trace the claimed failure scenario, and
look for counterevidence. Check that the proposed correction addresses the cause
without breaking required behavior. Return one JSON entry per assigned ID, including
REFUTED and UNVERIFIED entries so the caller can account for every check:

```json
[
  {
    "finding_id": "F1",
    "verdict": "CONFIRMED",
    "reason": "A closed receiver discards the result while the caller reports success.",
    "evidence": ["src/jobs/runner.rs:88 discards the send error; line 92 returns success."],
    "missing_evidence": null
  }
]
```

Use CONFIRMED, PLAUSIBLE or REFUTED for completed checks. Use UNVERIFIED when a check
cannot be completed, such as when the code is inaccessible. Cite source locations
supporting the decision; an UNVERIFIED entry may have an empty `evidence` list.
For PLAUSIBLE or UNVERIFIED, make `missing_evidence` a nonempty description of what
is needed. Explain needed corrections to the proposed fix in `reason`.

Retrieve complete verifier results and check them against the assigned IDs. Missing,
duplicate, unknown or malformed entries do not count as completed verification.
The caller resolves those entries, UNVERIFIED results and any failed assignments by
checking the affected findings locally, disclosing the fallback. If a check still
cannot be completed, mark that finding unverified in the report and exclude it from
automatic fixes. Finish verification before changing code.

Static inspection does not prove runtime behavior, so say which paths were
unverifiable. Never cap findings by agent count, never edit the microskill files, and
do not write a separate report file unless asked.
