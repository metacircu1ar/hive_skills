---
name: perf-optimization
description: Find and remove performance bottlenecks with evidence. Locate the bottleneck with release-build CPU/wall accounting, bounded instrumentation and profiling; predict each change's effect; then confirm it with frozen-binary paired experiments under predeclared gates, without weakening correctness or durability. Use for throughput, latency, stall, or resource problems in a workload, benchmark, service, or code path, with in-place implementation or read-only analysis. Not a micro-benchmark tuning pass or a style review.
---

# Performance optimization

Improve a real workload's performance by first finding what limits it, then changing
one mechanism at a time and proving each effect with controlled measurements. The
target is the user's stated metric under the workload's correctness rules, not lower
CPU numbers, more caches, or prettier flame graphs. Never buy speed by weakening
correctness, durability, ownership, security, or the workload's semantics.

## Invocation

```text
/perf-optimization [--finders N] [--verifiers M] [--delivery-mode in-place|read-only] [<target>]
```

Use the host's skill invocation mechanism or provide this file and the same arguments
directly. A target may be a benchmark or workload command, a scenario name, a code path,
or a symptom ("control latency spikes", "throughput falls at 100k"). With no target,
use the repository's primary documented benchmark or workload. If none exists, stop
and ask the user to name the workload and metric. Do not invent one.

`--finders` and `--verifiers` are non-negative integer worker counts, each defaulting
to **0**, excluding the invoking agent. `--delivery-mode` defaults to **`in-place`**.
Invalid counts or modes require a corrected invocation; do not guess or silently fall
back to editing. Counts change delegation, not rigor or model settings. An explicit
no-edit or no-run instruction selects `read-only` even without the flag.

### Example activations

```text
/perf-optimization
/perf-optimization "scripts/bench.py --agents 10000"
/perf-optimization --finders 2 --verifiers 1 src/runtime/hub.rs
/perf-optimization --delivery-mode read-only "p99 control latency regression"
```

## Delivery and worker policy

- **`in-place`:** Build release artifacts, add opt-in instrumentation, run measurements,
  implement one increment at a time, validate, and screen it as described below.
- **`read-only`:** Treat the repository and its evidence as immutable. Inspect code,
  configuration, and existing measurement data without editing files, building, or
  running tests, benchmarks, profilers, or tracers. Return a bottleneck analysis,
  ranked hypotheses with predicted effects, and a concrete measurement and experiment
  plan for someone else to execute.

Neither mode authorizes commits, pushes, deployments, configuration changes on shared
systems, or expensive confirmation runs beyond what the user requested. The largest
or longest confirmations (for example production-scale or multi-hour runs) run only
when the user explicitly asks; do not schedule them as an automatic final step.

**Launch no subagents by default.** Do not infer delegation permission from task size.
Positive counts permit at most `N` finder workers and `M` verifier workers:

- **Finders** analyse code paths, configuration, and *existing* evidence to propose
  bottleneck hypotheses with mechanisms and predicted effect sizes.
- **Verifiers** adversarially check measurements, statistics, and claims: confounds,
  sample sizes, misaligned timestamps, overclaimed causation, and correctness risk.
  A verifier must not verify its own hypotheses.
- **Workers never perturb measurements.** They perform static inspection and
  lightweight analysis of retained data only. They must not build, run benchmarks,
  tests, or profilers, attach tracers, edit files, or spawn agents. Never run worker
  analysis that competes for CPU or I/O while a timed measurement is in progress.
- Pass each worker the absolute repository path, the target and metric, the relevant
  evidence paths, the applicable constraints (including forbidden paths such as
  credentials or protocol files), assigned work, and expected output. Use fewer
  workers when useful work is limited and disclose the reduction. If delegation is
  unavailable or fails, do the work yourself.

The invoking agent owns all execution, final judgment, edits, and claims.

## 1. Frame the problem

Write down, before measuring:

- **Metric and success definition:** throughput, latency quantiles, stall freedom,
  CPU or memory per unit of work, or time to completion. Name the workload size and
  shape (closed-loop burst, steady arrival, mixed reads and writes).
- **Correctness oracle:** an independent audit that every timed run must pass, such as
  exact counts, ordering, cleanup, ownership, and resource caps. A faster run that
  fails its audit is a failed run, not a data point.
- **Invariants that are not negotiable:** durability (for example "durable before
  acknowledgement"), security and ownership checks, protocol semantics, data formats,
  and user-visible behavior. Performance work may move work between threads or
  processes; it may not remove required work.
- **Fixed floors:** costs inherent to the workload or invariants (required round
  trips, required syncs, one conversation per agent, sequential dependency chains).
  Optimize what remains; report floors instead of fighting them.
- **Trade-off preferences:** for example whether extra memory is acceptable for speed.
  Ask when it matters and record the answer.

## 2. Measurement hygiene (every run)

- **Release builds only**, at the project's production optimization level. Never
  measure debug builds. Record the build profile, compiler version, and binary hash.
  A profiling build differs only by debug symbols (for example line tables).
- **Freeze before measuring.** Snapshot the binaries, the harness, the fixtures, and the
  plan, and record their hashes. The driver re-verifies them before every run and refuses
  to overwrite existing output. Changing code, gates, or thresholds after seeing data
  requires a new, separately labelled experiment.
- **Quiet host.** Run no builds, tests, other workloads, profilers, or heavy analysis
  during timed runs. Record host load at each run's start.
  - **Exclude evidence directories from indexing,** for example macOS Spotlight
    exclusions or a `.noindex` suffix, and note indexing or antivirus activity.
  - **Use a minimal environment allowlist** for every launched process (PATH, HOME,
    TMPDIR, USER, LANG and similar), so credentials never reach traces.
- **Disk and retention.** Preflight disk space against the expected evidence plus a
  reserve, and stop cleanly with evidence retained if the reserve is breached.
  - Delete scratch after each run.
  - Keep raw data only until its report is reviewed, then keep conclusions (reports
    plus summary JSON) unless the user asks otherwise.
  - Mark removed raw evidence in the reports instead of leaving dead links.
- **Never discard runs.** Keep every valid run, including slow ones. No rerolls until
  a favourable result appears. Stop a matrix on functional failure and preserve its
  evidence.

## 3. Find the bottleneck before changing anything

Build a model of where time goes, cheapest evidence first.

1. **Accounting, not guessing.** Bracket process and thread CPU (for example
   `getrusage` SELF and CHILDREN, and per-thread CPU clocks) around the workload.
   - Compare CPU per unit of work with wall time per unit of work.
   - Count reaped children and reconcile them against launches before trusting
     CHILDREN totals.
   - Sample per-process CPU to tell a saturated helper process from an aggregate.
2. **Find the serial resource.** For each serializing component (single writer thread,
   global lock, queue consumer, connection), measure **busy-service time against its
   lifetime**, including waiting-for-work time.
   - A component busy around 99% of the run is the throughput bound. Then
     scenario time ≈ total service time, and service saved per unit of work predicts
     the speedup. Treat this as a model that each experiment tests.
   - Split its busy time into on-CPU and off-CPU (blocked): service wall minus thread CPU.
3. **Count operations exactly.** Statements per unit of work, commits per unit of work,
   jobs per batch, rows changed, syscalls, and launches.
   - Prefer exact counts over coarse built-in timers: for example SQLite's profile
     callback has millisecond resolution, so use it for counts and over-1 ms outliers,
     never for time shares.
   - Use high-resolution timers only around outer operations (batch, commit, checkpoint).
4. **Profile stacks only once accounting points somewhere.**
   - **Compute-bound:** use a sampling CPU profiler (Time Profiler, perf, samply) on
     the release binary with line tables.
   - **Blocked:** use an off-CPU or system trace to get blocked time by syscall and
     *target file* and thread state. Inclusive frames overlap; do not add them up.
5. **Locate intermittent pauses with bounded locators.** Keep the top 32 slowest:
   - batches, with CPU against wall and their begin/jobs/commit/residual split;
   - individual jobs, with a static call-site label (for example `#[track_caller]`
     or `__FILE__:__LINE__`) captured at submission;
   - waits for work;
   - process launches;
   
   all with absolute monotonic timestamps. The three places a pause can live —
   **worker busy**, **worker starved**, and **upstream blocked** — must all be
   observable. A slow-batch list alone cannot see a starved worker.
6. **Measure progress independently of the thing you optimize.** A fast read path
   or responsive control replies prove nothing about writer progress. Sample committed
   progress counters on a separate connection, with bracketed timestamps.

## 4. Instrumentation rules

- **Opt-in, zero-cost when disabled.** No clocks, allocations, or callbacks on the
  disabled path. Strip inherited enabling variables in normal runs.
- **Bounded.** Fixed-size top-N structures and bounded key maps with explicit overflow
  counters. No unbounded logs from hot paths, and no I/O inside hot callbacks; serialize
  once at shutdown.
- **Versioned, strict formats.** The parser rejects missing, malformed, out-of-order,
  or non-reconciling records, so a "clean" report cannot come from a broken capture.
  Test the parser with corrupted evidence. Validate profiles only *after* the
  correctness audit has passed.
- **No secrets.** Record SQL text unexpanded (no bound values), never the environment,
  and never credentials or tokens.
- **Do not change the mechanism you measure.** Example: installing a SQLite WAL hook
  disables automatic checkpointing, so it is not a neutral observer. Label enabled-run
  timings as attribution only, never comparable to unprofiled runs.
- **Ownership.** Instrumentation threads and observers are owned and joined before
  shutdown. A measurement failure invalidates the comparison but must not skip cleanup
  or the audit.

## 5. Hypotheses and predicted effects

For each candidate change, state its mechanism and **predict the effect size from the
profile** before running it:

- Expected service saved ≈ (share of the work removed) × (fraction affected) × (CPU
  share of service, if CPU-bound). If the prediction is below what the experiment can
  resolve, widen the change to the whole mechanism (for example cache *all* hot
  statements, not one), or measure a lower-noise mechanism metric (CPU per unit of work)
  instead of wall time.
- Write a mechanism check that would confirm the change worked for the predicted
  reason, for example "preparation share near 0" or "file syscalls on the writer near 0".
- Check whether the change *moves* work (another thread still pays it; report total CPU)
  or *removes* it.
- Look for accounting or bookkeeping bugs first (stale counts, leaked capacity, wrong
  eviction triggers). They often cause churn far larger than any micro-optimization.

## 6. Experiment design

- **Paired, alternating A/B** on frozen binaries, with the same harness, fixture,
  limits, observers, and environment. Use paired ratios (median and geometric mean
  of within-pair ratios), not ratios of condition medians. Report every pair.
- **More than two arms:** use a Latin square, so every arm takes every position once,
  and also balance *ordered adjacency* where pairs are compared. Cyclic rotation alone
  makes the same arm always follow the same predecessor, so carryover (page cache, flush,
  thermal) biases the contrast. Record the realised order counts.
- **Predeclare gates and rules before data:**
  - throughput (for example median paired ratio at most 1.00 for non-regression);
  - tail latency on pooled samples with a minimum count (around 1,000 per arm for p99).
    Never gate on per-run maxima of about 20 samples;
  - an independent stall criterion;
  - correctness;
  - a stop rule;
  - how failures are handled. Mandatory improvements are investigated and fixed, not
    silently dropped; failed screens stay on record.
- **Stall detector:** sliding windows of at least 1 s anchored at every sample (not
  back-to-back windows, which miss pauses straddling boundaries), conservative rate
  bounds from bracketed timestamps, and a median from a non-overlapping subset. Flag
  windows below a fraction (for example 30%) of the median rate, and also flag zero
  progress for 1 s or more. Flags trigger investigation, not automatic causal claims.
- **Closed-loop observers:** disclose that slow replies reduce the sampling rate. Select
  samples by *start* time inside the active window, and keep slow replies that cross
  the boundary.
- **Separate OFF (timing) from ON (attribution) runs,** and never pool them. Attribution
  runs answer "why"; timing runs answer "how much".
- **Increments:** evaluate each against the previously accepted state (adjacent
  contrasts) plus the combined effect against the original. Scale up (for example 10× the
  workload) only after the smaller screen and its findings have been reviewed.
  Capacity- and size-dependent effects (eviction, cache misses, index depth) may appear
  only at larger scale.

## 7. Attributing pauses and regressions

- **Wall far above CPU means blocked.** Determine where: lock, syscall, page-in, or
  scheduling. With a zero busy-timeout, a database never sleeps on its own locks, so
  look below it.
- **Simultaneous blocking in unrelated threads** points to a shared lower layer
  (filesystem flush, device cache flush, kernel lock), not application logic.
- **Align every signal on one clock:** progress windows, locator spans, writer
  publication sequence and age, pool or launch counters, and native or provider events.
  Correct misaligned brackets before drawing conclusions.
- **System-wide traces capture other processes.** Export only owned PIDs, aggregate
  anything else anonymously, never open raw metadata or environment, and delete the raw
  trace immediately after export, even if the export fails.
- **Distinguish workload phases from defects.** For example, synchronized process-pool
  turnover (a cohort retiring together) produces periodic troughs that a
  median-relative detector flags more often in faster configurations. Check pool
  counters before blaming the hot path.
- **Prefer one decisive measurement over another tuning loop.** Example: blocked syscalls
  on the main database file inside commit indicate checkpoint work, while syscalls on
  the log file indicate an ordinary commit. State what data cannot decide.

## 8. Pattern catalogue

Check whether these patterns apply, and verify each one in the target before proposing it.

- **Single serialized writer or worker:**
  - **Cache compiled statements.** Cover all hot statements, including savepoint and
    transaction control, and set the cache capacity to the hot set (an LRU smaller than
    the set thrashes).
  - **Move non-database work off the serial thread,** such as filesystem, credential,
    and lease checks: *capture* an immutable snapshot, *preflight* on a bounded owned
    worker, *revalidate* identity and lifecycle on the serial thread, then commit.
    Bound retries, carry errors as data to their original validation point, never let
    the serial thread wait on the helper, and join the helper before the serial owner
    at shutdown.
  - **Serve reads from a separate read-only connection or thread:** truly read-only
    (not "immutable" snapshots that ignore the log), short snapshots, a bounded queue,
    the same authorization, read-your-writes guaranteed by acknowledge-after-commit, and
    joined before the writer closes. Label any writer-only in-memory values in read
    replies with sequence and age.
  - **Remove no-op writes:** guard triggers and updates with `WHEN` conditions so
    unchanged values are not rewritten, and apply net deltas. Prove equivalence with
    randomized recompute-and-compare tests (including nested rollback) and the same
    recompute in every benchmark audit. Bump the storage format when the schema changes.
- **SQLite and WAL specifics:**
  - `synchronous=FULL` commit syncs are a durability floor.
  - Automatic checkpoints (default 1,000 pages) run *inside the committing thread*;
    consider `wal_autocheckpoint=0` plus a dedicated checkpointer connection with a
    bounded WAL size.
  - Nested savepoints spill statement journals to temp files past about 64 KiB, so
    consider `temp_store=MEMORY` (undo data only, not durability).
  - A restarted WAL reuses its file, so file size does not count checkpoints.
  - On macOS, `fsync` is not a full device flush, and `F_FULLFSYNC` (for example Rust's
    `File::sync_all`) is much more expensive. Coalesce such syncs where invariants allow.
- **Process pools:** synchronized cohorts retire together. Warm spares, pre-launching a
  replacement near the session budget, or jittered budgets smooth turnover. Report the
  memory cost, and let the user choose the trade-off.
- **Admission and priority policies:** check starvation of other classes. In
  closed-loop burst workloads, "latency from submission" mostly measures queue drain
  (throughput), so decompose it into queue wait and service.
- **Control-plane isolation:** an independent accept or listener task keeps control
  responsive. Separately measure acceptance, queueing, and service stages before
  claiming improvement.

## 9. Implement, validate, and freeze (in-place)

Make one mechanism change per increment, with tests that prove behavior is unchanged
(errors, ordering, rollback, shutdown, ownership). Then:

- run the project's full release test suite, lints, and formatters on the **final**
  source; logs must postdate the last source edit;
- re-run any check whose start coincided with an edit;
- freeze the binary and source hashes;
- screen per section 6;
- run attribution (ON) per sections 3 and 7.

Use an independent reviewer or review loop when available. Do not modify product
source while a frozen measurement is running.

## 10. Report

- **Facts first:** paired statistics, the decomposition of latency (queue wait against
  service), CPU against wall, operation counts per unit of work, and mechanism checks.
  Mark inference and confidence explicitly.
- **Show every gate, including failures,** and why. Keep earlier failed screens visible;
  never overwrite them with later attribution.
- **Caveats:** cross-scale and cross-matrix comparisons are observations, not
  controlled causes. Single-run attribution is descriptive. A sampled size high-water
  mark is not cumulative bytes.
- **What remains:** the fixed floors reached, the remaining candidates ranked by
  predicted impact and risk, and the single most informative next measurement.
- **Retention:** keep conclusions; delete reviewed raw data per the user's policy.

Return a summary listing scope, runs executed (or, in read-only mode, none), validation
actually performed, and any reduced delegation. Do not imply measurements or tests ran
when they did not.

## Provenance

Distilled from a reviewed optimization campaign on a durable, single-writer agent
orchestrator. That campaign covered:
- a stale-worker accounting fix;
- control-listener isolation;
- statement caching;
- a separate read connection;
- moving filesystem preflight off the writer;
- trigger write reduction;
- checkpoint and fsync attribution;
- pool cohort analysis.

Its lessons are generalized here. The skill carries no dependency on that project.
