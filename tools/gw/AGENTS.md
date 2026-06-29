# Repository Guidelines

## Project

- `gw` is a personal, macOS-only Git worktree manager written in Rust
- Zsh is only supported shell integration target
- Git CLI remains source of truth for repository and worktree operations
- CLI entrypoint: `src/main.rs`; reusable implementation: `src/lib.rs`
- Commands: `src/commands/`; shared modules: `src/{git,config,hooks,worktree,shell}.rs`
- Unit tests live beside code; real Git workflow tests live in `tests/cli.rs`

## Development Commands

- Format: `cargo fmt --all`
- Format check: `cargo fmt --all -- --check`
- Lint: `cargo clippy --all-targets -- -D warnings`
- Test: `cargo test --all-targets`
- Build: `cargo build --release`
- Install locally: `cargo install --path .`
- Run without install: `cargo run -- <args>`

Before completing implementation work, run format check, Clippy, tests, and release build.

## Coding Style

- Follow standard Rust formatting and Clippy guidance.
- Keep modules small and direct; avoid abstractions without current need.
- Add context to filesystem, process, and Git errors with `anyhow::Context`.
- Keep destructive Git operations narrow and explicitly protect main/current worktrees.
- Use `Path`/`PathBuf` for paths and pass Git arguments without shell interpolation.
- Shell command hooks intentionally run through `/bin/sh -c`; all other Git commands use `std::process::Command` argument arrays.

## Core Behavior

- Main worktree is always named `@`.
- Managed worktrees live under configured `defaults.base_dir`; default is `../worktrees` relative to main root.
- `list` shows managed and unmanaged worktrees; `cd`, `remove`, and `clean` operate only on managed worktrees.
- `gw cd` prints one absolute path. Zsh hook performs parent-shell directory change.
- `gw init` always creates `.gw.yml` at main repository root, regardless of invocation directory.
- Post-create hooks run sequentially. Copy/symlink sources resolve from main root; destinations and command work directories stay inside new worktree.
- Hook failures warn after successful worktree creation rather than removing worktree.
- Only Zsh completion/hook behavior is supported.

## Testing

- Unit-test parsing, path containment, config defaults, and script generation near implementation.
- Integration-test user workflows with temporary real Git repositories in `tests/cli.rs`.
- Add regression test when real use exposes issue; do not preserve obsolete Go behavior for compatibility.
- Keep tests isolated from global Git configuration.

## Git Hygiene

- Follow Conventional Commits when commits are requested.
- Never commit secrets or local `.gw.yml` values containing secrets.
- Do not revert unrelated user changes.
