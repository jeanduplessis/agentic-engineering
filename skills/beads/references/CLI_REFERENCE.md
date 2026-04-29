# Beads CLI reference for coding agents

This is a compact runtime reminder. Use `bd <command> --help` for the installed syntax before advanced or unfamiliar commands.

## Global conventions

```bash
bd [global-flags] <command> [command-flags] [arguments]
```

Useful global flags:

| Flag | Use |
| --- | --- |
| `--json` | Machine-readable output; use this for agent workflows when supported |
| `--quiet` | Suppress non-essential output |
| `--verbose` | More diagnostic output |
| `--help` | Command-specific help |
| `--version` / `bd version` | Version information |

## Essential runtime loop

```bash
bd ready --json                  # Unblocked work
bd list --status in_progress --json
bd show <id> --json              # Issue details
bd update <id> --claim --json    # Atomically claim/start
bd update <id> --notes "CURRENT: ... NEXT: ..." --json
bd comment <id> "Handoff or review context" --json
bd close <id> --reason "Completed: ..." --json
```

Do not add backend/session-finalization commands to this loop unless the user explicitly asks for storage or collaboration operations.

## Create issues

```bash
bd create "Title" -t task -p 2 --description "Details" --json
bd create "Fix login" -t bug -p 1 --description "Repro and expected behavior" --json
bd create "Subtask" --parent bd-a3f8e9 -p 2 --json
bd create "Found during work" --deps discovered-from:bd-42 --description "Context" --json
```

Common types: `bug`, `feature`, `task`, `epic`, `chore`, `decision`. Priorities: `0` / `P0` critical through `4` / `P4` backlog.

For long descriptions, prefer a file or stdin when supported by the installed command:

```bash
bd create "Title" --body-file notes.md --json
cat notes.md | bd create "Title" --stdin --json
```

Avoid `bd edit`; it opens an editor and can hang agent runs.

## List and query

```bash
bd ready --json
bd ready --priority 1 --json
bd blocked --json
bd list --status open --json
bd list --status in_progress --json
bd list --priority 0,1 --type bug --json
bd list --label-any urgent,critical --json
bd search "keyword" --json
bd status --json
bd info
```

Prefer `bd ready` over scanning all open issues manually; it applies blocker-aware semantics.

## Update, comment, and close

```bash
bd update bd-42 --claim --json
bd update bd-42 --priority 0 --add-label urgent --json
bd update bd-42 --title "Updated title" --json
bd update bd-42 --description "New description" --json
bd update bd-42 --notes "CURRENT: ... NEXT: ..." --json
bd comment bd-42 "Handoff: backend done; frontend remains" --json
bd comments bd-42 --json
bd close bd-42 --reason "Fixed in PR #123" --json
bd reopen bd-42 --reason "Regression found" --json
```

Use `bd comment <id> ...` or `bd comments add <id> ...`; do not insert an `add` subcommand after singular `comment`.

## Dependencies

```bash
# bd-2 depends on bd-1; bd-1 blocks bd-2
bd dep add bd-2 bd-1 --json

# Soft relationship
bd dep add bd-2 bd-1 --type related --json
bd dep relate bd-42 bd-43 --json

# Inspect graph
bd dep tree bd-2 --json
bd dep list bd-2 --json
bd dep cycles --json
bd blocked --json
bd ready --json
```

Direction trap: the first argument is the blocked/dependent issue; the second is the prerequisite.

## Assignment and labels

```bash
bd update bd-42 --assignee alice --json
bd assign bd-42 alice --json
bd assign bd-42 "" --json                 # unassign
bd update bd-42 --add-label needs-review --json
bd label add bd-42 needs-review --json
bd label remove bd-42 needs-review --json
bd label list bd-42 --json
bd label list-all --json
```

Use assignment and claim state for ownership; use dependencies for ordering; use labels for lightweight classification.

## Diagnostics

```bash
bd info
bd status --json
bd doctor --agent --json
bd doctor --deep --json
```

Ask before running commands that repair, migrate, delete, reinitialize, or change setup.

## Advanced commands to discover with help

Only use these when the task calls for them, and inspect help first:

```bash
bd gate --help       # External waits such as human approval, timers, PRs, CI
bd formula --help    # Workflow formula discovery
bd cook --help       # Compile formula to a proto/template
bd mol --help        # Molecules and wisps from workflow templates
bd setup --help      # Integration/setup only when requested
```
