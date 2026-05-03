---
name: beads
description: >
  Runtime guidance for using beads_rust (`br`) as persistent, dependency-aware task
  memory for coding agents. Use when work may span sessions or context
  compaction, needs blockers/dependencies, ready-work discovery, handoffs,
  multi-agent coordination, or the user asks to create/track/resume tasks.
  Prefer a session-local checklist for simple same-session work.
license: MIT
compatibility: Requires the br CLI in PATH and an existing beads database in the target project. Initialize or change setup only when the user asks.
allowed-tools: Bash(br:*) Read
---

# Beads — durable task memory

Use `br` for project memory that must survive chat loss, handoff, compaction, or parallel work.
Use the session-local checklist for short linear work finishing now.
If simple work branches, blocks, or needs handoff context, promote it to a bead.
Details: [BOUNDARIES.md](references/BOUNDARIES.md).

## First principles

- Treat `br <command> --help` as syntax source of truth.
- Normal issue commands mutate only `.beads/`; `br` does not commit, push, pull, install hooks, or run git.
- Do not initialize, import, repair, migrate, delete, or change setup unless the user asks or approves.
- Do not run bare `br sync`.
- Use `br sync --flush-only` only when asked to export JSONL before committing `.beads/`, after disabled auto-flush, or during approved recovery.
- Use `--json` for reads/writes when available. Avoid interactive/editor flows.

## Core protocol

```bash
br info
br ready --json
br list --status in_progress --json
br show <id> --json
br create "Title" --description "Context..." -t task -p 2 --json
br update <id> --claim --json
br update <id> --notes "CURRENT: ... NEXT: ... DECISIONS: ... VALIDATE: ..." --json
br comments add <id> --message "Handoff or review context" --json
br close <id> --reason "Delivered X; validated with Y; follow-up tracked as Z" --json
```

If `br` is missing or no DB exists, report it and ask before setup.
Claim before substantial edits.
Record durable notes at natural breakpoints, before pausing, when blockers/decisions change, and before close.
Use comments for long narrative handoffs.
Long comments: `br comments add <id> --file handoff.md --json`.
Long descriptions: `--description "$(cat /tmp/body.md)"`.

## Create and relate work

```bash
br create "Found bug in auth" --description "Observed while working on <id>; repro/context..." -t bug -p 1 --deps discovered-from:<id> --json
br create "Implementation slice" --parent <epic-id> -t task -p 2 --json
br dep add <dependent> <dependency> --json
br blocked --json
br dep tree <id> --json
```

`br dep add <dependent> <dependency>` means the dependent waits on the dependency.
Use blocker edges only for real ordering.
Use `--deps discovered-from:<id>` for found work, `--parent <epic-id>` for epic children, and `--type related` for soft links.
Details: [DEPENDENCIES.md](references/DEPENDENCIES.md).

## Troubleshooting boundary

If commands fail or state is unclear, diagnose first:

```bash
br --version
br where
br status --json
br sync --status --json
br doctor --json
```

Ask before repair, migration, deletion, initialization, import, or setup-changing commands.
Do not run bare `br sync`.
Details: [TROUBLESHOOTING.md](references/TROUBLESHOOTING.md).

## Read more only when needed

- More commands: [CLI_REFERENCE.md](references/CLI_REFERENCE.md)
- Durable note quality: [RESUMABILITY.md](references/RESUMABILITY.md)
- Multi-agent claiming, assignment, handoffs: [MULTI_AGENT.md](references/MULTI_AGENT.md)
- Epics, deferred work, saved queries, external waits: [WORKFLOWS.md](references/WORKFLOWS.md)
- Setup/init/import only when requested: [SETUP.md](references/SETUP.md)
