---
name: microskills-review-generator
description: >-
  Study a codebase's stack and architecture and generate as many narrow,
  project-specific review checklists ("microskills") as the evidence supports, one skill
  file per microskill, then report where they were written. Use to prepare exhaustive
  single-family review passes, such as unchecked errors, lost async failures, leaked
  resources, missing timeouts or authorization gaps, for microskills-review-runner. It
  only writes microskill files: it never runs them, never changes project code and never
  executes builds or tests.
---

# Microskills review generator

An agent finds far more when it is told exactly which problems to look for and how to
recognize them. General review skills ask for "problems". A **microskill** is a short
checklist for one family of defects, written for this codebase: its APIs, wrappers,
conventions and risky places. This skill writes them. `microskills-review-runner` runs each one
as an independent, exhaustive pass, a **micropass**, and merges the results.

## Invocation

```text
/microskills-review-generator [--output DIR] [--max N] [<target>]
```

- **`--output DIR`:** where to write the microskills. It defaults to `.microskills/` at
  the repository root. The directory is created if missing.
- **`--max N`:** at most `N` new microskills. By default there is no limit: write as
  many as the evidence supports.
- **`<target>`:** the code to study, a file or directory path. It defaults to the
  whole repository, with `.` meaning the same.

An invalid value requires a corrected invocation; do not guess.

### Example activations

```text
/microskills-review-generator
/microskills-review-generator --output /reviews/hive-microskills .
/microskills-review-generator --max 20 src/runtime/
```

## Boundaries

- **Static study only.** Read code, build files, configuration, documentation and
  repository instructions. Do not build, test, run the project, or run microskills.
- **Write only the microskill files and `INDEX.md`** in the output directory. Never edit
  project code, stage, commit or push.
- **Never overwrite** an existing microskill: the user owns those files. Skip names that
  already exist, and propose any changes to them in the report.
- **Launch no subagents.** One agent studying the whole codebase keeps the microskills
  consistent and free of overlap.

## 1. Learn the codebase

Record the facts the microskills will depend on, with evidence: paths, packages, counts
of call sites.

- **Stack:** languages, frameworks, runtimes and build files.
- **Concurrency model:** threads, async runtime, workers, queues and schedulers.
- **Persistence:** databases, transactions, files, caches and migrations.
- **External I/O:** HTTP and RPC clients, sockets, subprocesses and brokers.
- **Trust boundaries:** CLI, HTTP, RPC, files, environment, plugins, and model or tool
  input.
- **Conventions:** the error type and propagation style, the logger and its fields,
  wrappers and helpers, lint and policy gates, and existing review checklists.
- **Domain hazards:** money, time, units, identity, permissions and multi-tenancy.
- **Hot spots:** large or central modules, recent churn, and known-fragile areas named
  in docs or issues.

## 2. Choose the microskills

1. **Start from the catalogue.** Use [references/catalogue.md](references/catalogue.md).
   Keep a family only when the code shows it applies, and cite the evidence. Add
   families the catalogue lacks whenever this architecture has its own hazards, such
   as a custom transaction layer, a plugin ABI, a cache with invalidation rules, or a
   state machine.
2. **Always include `errors-and-logging`**, adapted to the project.
3. **Make each microskill narrow.** One defect family each, with 3–8 checklist items.
   Split broad areas by the mechanism a reviewer must trace. For example, concurrency
   becomes shared-state races, locks held across await, lost background failures, and
   cancellation and shutdown.
4. **Make every item checkable.** A site either has the defect or it does not. "Errors
   are handled" is a theme. "A `Result` is assigned to `_` or dropped with `.ok()`
   outside tests" is a checkable item.
5. **Be specific to this codebase.** Name its functions, types, wrappers, file areas
   and grep anchors, and the indirect forms a grep misses. State what is **not** a
   finding here, and the preferred fix.
6. **Avoid overlap.** When two microskills would check the same thing, assign it to
   one, and mention the boundary in both.
7. **Rank by expected yield** when `--max` applies: the hazards most common in this
   code first, and those with the worst failures if missed.

There is no target count. A small service may need a handful of microskills, and a
large system several dozen. Write every microskill the evidence supports.

## 3. Write one skill file per microskill

For each microskill, write `OUTPUT/<name>/SKILL.md` using
[references/template.md](references/template.md). Each file is a complete skill:
`name` and `description` in the frontmatter, then the checklist. It can be read or run
on its own.

Check that each file's frontmatter parses as YAML before reporting it as written.

Then write `OUTPUT/INDEX.md` with:

- the repository path, commit and generation date;
- the stack facts from step 1;
- a table with one row per microskill: name, family, scope, item count and evidence;
- the families considered and skipped, and why.

When `INDEX.md` already exists, add the new rows and keep the existing ones.

## 4. Report

Return:

- the **absolute path** of the output directory;
- the list of microskills written: name, one-line purpose, and file path;
- names skipped because they already exist, with proposed changes to them;
- skipped families, and why;
- the next command to run, for example
  `/microskills-review-runner --skills /abs/path/.microskills --finders 12 .`. Without
  `--finders`, the runner launches no agents and runs the passes one at a time. Leave
  the choice of `N` to the user.
