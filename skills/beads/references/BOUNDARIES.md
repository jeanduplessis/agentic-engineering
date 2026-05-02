# When to use br vs a session-local checklist

Use br for durable project memory. Use the agent/runtime's ordinary in-session checklist for immediate execution steps.

## Decision rule

Ask: "Will this state matter after this chat or for another worker?"

- Yes, probably → create or update a bead.
- No, it will finish now and has no durable value → use a session-local checklist.
- Unsure → start local; promote to br when the work branches, blocks, or needs handoff context.

## Use br for

- Multi-session or compaction-prone work.
- Dependencies/blockers: `br ready`, `br blocked`, and `br dep tree` compute work state.
- Parent/epic task graphs with implementation children.
- Handoff context: notes, comments, acceptance criteria, validation commands.
- Multi-agent work: claims, assignment, comments, labels, and dependencies reduce collisions.
- Follow-up work discovered while implementing another task.
- User requests to track, resume, create tasks, inspect ready work, or preserve state.

## Use a session-local checklist for

- Small linear changes that will finish now.
- Throwaway exploration where no durable decision has been made.
- Private execution steps that future agents do not need.
- Minute-by-minute progress inside one already-tracked bead.

## Promotion pattern

For a durable issue, keep br as source of truth and use the session checklist as a working copy:

1. `br show <id> --json` to load context.
2. `br update <id> --claim --json` before editing.
3. Use a local checklist for immediate steps.
4. At meaningful breakpoints, update br with durable facts: decisions, current state, next step, blockers.
5. Close the bead only when the durable work is actually complete.

Do **not** mirror every checklist item into br. Beads should contain information future agents need, not minute-by-minute execution noise.

## Promote when simple work changes shape

Start with a checklist if work looks simple. Promote to br when you notice any of these:

- The work now has multiple independent slices.
- A blocker requires waiting for a user, PR, CI, credentials, or another task.
- You discover follow-up work that should not derail the current task.
- The context needed to resume is larger than a final user response.
- Another agent/human may work on the same project before this is done.

Example:

```bash
br create "Implement OAuth callback" \
  -t task -p 2 \
  --description "CURRENT: route identified; NEXT: add callback validation and tests; BLOCKED: none." \
  --json
```

## Anti-patterns

- Creating br issues for throwaway one-hour chores.
- Leaving durable decisions only in chat when the task may continue later.
- Creating duplicate markdown TODO files when br already tracks the work.
- Closing a bead without a reason or without recording important follow-up context.
- Using br as a verbose activity log instead of a durable project-memory graph.
