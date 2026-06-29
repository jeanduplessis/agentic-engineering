# gw Architecture

`gw` is a macOS-only Rust CLI that manages Git worktrees through installed Git CLI. It deliberately favors direct modules over framework layers.

## Modules

```text
src/main.rs          parse command, dispatch, print top-level errors
src/cli.rs           clap command and flag definitions
src/commands/        add/list/remove/clean/init/cd/completion workflows
src/git.rs           explicit Git command execution and repository discovery
src/worktree.rs      `git worktree list --porcelain` parser and naming
src/config.rs        `.gw.yml` schema, defaults, and path resolution
src/hooks.rs         copy, symlink, and `/bin/sh -c` post-create hooks
src/shell.rs         Zsh completion and parent-shell `cd` wrapper
```

## Repository Discovery

Every command starts from current directory, verifies it is inside Git repository, and reads `git worktree list --porcelain`. First worktree record is main root. Config always loads from that main root.

## Worktree Model

- Main worktree display name: `@`.
- Managed non-main worktrees: paths beneath configured `base_dir`.
- Managed display name: path relative to `base_dir`.
- Unmanaged worktrees remain visible in `list` but cannot be navigated, removed, or cleaned by `gw`.
- Branch names containing `/` map to nested paths beneath `base_dir`.

## Commands

- `add`: resolve local branch, unique remote branch, or new branch; create worktree; run hooks.
- `list`: render all Git worktrees or names only.
- `cd`: print one managed worktree absolute path; Zsh wrapper performs actual directory change.
- `remove`: remove one managed non-main worktree and optionally branch.
- `clean`: remove managed non-main worktrees whose branches are merged into selected base branch.
- `init`: create `.gw.yml` at main repository root.
- `completion`, `hook`, `shell-init`: emit Zsh integration scripts.

## Configuration and Hooks

Missing `.gw.yml` uses default `../worktrees` base directory. Post-create hooks execute sequentially:

- `copy`: recursively copy source from main root.
- `symlink`: create symlink to source from main root.
- `command`: run `/bin/sh -c` inside new worktree or contained `work_dir`.

Destinations and command working directories cannot escape new worktree. Command hooks inherit terminal streams and receive `GIT_GW_WORKTREE_PATH` and `GIT_GW_REPO_ROOT`.

## Error and Process Handling

Git commands use `std::process::Command` with explicit argument arrays and working directories. Mutating interactive commands inherit terminal streams. Other commands capture stdout and stderr separately. Errors gain operation context through `anyhow`.

## Tests

Unit tests cover parsing, config, containment, copying, and shell scripts. `tests/cli.rs` builds temporary real Git repositories and exercises complete workflows.
