# Troubleshooting and recovery

Prefer diagnosis and reversible actions. Ask before destructive repairs, setup changes, database
reinitialization, migration, deletion, or low-level storage operations.

## First diagnostics

```bash
bd --version
bd info
bd status --json
bd doctor --agent --json
```

If a command fails, rerun `bd <command> --help` to confirm the installed version supports the command and flags you planned to use.

## Common problems

- `bd: command not found`: Tell the user bd is not installed; ask before installing.

- No beads database: If the user requested setup, initialize carefully; otherwise ask before changing the
  project.

- Unknown flag/command: Use `bd <command> --help`; beads CLI changes across versions.

- Interactive editor opens: Avoid `bd edit`; cancel if possible and use `bd update` flags.

- Shell quoting breaks text: Use comments, `--body-file`, `--stdin`, or a temporary file where the command
  supports it.

- Ready queue looks wrong: Inspect `bd blocked --json`, `bd dep tree <id> --json`, and `bd dep cycles --json`.

- Database health is unclear: Run `bd doctor --agent --json` and summarize only the relevant findings.

## Doctor and repair

`bd doctor` is the health-check entry point:

```bash
bd doctor --agent --json
bd doctor --deep --json
bd doctor --perf --json
```

Repair modes can mutate project state. Ask the user before running commands with flags such as `--fix`,
`--clean`, `--yes`, `--force`, or migration-specific options. Prefer `--dry-run` when available.

## Setup or initialization problems

If the user asked to set up beads and no database exists:

1. Run `bd init --help` and pick flags supported by the installed CLI.

2. Explain whether setup may write project instruction files, git hook files, or local excludes.

3. Use non-interactive flags only when the user has approved the setup approach.

For existing projects, do not overwrite or reinitialize beads data without explicit confirmation.

## Collaboration/storage problems

Most agent task tracking does not require inspecting storage internals. Only investigate backend or
collaboration state when the user asks or when bd itself reports a storage error that blocks the requested
task.

When reporting such an error, include:

- command run;

- exact error;

- bd version;

- project/database path from `bd info`;

- what you did not try because it might mutate data or setup.

## Handoff after an error

If you cannot resolve a beads problem in-session, leave a useful comment or note in the current issue if
writes still work. If writes do not work, report the diagnostics above in the conversation and avoid
speculative repair.
