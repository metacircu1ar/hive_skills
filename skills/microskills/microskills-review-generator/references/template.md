# Microskill template

Write each microskill as its own skill file, `OUTPUT/<name>/SKILL.md`. Keep it short:
a micropass must be able to hold the whole file in mind while it checks each site.
`microskills-review-runner` supplies the procedure (inventory every site, check every item,
return findings), so the file holds only what is specific to this defect family and
this codebase.

```markdown
---
name: NAME
description: >-
  One sentence naming the defect family this pass finds, e.g. Find background
  tasks whose failures are never observed in this tokio service.
---

# One-line statement of the defect family

## Applies here

- Family: catalogue family, or "project" for one this codebase needs.
- Scope: paths or globs where it applies, e.g. `crates/worker/**`, `src/runtime/**`.
- Evidence: why it applies, e.g. "tokio runtime; 61 `tokio::spawn` sites;
  `JoinHandle` values dropped in crates/worker".

## Look for

1. A concrete, checkable defect, stated so a site either has it or does not.
2. ...
3. ...

## How to recognize it here

- This project's functions, types, wrappers and macros that mark candidate sites,
  e.g. `spawn_supervised`, `Store::transaction`, `retry_with_backoff`.
- File areas and grep anchors that lead to them, and the indirect forms a grep misses.
- The local conventions that define "correct", such as the logger, the error type and
  the boundary that owns logging.

## Not a finding

- Explicit exclusions that keep the pass quiet, e.g. "test-only helpers", or "errors
  deliberately ignored with a documented reason".
- Defects that belong to another microskill: name it.

## Fix

- The preferred correction in this codebase, with a short example if it helps.
- What a fix must preserve, such as the original error cause or a single log record.
```

Use kebab-case names, unique within the output directory, such as
`errors-and-logging`, `async-lost-failures` or `sql-transaction-scope`. Always write
`description` as a folded scalar (`>-`), as above. A plain one-line value breaks YAML
as soon as the text contains `: `.
