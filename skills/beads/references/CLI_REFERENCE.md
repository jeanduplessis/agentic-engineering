# Beads Rust CLI reference for coding agents

Compact runtime reminder. Use `br <command> --help` for installed syntax before advanced or unfamiliar commands.

## Table of contents

- [Global habits](#global-habits)
- [Core workflow](#core-workflow)
- [Create work](#create-work)
- [Find work](#find-work)
- [Update, comment, close](#update-comment-close)
- [Dependencies](#dependencies)
- [Epics and children](#epics-and-children)
- [Assignment and labels](#assignment-and-labels)
- [Sync and diagnostics](#sync-and-diagnostics)
- [Setup hooks for agents](#setup-hooks-for-agents)

## Global habits

```bash
br [global-flags] <command> [command-flags] [arguments]
```

Useful global flags:

| Flag | Use |
|---|---|
| `--json` | Machine-readable output |
| `--actor <name>` | Attribute mutations to an agent/human |
| `--db <path>` | Explicit DB path when autodiscovery is wrong |
| `--no-auto-flush` | Skip automatic JSONL export for one mutation |
| `--allow-stale` | Bypass freshness warning only when you understand it |
| `--version` / `br version` | Version information |

## Core workflow

```bash
br ready --json                         # Unblocked open work
br list --status in_progress --json     # Claimed work
br show <id> --json                     # Issue details; returns an array
br update <id> --claim --json           # Atomically claim/start
br update <id> --notes "CURRENT: ... NEXT: ..." --json
br comments add <id> --message "Handoff or review context" --json
br close <id> --reason "Completed: ..." --json
```

## Create work

```bash
br create "Title" -t task -p 2 --description "Details" --json
br create "Fix login" -t bug -p 1 --description "Repro and expected behavior" --json
br create "Subtask" --parent br-abc123 -t task -p 2 --json
br create "Found during work" --deps discovered-from:br-42 --description "Context" --json
br q "Quick capture"                         # Prints only the new ID
```

For long descriptions, write a temp file and pass its contents:

```bash
br create "Title" --description "$(cat /tmp/notes.md)" --json
```

Current `br create` supports markdown bulk import with `--file`, but not `--body-file` or `--stdin` for one issue.

## Find work

```bash
br ready --json
br ready --priority 1 --json
br ready --parent <epic-id> --recursive --json
br blocked --json
br list --status open --json
br list --status in_progress --json
br list --priority 0 --priority 1 --type bug --json
br list --label-any urgent --label-any critical --json
br search "keyword" --json
br status --json
br info
br where
```

Prefer `br ready` over scanning all open issues manually; it applies blocker-aware semantics.

## Update, comment, close

```bash
br update br-42 --claim --json
br update br-42 --priority 0 --add-label urgent --json
br update br-42 --title "Updated title" --json
br update br-42 --description "New description" --json
br update br-42 --notes "CURRENT: ... NEXT: ..." --json
br comments add br-42 --message "Handoff: backend done; frontend remains" --json
br comments add br-42 --file handoff.md --json
br comments list br-42 --json
br close br-42 --reason "Fixed in PR #123" --json
br reopen br-42 --reason "Regression found" --json
```

Use canonical `br comments add/list`. Avoid legacy singular comment forms in migrated docs.

## Dependencies

```bash
# br-2 depends on br-1; br-1 blocks br-2
br dep add br-2 br-1 --json

# Non-blocking relation where supported by project convention
br dep add br-2 br-1 --type related --json

br dep tree br-2 --json
br dep list br-2 --json
br dep list br-2 --direction up --json       # Dependents
br dep cycles --json
br blocked --json
br ready --json
```

Use default `blocks` edges only for real ordering constraints. Use `--parent <epic-id>` or `--type parent-child` for hierarchy/provenance, not blocker ordering.

## Epics and children

```bash
br create "PRD: Feature" -t epic -p 2 --json
br create "Implement first slice" --parent <epic-id> -t task -p 2 --json
br dep list <epic-id> --direction up --type parent-child --json   # Direct children
br dep tree <epic-id> --direction up --json                       # Descendants
br ready --parent <epic-id> --recursive --json
br epic status --json
br epic close-eligible --dry-run --json
```

`br blocked` has no `--parent` flag; get descendants, run `br blocked --json`, then intersect IDs if you need blocked children under one epic.

## Assignment and labels

```bash
br update br-42 --assignee alice --json
br update br-42 --assignee "" --json              # Unassign
br update br-42 --add-label needs-review --json
br label add br-42 -l needs-review --json
br label remove br-42 -l needs-review --json
br label list br-42 --json
br label list-all --json
```

Use claim/assignment state for ownership, dependencies for ordering, labels for lightweight classification.

## Sync and diagnostics

```bash
br sync --status --json       # Read-only sync state
br sync --flush-only          # Export DB to .beads/issues.jsonl
br sync --import-only         # Import JSONL into DB after pulling/recovery
br doctor --json
br stats --json
br lint --json
```

Do not run bare `br sync`; choose a mode. Ask before running commands that repair, import, merge, delete, reinitialize, or change setup. `br` never runs git; stage/commit `.beads/` only when the user asked for a git workflow.

## Setup hooks for agents

```bash
br init --help
br agents --check
br agents --add --dry-run
br agents --add --force
```

Initialize or edit project instruction files only when the user explicitly asks for setup.
