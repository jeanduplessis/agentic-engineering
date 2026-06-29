# Testing Guidelines

## Commands

```zsh
cargo test --all-targets
cargo test --test cli
cargo clippy --all-targets -- -D warnings
cargo fmt --all -- --check
```

## Test Levels

Use unit tests beside implementation for deterministic logic:

- Worktree porcelain parsing and naming
- Configuration defaults and path resolution
- Hook path containment and filesystem helpers
- Zsh script generation
- Completion candidate filtering

Use `tests/cli.rs` for complete workflows that require real Git repositories:

- Add, list, cd, remove, and clean
- Main-root config creation from nested directories
- Post-create copy, symlink, and command hooks
- Remote branch behavior
- Safety failures around main/current/unmanaged worktrees

## Integration Test Isolation

Each CLI test must:

- Create its own temporary repository and worktree directory.
- Initialize main branch and initial commit.
- Set repository-local Git identity.
- Disable signing and hooks.
- Set `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CONFIG_NOSYSTEM=1`.
- Assert filesystem and Git state, not exact decorative output.

## Priorities

Prioritize tests that prevent data loss or broken daily workflows:

1. Main and current worktrees cannot be removed.
2. `clean` removes only merged managed worktrees.
3. Hook destinations and working directories stay inside new worktree.
4. `gw cd` prints only target path.
5. `gw init` writes to main repository root.
6. Zsh completion returns usable branch and worktree names.

Add regression tests when real use exposes issues. Avoid exhaustive compatibility snapshots or tests for unsupported platforms and shells.
