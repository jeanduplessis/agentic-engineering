# Repository guidelines

## Project

- `ghh` is a Rust CLI helper for approving GitHub pull requests through the local GitHub CLI (`gh`).
- The only command is `ghh stamp`, which approves one or more PRs in a single repository.
- `gh` remains the source of truth for authentication and GitHub API behavior.
- PRs are processed sequentially, and processing stops on the first failed approval.
- Keep process arguments separate; do not invoke `gh` through a shell.

## Development commands

- Format: `cargo fmt --all`
- Format check: `cargo fmt --all -- --check`
- Lint: `cargo clippy --all-targets --all-features -- -D warnings`
- Test: `cargo test --all-targets`
- Build: `cargo build --release`
- Install locally: `cargo install --path . --force`
- Run without installing: `cargo run -- <args>`

Before completing implementation work, run the format check, Clippy, tests, and release build.

For version requirements and the release checklist, see [`RELEASE.md`](RELEASE.md).

## Coding style

- Follow standard Rust formatting and Clippy guidance.
- Keep the implementation small and direct; avoid abstractions without a current need.
- Preserve useful `gh` error output when an approval fails.
- Keep destructive or remote-mutating actions explicit in command names and help text.
- Add context to process-launch and exit-status errors.

## Testing

- Unit-test parsing and validation without calling GitHub.
- Use a fake `gh` executable for command behavior tests; do not make live GitHub calls in automated tests.
- Add a regression test when changing argument construction, failure handling, or multi-PR behavior.
- Keep tests isolated from the user's GitHub CLI configuration and authentication.

## Git hygiene

- Follow Conventional Commits when commits are requested.
- Never commit GitHub tokens, credentials, or captured private PR data.
- Do not revert unrelated user changes.
