# Commit or range target

Use this procedure for one existing commit or a contiguous linear range. It verifies topology and publication status before rewriting, protects the original branch tip, and replays descendants without dropping empty commits.

## Normalize and validate

1. Require the tracked worktree and index to be clean:

   ```sh
   git diff --quiet
   git diff --cached --quiet
   ```

   Ordinary untracked files do not make the tracked tree dirty. Record `ordinary_untracked_before` and `ignored_before` as the expected final sets, and record optional `preserved_excluded_hashes` as described in `SKILL.md`. Do not stash, move, or discard any path without the user's explicit choice.
2. Normalize the target:

   - single commit `C`: `base=C^`, `range_tip=C`, `source_ref=C`;
   - range `A..B`: `base=A`, `range_tip=B`, `source_ref=B`.

3. Require `base` to be an ancestor of `range_tip` and `range_tip` to be an ancestor of `original_head`:

   ```sh
   git merge-base --is-ancestor <base> <range_tip>
   git merge-base --is-ancestor <range_tip> <original_head>
   ```

4. Reject a root commit as a single target and reject merge commits in both `<base>..<range_tip>` and `<range_tip>..<original_head>`.
5. Determine publication status for every target commit using local remote-tracking refs. A match requires explicit authorization. No match is only absence of local evidence: fetch and re-check, or ask the user to confirm the commits were never shared. Never force-push, and treat any later push as separately authorized work.
6. Record the ordered descendant list and `expected_descendant_count` for `<range_tip>..<original_head>`, including intentionally empty commits.
7. Before any reset, check every ordinary-untracked and ignored path for a collision with `base`, `range_tip`, or any descendant tree. Include prefix collisions: an untracked `dir/file` conflicts when one of those trees contains tracked file `dir`, and an untracked file `dir` conflicts when a tree contains `dir/file`. Stop and ask the user to relocate or explicitly preserve colliding paths. `git reset --hard` normally leaves unrelated untracked files alone, but it can remove an untracked path that obstructs a tracked path it must write; `git reset --mixed <base>` can reclassify an untracked path as a tracked modification; and a later cherry-pick can stop because an untracked path would be overwritten.

## Protect, unwind, and split

1. Set the backup target to `original_head`. Choose a free `backup/pre-split-<short-sha>` branch name by testing the full `refs/heads/...` name and appending an incrementing suffix on collision. Create `backup_ref`, then record `backup_sha` and its tree hash.
2. If the target is not at the branch tip, move to `range_tip`; then expose the target delta from `base`:

   ```sh
   git reset --hard <range_tip>    # non-tip target only
   git reset --mixed <base>
   ```

3. Confirm the working delta against `git diff --stat <base> <range_tip>`, never against the backup, because the backup includes descendants.
4. Build replacement commits with the shared instructions in `SKILL.md`.

## Prove the split and replay descendants

For a non-tip target, prove the split before replay:

```sh
git rev-parse HEAD^{tree}
git rev-parse <range_tip>^{tree}
```

The hashes must match. Record the replacement tip before replay:

```sh
new_split_tip=$(git rev-parse HEAD)
```

Replay descendants in original order with hooks disabled and empty commits preserved:

```sh
git -c core.hooksPath=<absolute-empty-dir> cherry-pick \
  --allow-empty --keep-redundant-commits <range_tip>..<original_head>
```

On conflict, abort the cherry-pick, restore from the backup, and stop. Do not edit a conflict resolution: the pre-replay tree matched the descendant's original parent tree.

Verify that empty descendants were not silently lost:

```sh
git rev-list --count <range_tip>..<original_head>
git rev-list --count <new_split_tip>..HEAD
```

Both counts must equal `expected_descendant_count`, and every old descendant must appear in the old-to-new mapping. A deployment that cannot preserve empty commits with these flags must reject such descendants during preflight rather than skip them.

## Final proof and recovery

Apply the shared final comparison against `backup_ref`, the clean status and path-set checks, optional preserved-hash equality, and the validation gate.

The final ordinary-untracked set must equal `ordinary_untracked_before`, and the final ignored set must equal `ignored_before`.

Recovery after the backup exists is:

```sh
git reset --hard <backup_ref>
```

Because `HEAD` once referenced `original_head`, its SHA normally remains in the reflog after backup deletion for the repository's reflog-retention period. Report the backup SHA regardless.
