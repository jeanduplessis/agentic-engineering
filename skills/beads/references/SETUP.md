# Setup, initialization, and integration

This skill is runtime-focused. Only initialize beads or change integration files when the user asks, when a project clearly already uses beads and needs recovery, or when setup is necessary to complete the requested task.

## Before setup

Check installed syntax and current workspace state:

```bash
br --version
br info
br where
br init --help
```

If `br` is missing, tell the user and ask before installing. Do not run installer scripts without approval.

If no database exists and the user did not ask for setup, ask how to proceed instead of initializing silently.

## Initialize

After explicit approval:

```bash
br init
br init --prefix <prefix>
```

Explain side effects before setup:

- normal setup creates or updates `.beads/`;
- `br` does not install hooks or run git;
- the user remains responsible for staging/committing `.beads/` when they want tracker state in git.

For non-interactive agent runs, use only flags supported by `br init --help`.

## Agent instruction files

`br agents` writes workflow instructions. Use it only when the user asks to configure an integration.

```bash
br agents --check
br agents --add --dry-run
br agents --add --force
br agents --update --dry-run
br agents --remove --dry-run
```

Use `--dry-run` first when practical. Do not add or update project instruction files unless setup requires them and the user agrees.

## Import existing JSONL

If migrating a project that already has classic beads JSONL, ask before importing. Typical sequence after backup:

```bash
br init --prefix <prefix>
br sync --import-only
br info
br ready --json
```

Use `br sync --import-only --help` and recovery docs before adding flags such as `--rebuild`, `--merge`, or `--force`.
