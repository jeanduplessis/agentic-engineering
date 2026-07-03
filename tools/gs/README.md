# gs

`gs` prints a compact, colorized enhanced status view for the current Git repository.

```shell
 ───────────────────────────────────
 Branch: main                 ↑1 ↓0
 Commit: a1b2c3d Show latest commit
 ───────────────────────────────────

 Staged (4)                  +162/-48
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
   M AGENT_LEXICON.md         +8/-4
   M README.md               +18/-13
   M src/renderer.rs        +122/-20
   M tests/cli_behavior.rs   +14/-11

 Tracked (4)                  +53/-55
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
   M AGENT_LEXICON.md        +19/-13
   M README.md                +6/-5
   M src/renderer.rs         +16/-26
   M tests/cli_behavior.rs   +12/-11
```

## Install

### Requirements

- Rust/Cargo installed locally

Check Cargo:

```sh
cargo --version
```

If Cargo is missing, install Rust from <https://rustup.rs/> or your system package manager.

### Install from this checkout

From the repository root:

```sh
cargo install --path .
```

This installs `gs` to Cargo's bin directory, usually:

```sh
~/.cargo/bin/gs
```

Verify installation:

```sh
gs --version
which gs
```

If `gs` is not found, add Cargo's bin directory to your `PATH`.

For zsh, add this to `~/.zshrc`:

```sh
export PATH="$HOME/.cargo/bin:$PATH"
```

Then reload your shell:

```sh
source ~/.zshrc
```

### Update after local changes

From the repository root:

```sh
cargo install --path . --force
```

### Uninstall

```sh
cargo uninstall gs
```

## Usage

Run inside any Git repository:

```sh
gs
```

Color options:

```sh
gs --color=auto    # default: color only when stdout is a TTY
gs --color=always  # always emit ANSI 256-color output
gs --color=never   # plain output for scripts or copy/paste
```

## Output

Output is padded with a one-space left buffer.

A clean repository shows the Branch header and Latest commit line framed by border lines plus Clean repository output:

```text
 ──────────────────────────────
 Branch: main ↑0 ↓0
 Commit: a1b2c3d Initial commit
 ──────────────────────────────
 ✓ working tree clean
```

A repository with changes shows the Branch header and Latest commit line framed by border lines, followed by visible Sections only:

```text
 ───────────────────────────
 Branch: main     ↑1 ↓2
 Commit: a1b2c3d Update view
 ───────────────────────────

 Staged (1)       +3/-1
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
   M src/lib.rs      +3/-1

 Tracked (1)      +0/-4
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
   D old.txt         +0/-4

 Untracked (1)    +2/-0
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
   ? notes.txt       +2/-0
```

Sections:

- `Staged`: index changes that are commit-ready.
- `Tracked`: unstaged worktree changes to tracked files.
- `Untracked`: untracked, non-ignored files.

Entry stats:

- Section headings include aggregate stats for that Section.
- A blank line separates the repository context from the first Section.
- A muted dashed divider separates each Section heading from its entries.
- `+N/-N`: Known text stats.
- `+?/-?`: Unknown stats, used for binary, non-line-oriented, or submodule path-level changes.
- The `/` separator is vertically aligned across entries.
- In colored output, Section headings stay plain; Staged entries are green, Tracked entries are tan, and Untracked entries are muted gray.
- Branch names and ahead counts are green; behind counts are red; commit hashes are tan.
- Additions are green, the `/` separator and border lines are muted gray, and deletions are red.

Path and sorting behavior:

- Paths are repository-root-relative, regardless of where you run `gs` inside the repo.
- Entries sort alphabetically by Display path.
- Renames display as `old/path -> new/path`.
- Partially staged files appear once in `Staged` and once in `Tracked`, with separate stats.

Branch header behavior:

- Branches render as `Branch: branch ↑ahead ↓behind`.
- Ahead/behind counts are always shown, even when `0`.
- Detached HEAD renders as `detached @ <short-sha>`.

Latest commit line behavior:

- Repositories with commits render `Commit: <short-hash> <subject>` below the Branch header.
- The subject is the first line of the latest commit message at `HEAD`.
- Unborn branches omit the Latest commit line.

## Errors

Outside a Git repository, `gs` exits with code `1` and prints:

```text
gs: not a git repository
```

## Development

Run tests:

```sh
cargo test
```
