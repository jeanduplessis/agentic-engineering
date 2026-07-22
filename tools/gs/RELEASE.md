# Release process

`gs` releases are built and installed from this monorepo. There is currently no tag-based, GitHub Release, or package-registry workflow.

## Requirements

- Run releases on macOS with a Rust toolchain that supports edition 2024.
- Start from a release branch based on the current local `main` branch.
- Keep the `main` worktree clean before merging.
- Use semantic versioning. Update `Cargo.toml`, the `gs` package entry in `Cargo.lock`, and `CHANGELOG.md` to the same version.
- Put the newest changelog entry first and describe user-visible changes.
- Pass formatting, Clippy, all tests, the release build, and a version smoke test before committing.
- Do not push, create a tag, or create a GitHub Release unless explicitly requested.

## Instructions

Run package commands from `tools/gs` unless a step says otherwise.

1. Check the release branch and the `main` worktree:

   ```zsh
   git status --short --branch
   git log --oneline -10
   git worktree list
   ```

2. Choose the next semantic version and update:

   - `Cargo.toml`: `[package].version`
   - `Cargo.lock`: the `gs` package version
   - `CHANGELOG.md`: add a section for the release

3. Validate the release:

   ```zsh
   cargo fmt --all -- --check
   cargo clippy --all-targets --all-features -- -D warnings
   cargo test --all-targets
   cargo build --release
   ./target/release/gs --version
   ```

   The reported version must match `Cargo.toml` and `CHANGELOG.md`.

4. Review and commit only the intended release files:

   ```zsh
   git status --short
   git diff --check
   git diff
   git add <exact-paths>
   git diff --cached --name-status
   git commit -m "feat(gs): release X.Y.Z"
   ```

5. In the clean `main` worktree, fast-forward to the release branch:

   ```zsh
   git merge --ff-only <release-branch>
   git status --short --branch
   ```

6. Rebuild the installed binary from `main`:

   ```zsh
   cd tools/gs
   cargo install --path . --force
   command -v gs
   gs --version
   ```

   Confirm that the resolved executable reports the new version.

7. If publishing was explicitly requested, push `main` after checking its upstream and ahead/behind state. Tags and GitHub Releases are not part of the current release process.
