# Uncommitted target

Use this procedure for staged, unstaged, and explicitly selected new files. It creates a hook-free synthetic commit without moving `HEAD`, then protects that commit with a backup branch.

## Normalize and decide scope

1. Set `base = original_head`. There are no descendants and no existing history to rewrite, so do not run range ancestry, merge, root, or publication checks.
2. Present `ordinary_untracked_before` and `ignored_before`. Ask which paths belong to the requested change; do not guess.
3. Record four disjoint sets: `ordinary_in_scope`, `ordinary_excluded`, `ignored_in_scope`, and `ignored_excluded`.
4. The expected final ordinary-untracked set is `ordinary_excluded`; the expected final ignored set is `ignored_excluded` because in-scope new files become tracked.
5. Record optional `preserved_excluded_hashes` as described in `SKILL.md` before staging anything.

## Capture the source tree

1. Stage all tracked changes and the selected new files. Use explicit paths when any new file is excluded, and force-add selected ignored files:

   ```sh
   git add -- <tracked and ordinary-in-scope paths>
   git add -f -- <ignored-in-scope paths>
   ```

2. Verify the snapshot boundary with separate checks:

   - `git diff --quiet` succeeds, proving no unstaged tracked change was left behind;
   - `git ls-files --others --exclude-standard` equals `ordinary_excluded`;
   - `git ls-files --others --ignored --exclude-standard` equals `ignored_excluded`;
   - `git diff --cached --name-status HEAD` matches the intended staged operations.

   Accept `A` for additions, `M` for edits, `D` for deletions, `T` for type changes, and `R<score>` for detected renames. A rename may instead appear as `D` plus `A`; a copy appears as `C<score>` only when copy detection is enabled. Do not verify by requiring every intended path to exist in the resulting tree: deleted paths and old rename paths must be absent.
3. Capture the index without hooks or a branch move:

   ```sh
   TREE=$(git write-tree)
   SNAP=$(git commit-tree "$TREE" -p HEAD -m "TEMP: pre-split snapshot")
   ```

4. Set `source_ref = SNAP` and `range_tip = SNAP`.
5. Choose a free `backup/pre-split-<short-sha>` branch name. Test the full `refs/heads/...` name; on collision append an incrementing suffix. Create `backup_ref` at `SNAP`, then record `backup_sha` and its tree hash.

The backup exists before the current branch moves. `commit-tree` runs no commit hooks and leaves `HEAD` unchanged.

## Unwind and split

Clear the index while preserving the working tree:

```sh
git reset --mixed HEAD
```

Confirm the unwound delta explicitly:

```sh
git diff --stat <base> <source_ref>                 # complete expected delta
git diff --stat                                     # tracked working-tree portion
git ls-files --others --exclude-standard            # ordinary new files
git ls-files --others --ignored --exclude-standard  # ignored new files
```

The complete expected delta must equal the tracked working-tree portion plus `ordinary_in_scope` and `ignored_in_scope`. After the mixed reset, the ordinary-untracked inventory must again equal `ordinary_untracked_before`, and the ignored inventory must equal `ignored_before`. Any discrepancy means the source delta was not exposed completely; stop before building commits.

Then build replacement commits using the shared instructions in `SKILL.md`. Skip descendant replay entirely.

## Proof and recovery

The shared final comparison is `HEAD^{tree}` against `backup_ref^{tree}`. Apply the shared ordinary-untracked, ignored, optional-hash, and validation gates as well.

Recovery after the backup exists requires both commands:

```sh
git reset --hard <backup_ref>
git reset --mixed <base>
```

This restores content and returns the branch to `base`, but it cannot reconstruct the original staged/unstaged partition. After successful proof and backup deletion, the synthetic snapshot was never referenced by `HEAD`; it remains reachable by its recorded SHA only until Git prunes the dangling object, not through `git reflog`.
