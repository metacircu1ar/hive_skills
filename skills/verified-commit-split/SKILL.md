---
name: verified-commit-split
description: "Split uncommitted work, one commit, or a contiguous commit range into smaller logical commits, and prove the resulting tree matches a protected copy of the original state. Use for reviewability, bisectability, or history hygiene when final repository content must not change."
metadata:
  version: "1.0.0"
  argument-hint: "[uncommitted | <commit> | <base>..<tip>]"
  compatibility: "Requires Git and a filesystem-enabled coding agent. Uses no interactive Git, never force-pushes, and requires separate authorization before rewriting known-published history."
---

# Verified Commit Split

Split one unit of work into logical commits and prove that the final Git tree is unchanged. Tree identity proves content preservation; it does not prove that the chosen commit boundaries are good, so validate each new commit separately.

## Select one target procedure

Read exactly one target reference before any mutation:

- For staged, unstaged, and selected new files, read [references/uncommitted.md](references/uncommitted.md).
- For one existing commit or a contiguous linear range, read [references/commit-or-range.md](references/commit-or-range.md).

Both procedures produce `base`, `source_ref`, `backup_ref`, `backup_sha`, `original_head`, and mode-specific recovery commands. Use the shared rules below after the selected procedure tells you to build the replacement commits.

## Mandatory invariants

1. Never change content to make the split cleaner. Fixes and formatting belong in later work.
2. Create the backup ref before moving the current branch or rewriting history. Retain it on every failure or unresolved gate.
3. Use tree-hash equality as the content proof. A visual diff, diffstat, or passing test suite is not a substitute.
4. Do not use interactive Git: no `rebase -i`, `add -p`, `checkout -p`, or editor-driven flows.
5. Disable every Git hook for reconstruction commits and descendant cherry-picks with an empty `core.hooksPath`; `--no-verify` alone does not suppress all hooks.
6. Never force-push. Rewriting history known or possibly to be published requires explicit authorization; pushing rewritten history is a separate action requiring separate authorization.
7. Account for tracked, ordinary-untracked, and ignored paths separately. Default porcelain collapses untracked directories and hides ignored files.
8. Delete the backup only after every applicable content, inventory, hash, descendant, and validation gate passes.
9. Report skipped checks as skipped, never as passing.

## Shared preflight and boundary record

Before mutation:

1. Confirm a Git work tree and record `original_head` and the current branch. Detached `HEAD` requires the user to name where the result should land.
2. Stop if a rebase, merge, cherry-pick, revert, or bisect is in progress. Check `rebase-merge/`, `rebase-apply/`, `MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, and `BISECT_LOG` under `git rev-parse --git-dir`.
3. Record the project's practical build, test, lint, and type-check commands.
4. Record individual path sets, never collapsed directory summaries:

   ```sh
   git ls-files --others --exclude-standard
   git ls-files --others --ignored --exclude-standard
   ```

   Call these `ordinary_untracked_before` and `ignored_before`. The selected target procedure defines which paths enter the snapshot and therefore the expected final sets.
5. For any excluded regular file that must remain byte-identical, record a path-to-hash mapping with `git hash-object --no-filters -- <path>`. Call it `preserved_excluded_hashes`. If no hashes are recorded, state explicitly that excluded-file contents are outside the proof.
6. Create one empty hooks directory with `mktemp -d`, record its absolute path, and reuse that literal path in every later Git command. Do not assume a shell variable persists across tool calls. Remove it at the end with `rmdir` only; if it is unexpectedly non-empty, retain it and report that fact.

## Build the replacement commits

Build forward from `base`, earliest prerequisite first.

For a path-disjoint commit:

```sh
git add -- <ordinary paths>
git add -f -- <new ignored paths>
git -c core.hooksPath=<absolute-empty-dir> commit --no-verify -m "<message>"
```

After every commit, `git diff --cached --quiet` must succeed before staging the next one.

For changes within one file, materialize the intended intermediate content and commit it. For the last commit touching that path, derive the final state from `source_ref`: use `git checkout <source_ref> -- <path>` when the path exists there, or remove and stage the path when its final state is absent. Newly added ignored paths still require `git add -f`. Use the same hook-disabled commit command every time.

Prefer materializing intermediate content over editing a hand-built patch. If clean separation is not possible, fall back to file granularity and report the reduced granularity rather than changing final content.

Run practical validation after each commit when appropriate. Record the command and result. Reorder commits when a missing prerequisite makes an intermediate commit invalid; do not hide a failing commit.

## Shared completion gates

Before deleting the backup:

1. Prove final tracked content:

   ```sh
   git rev-parse HEAD^{tree}
   git rev-parse <backup_ref>^{tree}
   ```

   The hashes must match exactly. This covers blobs, modes, symlinks, and submodule pointers, but not commit metadata or excluded working-tree files.
2. Confirm no tracked or staged residue and compare individual path sets:

   ```sh
   git status --porcelain=v1 --untracked-files=all
   git ls-files --others --exclude-standard
   git ls-files --others --ignored --exclude-standard
   ```

   The ordinary-untracked and ignored sets must equal the expected sets recorded by the selected target procedure. A new file inside an already excluded directory is still a mismatch.
3. If `preserved_excluded_hashes` is non-empty, recompute every hash and require the complete path-to-hash mapping to match. A missing or changed file is a failure. The Git backup cannot restore excluded files, so report any mismatch explicitly and do not delete the backup.
4. Require the selected target procedure's extra gates, including pre-replay tree identity and descendant-count equality where applicable.
5. Require per-commit validation to pass, or obtain the user's explicit acceptance of each skipped or failed check.

On a tree or history failure, use the selected procedure's recovery commands, retain the backup, and report the exact diff. On an inventory or excluded-hash failure, retain the backup and report the affected paths; do not claim the Git backup can recover files it never contained.

Delete the backup only after all applicable gates pass:

```sh
git branch -D <backup_ref>
```

Remove the empty hooks directory with `rmdir <absolute-empty-dir>`.

## Final report

State:

- target type, `base`, `source_ref`, `original_head`, backup name, and backup SHA;
- in-scope and excluded ordinary-untracked and ignored paths;
- whether excluded-file hashes were recorded and whether every recorded hash matched;
- new commits in order, their intent, and the old-to-new mapping;
- every required tree-hash pair and an explicit match statement for each;
- descendant counts and mapping when descendants were replayed;
- validation commands and results, including explicit skips or accepted failures;
- any granularity reduction;
- whether the backup was deleted or retained and the target-specific recovery limitation;
- any separately authorized next action, such as pushing rewritten history.

## Failure rules

- Stop before mutation when target scope, new-file scope, topology, publication status, or recovery location is unclear.
- Abort an in-progress descendant cherry-pick before using the mode-specific recovery commands.
- A tree mismatch, path-set mismatch, preserved-hash mismatch, descendant mismatch, or unaccepted validation result keeps the backup.
- Never resolve a replay conflict by editing content; exact pre-replay tree identity means the descendant should apply to the same state as before.
- Never claim proof from commands that were not executed.

## Example activations

- "Split my uncommitted changes into separate commits for the API change and the migration."
- "This commit does three things—split it and prove nothing changed."
- "Take the last four commits and resplit them by component."
- "Break `HEAD~3..HEAD~1` into smaller commits and replay the rest on top."
