# Changelog

## 1.2.0

- Added support for removing multiple managed worktrees in one command.
- `--force`, `--with-branch`, and `--force-branch` apply to every named worktree.
- All named worktrees are resolved and safety-checked before removal begins.

## 1.1.0

- Added `optional: true` for `copy` and `symlink` post-create hooks.
- Missing optional hook sources are skipped instead of failing the post-create hook chain.
- Copy and symlink hooks remain strict by default, so existing configurations still warn on missing sources unless they opt in.
