# Multi-agent coordination with br

Use these patterns when more than one agent, branch, or human may touch the same work. Always check installed syntax with `br <command> --help` before unfamiliar coordination commands.

## Claiming and assignment

Claim before editing:

```bash
br update br-42 --claim --json
```

Assign or unassign when coordinating with a named human or agent:

```bash
br update br-42 --assignee agent-a --json
br update br-42 --assignee "" --json
```

Prefer claiming before editing. Assignment communicates ownership; dependencies communicate ordering.

## Handoff to another agent

Leave a durable comment and, when appropriate, assign the issue:

```bash
br comments add br-42 --message "Backend API complete. Needs frontend wiring; see auth/api.go and TestLoginAPI." --json
br update br-42 --add-label needs-frontend --assignee agent-b --json
```

The receiver should inspect and claim before editing:

```bash
br show br-42 --json
br comments list br-42 --json
br update br-42 --claim --json
```

If the work is actually complete, close it and create/assign a separate follow-up issue rather than reusing a closed issue.

## Parallel epic work

Create a parent epic and child tasks:

```bash
br create "Auth System" -t epic -p 1 --json
br create "Backend auth" --parent br-auth -p 1 --json
br create "Frontend auth" --parent br-auth -p 1 --json
br create "Integration tests" --parent br-auth -p 1 --json

br update br-auth.1 --assignee agent-a --json
br update br-auth.2 --assignee agent-b --json
br update br-auth.3 --assignee agent-c --json
br list --status in_progress --json
```

Create a merge/integration bead that depends on all parallel parts:

```bash
br create "Integrate auth parts" -t task -p 1 --parent br-auth --json
br dep add br-integrate br-auth.1 --json
br dep add br-integrate br-auth.2 --json
br dep add br-integrate br-auth.3 --json
br ready --json
```

Only the integration bead becomes ready when all blockers close.

## External waits

For waits on human approval, PRs, CI, credentials, or timers, make the wait explicit instead of pretending work is complete:

- Create a blocking task such as "Human design review for checkout copy".
- Add a comment with the external condition and owner.
- Defer the blocked work if it should not appear ready until later.
- Use labels such as `needs-review`, `waiting-ci`, or `needs-credentials` when helpful.

Example:

```bash
br create "Design review for checkout copy" -t task -p 1 --parent br-checkout --json
br dep add br-checkout-impl br-design-review --json
br comments add br-design-review --message "Needs human approval of checkout copy before implementation proceeds." --json
```

## Collision-avoidance checklist

Before editing shared files:

1. Load context with `br show <id> --json` before acting.
2. Check active claims with `br list --status in_progress --json`.
3. Claim or assign the bead before substantial edits.
4. Write a handoff comment before stopping or reassigning.
5. Create blockers/dependencies for real ordering constraints; do not rely on prose alone.
6. If the tree has unrelated dirty changes, ask before proceeding or document the safe file scope in a comment.
