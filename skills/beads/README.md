# Beads Agent Skill

Runtime guidance for using [beads](https://github.com/gastownhall/beads) (`bd`) as persistent, dependency-aware task memory from coding agents.

## What this skill helps agents do

- find ready work and blockers;
- create durable issues with useful context;
- claim, update, hand off, and close work;
- preserve state across session boundaries or context compaction;
- coordinate multi-agent work with dependencies, assignment, comments, and gates;
- decide when a session-local checklist is enough instead of durable issue tracking.

## Requirements

- `bd` CLI installed and in `PATH`.
- A beads database initialized in the target project, unless the user explicitly asks to set one up.
- A coding-agent runtime that can run shell commands and read files.

## Current runtime loop

```bash
bd ready --json                  # find unblocked work
bd show <id> --json              # load context
bd update <id> --claim --json    # start atomically
bd update <id> --notes "CURRENT: ... NEXT: ..." --json
bd comment <id> "handoff/review context" --json
bd close <id> --reason "..." --json
```

Use `bd <command> --help` as the final authority for the installed version. Avoid low-level storage commands unless the user explicitly asks for setup, recovery, or collaboration troubleshooting.

## Files

```text
beads/
├── SKILL.md              # Required metadata + runtime instructions
├── README.md             # This runtime overview
└── references/           # Optional runtime references loaded on demand
```
