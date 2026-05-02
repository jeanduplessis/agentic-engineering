# Troubleshooting br

Prefer diagnosis and reversible actions. Ask before destructive repairs, setup changes, database rebuilds, imports, merges, or deletes.

## Table of contents

- [First checks](#first-checks)
- [Common failures](#common-failures)
- [Doctor and repair](#doctor-and-repair)
- [Doctor summaries](#doctor-summaries)
- [Cleanup side effects](#cleanup-side-effects)
- [Setup or initialization problems](#setup-or-initialization-problems)
- [Sync and storage issues](#sync-and-storage-issues)
- [Handoff unresolved problems](#handoff-unresolved-problems)

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

## Doctor summaries

When summarizing `br doctor --json`, report separately:

- `ok`;
- `workspace_health`;
- `reliability_audit.anomalies`;
- every non-OK check.

Do not call the result clean if warnings, recoverable health, degraded health, or anomalies remain.
Distinguish "non-OK checks cleared" from "workspace health is clean".
If `workspace_health: recoverable` remains due to `truncated_wal`, say so explicitly.

Do not escalate warning-only output to repair when all are true:

- `ok: true`;
- issue counts match JSONL;
- sync dirty count is zero;
- warnings are limited to local recovery/sidecar artifacts.

In that case, do not run `br doctor --repair`, `br sync --import-only --rebuild`, or manual JSONL edits without fresh explicit approval.

## Cleanup side effects

Before deleting local recovery or sidecar artifacts, copy `.beads/` to a temp directory.
Test the cleanup and verification sequence there first.
Apply only the minimal proven cleanup to the real repo after confirmation.

When cleaning `.beads/.br_recovery/`, verify in side-effect-aware order:

1. Remove stale recovery artifacts only after approval.
2. Run `br doctor --json`.
3. Inspect non-OK checks, `workspace_health`, and `reliability_audit.anomalies`.
4. Avoid extra `br sync --status` or `br list` calls unless you rerun cleanup or state that they may recreate WAL/recovery artifacts.

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

Before `br sync --import-only`, scan classic beads JSONL for non-integer `comments[].id` values.
If found, ask before mapping legacy string/UUID comment IDs to integers.
Preserve comment text, author, timestamps, and issue IDs.

After `br sync --import-only` fails, stop.
Report the exact error and backup path.
Ask before changing recovery strategy, moving more `.beads/` files, using `--force`/`--rebuild`, editing JSONL, or repairing.

Do not run bare `br sync`; choose an explicit mode.

## Handoff unresolved problems

Before staging `.beads/`, ensure local-only runtime/recovery artifacts are ignored:

```text
beads.db
beads.db-*
*.db-wal
*.db-shm
.write.lock
.br_history/
.br_recovery/
interactions.jsonl
```

If you cannot resolve a beads problem in-session, leave a useful comment or note when a current issue ID is known and br writes still work. Include:

- br version;
- workspace path from `br where`;
- failing command and exact error;
- relevant `br doctor --json` or `br sync --status --json` findings;
- what you did not try because it might mutate data or setup.
