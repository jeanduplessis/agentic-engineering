# When to use bd vs a session-local checklist

Use bd for durable project memory. Use the agent/runtime's ordinary in-session checklist for immediate execution steps.

## Core test

Ask: **Will another agent, or this agent after compaction, need this context later?**

- Yes, probably → create or update a bead.
- No, this will finish in the current session and is linear → use a session-local checklist.

## Use bd for

| Situation | Why bd helps |
| --- | --- |
| Multi-session features or investigations | Issues persist after context loss |
| Dependencies/blockers | `bd ready` and `bd blocked` compute work state |
| Handoffs | Notes/comments preserve decisions and next steps |
| Multi-agent work | Claims, assignment, comments, and dependencies reduce collisions |
| Discovered side quests | `discovered-from` keeps provenance without derailing current work |
| Project memory | History survives beyond conversation scrollback |
| Fuzzy knowledge work | Description, design, acceptance, notes, and comments can evolve |

## Use a session-local checklist for

| Situation | Why a local checklist is better |
| --- | --- |
| Same-session implementation with clear steps | Less overhead |
| User wants visible progress in the chat | Checklist is immediate and lightweight |
| No future context is needed | Durable storage adds noise |
| Linear validation/build steps | Steps are transient and predictable |

## Hybrid pattern

For a durable issue, keep bd as the source of truth and use the session checklist as a working copy:

1. `bd show <id> --json` to load context.
2. Build a short local checklist from acceptance criteria and notes.
3. Work through the checklist.
4. At meaningful breakpoints, update bd with durable facts: decisions, current state, next step, blockers.
5. Close the bead only when the durable work is actually complete.

Do **not** mirror every checklist item into bd. Beads should contain information future agents need, not minute-by-minute execution noise.

## Transition point

Start with a checklist if work looks simple. Promote to bd when you notice any of these:

- You create more than a few nested/branching steps.
- You need to pause for human input, CI, PR review, or another task.
- You discover related work that should not interrupt the current flow.
- The session may end before completion.
- You make a decision that future agents must understand.

Promotion example:

```bash
bd create "Implement OAuth callback" \
  --description "Started as local checklist. Current state: routes added; token exchange untested. NEXT: add integration test and handle refresh-token errors." \
  -t feature -p 1 --json
```

## Anti-patterns

- Creating bd issues for throwaway one-hour chores.
- Keeping durable work only in conversation or a volatile checklist.
- Creating duplicate markdown TODO files when bd already tracks the work.
- Closing a bead without a reason or without recording important follow-up context.
- Using bd as a verbose activity log instead of a durable project-memory graph.
