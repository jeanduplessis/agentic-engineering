# Setup, initialization, and integration

This skill is runtime-focused.
Only initialize beads or change integration files when:

- the user asks;
- a project clearly already uses beads and needs recovery;
- setup is necessary to complete the requested task.

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

If migrating a project with classic beads JSONL, ask before importing.
Name the target `.beads/` directory before mutation; in monorepos, keep root `.beads/` out of scope unless root is the target.
Back up `.beads/`, preserve `.beads/issues.jsonl`, then quarantine old `bd` local state before `br init`.
Move files only after confirmation.

Common old `bd` local state:

```text
metadata.json
config.yaml
export-state.json
backup/
embeddeddolt/
hooks/
.local_version
```

Before import, scan `.beads/issues.jsonl` for non-integer `comments[].id` values.
If found, ask before normalizing legacy string/UUID comment IDs to integer IDs.
Preserve comment text, author, timestamps, and issue IDs.

Typical sequence after backup/quarantine and approved comment-ID normalization:

```bash
br init --prefix <prefix>
br sync --import-only
br info
br ready --json
```

Verify full counts with inclusive list flags, not plain `br list --json`:

```bash
br list --all --deferred --limit 0 --json
```

Summarize large JSON output by total count and sample IDs.
Use `br sync --import-only --help` and recovery docs before adding flags such as `--rebuild`, `--merge`, or `--force`.
After any import failure, stop, report the exact error and backup path, then ask before changing recovery strategy.
After `br init`, import, or final `br sync --flush-only`, run the repo quality gate before committing if one is known/configured.
If generated metadata fails formatting, apply only the minimal formatter-compatible change and restage.
