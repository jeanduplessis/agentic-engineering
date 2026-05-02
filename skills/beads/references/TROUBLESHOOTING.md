# Troubleshooting br

Prefer diagnosis and reversible actions. Ask before destructive repairs, setup changes, database rebuilds, imports, merges, or deletes.

## First checks

```bash
br --version
br info
br where
br sync --status --json
br status --json
br doctor --json
```

If a command fails, rerun `br <command> --help` to confirm the installed version supports the command and flags you planned to use.

## Common failures

Availability/setup:

- `br: command not found`: tell the user br is not installed; ask before installing.
- No beads database: if setup was requested, initialize carefully; otherwise ask before changing the repo.
- Unknown flag/command: use `br <command> --help`; br CLI changes across versions.

Input/queue state:

- Shell quoting breaks text:
  - long issue descriptions: temp file plus `--description "$(cat file.md)"`;
  - long comments: `br comments add <id> --file file.md --json`.
- Ready queue looks wrong: inspect blockers, dependency trees, dependency cycles, and deferred state.

Health/sync:

- Database health is unclear: run `br doctor --json` and summarize only relevant findings.
- Sync state is unclear: run `br sync --status --json`; do not run import/merge/rebuild without approval.

## Doctor and repair

`br doctor` is the health-check entry point:

```bash
br doctor --json
br doctor --repair --json
```

Run repair only when the user approves or when the requested task cannot continue without it and the user confirms the risk.

## Setup or initialization problems

If the user asked to set up beads and no database exists:

1. Run `br init --help` and pick flags supported by the installed CLI.
2. Explain that setup writes `.beads/` and that `br` does not run git.
3. Initialize only after approval.
4. Use `br agents --check` / `br agents --add --dry-run` only if the user asked for agent instruction integration.

For existing projects, do not overwrite or reinitialize beads data without explicit confirmation.

## Sync and storage issues

Most agent task tracking does not require storage-internal checks.
Investigate sync/storage only when the user asks or br reports a storage error that blocks the task.

Safe/read-only checks:

```bash
br where
br sync --status --json
br doctor --json
```

Potentially mutating commands require approval:

```bash
br sync --flush-only
br sync --import-only
br sync --merge
br sync --import-only --rebuild
br doctor --repair
```

Do not run bare `br sync`; choose an explicit mode.

## Handoff unresolved problems

If you cannot resolve a beads problem in-session, leave a useful comment or note when a current issue ID is known and br writes still work. Include:

- br version;
- workspace path from `br where`;
- failing command and exact error;
- relevant `br doctor --json` or `br sync --status --json` findings;
- what you did not try because it might mutate data or setup.
