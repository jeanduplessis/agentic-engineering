# gw

Personal macOS Git worktree manager written in Rust. Creates worktrees, runs post-create hooks, cleans merged worktrees, and provides Zsh navigation and completion.

## Install

```zsh
cargo install --path .
eval "$(gw shell-init zsh)"
```

Add shell initialization line to `~/.zshrc` for persistent setup.

## Commands

```text
gw add <branch>                 create worktree for local, remote, or new branch
gw add --cd <branch>            create worktree and enter it with shell integration
gw add -b <branch> [start]      create new branch and worktree
gw list                         list all worktrees
gw list --quiet                 print worktree names only
gw remove <name> [<name>...]                remove managed worktrees
gw remove --with-branch <name> [<name>...]  remove worktrees and branches
gw clean                        remove merged managed worktrees and branches
gw cd [name]                    print worktree path; defaults to @
gw init                         create .gw.yml at main repository root
gw shell-init zsh               emit Zsh completion and cd hook
```

Main worktree is named `@`. Other managed worktrees use paths relative to `base_dir`, so branch `feature/auth` becomes `feature/auth`.

## Configuration

`gw init` creates `.gw.yml` in main repository root even when invoked from a subdirectory or linked worktree. Missing config uses defaults.

```yaml
version: "1.0"
defaults:
  base_dir: ../worktrees
hooks:
  post_create:
    - type: copy
      from: .env.example
      to: .env
      optional: true
    - type: symlink
      from: .bin
      to: .bin
    - type: command
      command: cargo build
      env:
        RUST_BACKTRACE: "1"
      work_dir: .
```

Relative hook sources resolve from main repository. Copy and symlink hooks are strict by default; set `optional: true` to skip a missing source and continue. Hook destinations and command working directories must stay inside new worktree. Command hooks run through `/bin/sh -c` and receive `GIT_GW_WORKTREE_PATH` and `GIT_GW_REPO_ROOT`.

## Development

```zsh
cargo fmt --all
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
cargo build --release
```

## License

MIT
