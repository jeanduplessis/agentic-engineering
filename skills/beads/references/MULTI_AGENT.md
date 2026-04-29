# Multi-agent coordination

Use these patterns when more than one agent, branch, or human may touch the same work. Always check installed syntax with `bd <command> --help` before using unfamiliar coordination commands.

## Claiming and assignment

Claim the issue you are about to work on:

```bash
bd update bd-42 --claim --json
```

Assign or unassign when coordinating with a named human or agent:

```bash
bd update bd-42 --assignee agent-a --json
bd assign bd-42 agent-a --json
bd assign bd-42 "" --json
```

Prefer claiming before editing. Assignment communicates ownership; dependencies communicate ordering.

## Handoffs

Sequential handoff:

```bash
# Agent A
bd comment bd-42 "Backend API complete. Needs frontend wiring; see auth/api.go and TestLoginAPI." --json
bd update bd-42 --add-label needs-frontend --json
bd assign bd-42 agent-b --json

# Agent B
bd show bd-42 --json
bd update bd-42 --claim --json
```

If the work is actually complete, close it and create/assign a separate follow-up issue rather than reusing a closed issue.

## Parallel work

Split an epic into child issues or dependency layers:

```bash
bd create "Auth System" -t epic -p 1 --json
bd create "Backend auth" --parent bd-auth -p 1 --json
bd create "Frontend auth" --parent bd-auth -p 1 --json
bd create "Integration tests" --parent bd-auth -p 1 --json

bd assign bd-auth.1 agent-a --json
bd assign bd-auth.2 agent-b --json
bd assign bd-auth.3 agent-c --json
bd list --status in_progress --json
```

## Fan-out / fan-in

Create a merge/integration bead that depends on all parallel parts:

```bash
bd create "Integrate auth parts" -t task -p 1 --json
bd dep add bd-integrate bd-auth.1 --json
bd dep add bd-integrate bd-auth.2 --json
bd dep add bd-integrate bd-auth.3 --json
bd ready --json
```

Only the integration bead becomes ready when all blockers close.

## External waits

For waits on human approval, PRs, CI, or timers, use gates if supported by the installed version:

```bash
bd gate --help
bd gate create --help
bd gate create --type=human --blocks bd-42 --reason="Need design review" --json
bd gate resolve <gate-id> --json
```

Use gates for real external waits rather than pretending work is complete.

## Communication channels

- **Comments** for handoff narratives and review notes.
- **Notes** for compact current-state summaries.
- **Labels** for lightweight states (`needs-review`, `blocked`, `frontend`, `urgent`).
- **Dependencies** for true ordering constraints.
- **Claim/assignment state** for ownership.

## Coordination hygiene

1. Load context with `bd show <id> --json` before acting.
2. Claim before editing.
3. Write a handoff comment before stopping or reassigning.
4. Link discovered work with `discovered-from`.
5. Do not silently close or supersede another agent's work; comment and link the replacement.
6. Avoid unsupported coordination commands from memory; verify with help before use.
