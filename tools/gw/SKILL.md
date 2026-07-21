# gw - Git Worktree Manager

`gw` is a macOS-only Rust CLI for creating, navigating, listing, removing, and cleaning Git worktrees.

## Quick Reference

```zsh
gw add <branch>                    # local, remote, or new branch
gw add --cd <branch>               # create worktree and enter it with shell integration
gw add -b <new-branch> [start]     # explicitly create branch
gw list                            # list all worktrees; alias: ls
gw list -q                         # names only
gw remove <name> [<name>...]                   # remove managed worktrees; alias: rm
gw remove --with-branch <name> [<name>...]     # remove worktrees and branches
gw remove -f <name> [<name>...]                # force dirty/locked removal
gw clean                           # remove merged managed worktrees
gw cd [name]                       # print path; defaults to main @
gw init                            # create main-root .gw.yml
eval "$(gw shell-init zsh)"        # enable Zsh completion and cd hook
```

## Worktree Naming

- `@` always means main worktree.
- Managed worktrees use paths relative to configured `base_dir`.
- Branch names map directly to nested directories under `base_dir`.

## Configuration

`.gw.yml` lives in main repository root. Missing file uses defaults.

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

Relative hook sources resolve from main root. Copy and symlink hooks are strict by default; set `optional: true` to skip a missing source and continue. Destinations and command work directories must stay inside new worktree.
