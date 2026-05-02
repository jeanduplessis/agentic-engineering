# Beads Agent Skill

Runtime guidance for using [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`) as persistent, dependency-aware task memory from coding agents.

Use this skill to:

- decide when durable beads tracking is worth it;
- inspect and claim ready work;
- write resumable task notes and comments;
- create follow-up tasks and dependency edges;
- coordinate multi-agent work with dependencies, assignment, comments, and labels;
- avoid unsafe setup, sync, or recovery operations unless the user explicitly asks.

## Requirements

- `br` CLI installed and in `PATH`.
- A beads database initialized in the target project, unless the user explicitly asks to set one up.

## Essential commands

```bash
br ready --json                         # find unblocked work
br show <id> --json                     # load context
br update <id> --claim --json           # start atomically
br update <id> --notes "CURRENT: ... NEXT: ..." --json
br comments add <id> --message "handoff/review context" --json
br close <id> --reason "..." --json
br sync --flush-only                    # explicit final JSONL export when committing .beads/
```

Use `br <command> --help` as the final authority for the installed version. Avoid setup, import, repair, merge, and delete commands unless the user explicitly asks for setup, recovery, or collaboration troubleshooting.

## Files

```text
beads/
  SKILL.md
  README.md
  references/
    CLI_REFERENCE.md
    BOUNDARIES.md
    DEPENDENCIES.md
    MULTI_AGENT.md
    RESUMABILITY.md
    SETUP.md
    TROUBLESHOOTING.md
    WORKFLOWS.md
```
