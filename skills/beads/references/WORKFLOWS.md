# Advanced runtime workflows with br

Use this file when the user asks for reusable workflows, multi-step templates, temporary operational plans, or async waits. Command names and flags vary across releases; run `br <command> --help` before invoking unfamiliar commands.

## Epics as reusable work graphs

Use epics when a workflow should persist as a graph of implementation slices:

```bash
br create "Release checkout v2" -t epic -p 1 --description "Goal, constraints, and acceptance summary" --json
br create "Tracer bullet checkout path" --parent <epic-id> -t task -p 1 --json
br create "Payment failure path" --parent <epic-id> -t task -p 2 --json
br dep add <payment-failure-id> <tracer-bullet-id> --json
br ready --parent <epic-id> --recursive --json
```

Prefer several thin, independently verifiable child tasks over one large opaque task.

## Temporary operational plans

For same-session orchestration that has no future value, use a local checklist. Promote to br only when the workflow needs handoff, dependencies, blockers, or durable audit context.

When promoting, capture current state:

```bash
br create "Operational follow-up: stabilize import" \
  -t task -p 2 \
  --description "CURRENT: import repro captured. NEXT: isolate failure and add regression test. VALIDATE: cargo test import_repro." \
  --json
```

## External waits

br has no gate command. Represent external waits explicitly:

- Create a blocking task for human approval, CI, PR review, credentials, or timer waits.
- Add labels such as `needs-review`, `waiting-ci`, or `needs-credentials`.
- Add a comment with owner, expected condition, and next step.
- Use `br defer` if the task should be hidden from ready work until a later date.

```bash
br create "Human approval: checkout copy" -t task -p 1 --parent <epic-id> --json
br dep add <implementation-id> <approval-id> --json
br comments add <approval-id> --message "Needs product approval before implementation continues." --json
br update <implementation-id> --add-label waiting-approval --json
```

## Defer and undefer

Use defer/undefer for time-based readiness, not for dependency semantics:

```bash
br defer <id> --until tomorrow --json
br undefer <id> --json
br ready --include-deferred --json
```

Check installed syntax with `br defer --help` and `br undefer --help`.

## Saved queries

Use saved queries when a project repeatedly needs the same filtered work view:

```bash
br query --help
br query list --json
```

Do not invent query schemas from memory; inspect `br query --help` first.

## Choosing a workflow tool

| Need | Use |
|---|---|
| Durable multi-task feature plan | Epic + child tasks + dependencies |
| One-off same-session plan | Session-local checklist |
| External wait | Blocking task/comment/label/defer |
| Repeated filtered work view | Saved query if supported |
| Assign work across agents | Claim/assignment/comments/dependencies |

## Cleanup

Before ending a durable workflow session:

- leave notes/comments with current state and next action;
- create normal beads for deferred follow-up using `discovered-from` or `--parent`;
- do not close incomplete work;
- run `br sync --flush-only` only when the user/project asked for a final JSONL export before committing `.beads/`.
