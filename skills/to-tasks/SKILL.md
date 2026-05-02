---
name: to-tasks
description: Breaks a plan, spec, PRD, or beads task into independently grabbable beads_rust (`br`) tasks using tracer-bullet vertical slices. Use when the user wants to convert a plan into implementation tasks, create br tasks, or break work down into dependency-aware beads.
---

# To Tasks

Break a plan into independently grabbable beads tasks using vertical slices (tracer bullets).
Create the resulting work in `br`, with dependency links that make `br ready` useful.

## Process

### 1. Gather context

Work from whatever is already in the conversation context.

If the user passes a beads task ID, fetch it with:

```bash
br show <id> --json
```

If needed, inspect related context:

```bash
br dep tree <id> --json
br comments list <id> --json
```

If the source is a local file or PRD in the repo, read it directly. If the source is only in the conversation, use the conversation context.

### 2. Explore the codebase, if useful

If you have not already explored the codebase, do so enough to understand the current state, likely integration points, and testing patterns.

Task titles and descriptions should use project domain vocabulary from `CONTEXT.md`.
Respect relevant ADRs in `docs/adr/`.
If docs are absent, proceed silently.

### 3. Draft vertical slices

Break the plan into **tracer bullet** tasks.
Each task is a thin vertical slice that cuts through all required integration layers end-to-end, not a horizontal slice of one layer.

Slices may be **HITL** or **AFK**:

- **HITL** slices require human interaction, such as an architectural decision, design review, credential setup, or product approval.
- **AFK** slices can be implemented and validated without human interaction.

Prefer AFK where possible.

<vertical-slice-rules>
- Each slice delivers a narrow but complete path through every required layer.
- A completed slice is independently demoable or verifiable.
- Prefer many thin slices over a few thick ones.
- Dependencies should represent real ordering constraints, not vague relatedness.
- Each task should include enough context for a future agent to implement it after context compaction.
</vertical-slice-rules>

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Beads type**: usually `task`, `feature`, or `bug`
- **Priority**: 0-4, defaulting to 2 when unclear
- **Blocked by**: which other slices must complete first, if any
- **User stories covered**: which user stories this addresses, if the source material has them
- **Acceptance criteria**: concise checks for completion

Ask the user:

- Does the granularity feel right: too coarse, too fine, or about right?
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are the correct slices marked as HITL and AFK?

Iterate until the user approves the breakdown.

### 5. Create the beads tasks

Use `br`, not GitHub. Do not create tasks in another tracker unless the user explicitly asks.

First verify beads is available and initialized:

```bash
br --version
br info
```

If `br` is not installed or no beads database exists, ask the user how they want to proceed. Do not silently initialize beads unless the user asked for setup.

Create tasks in dependency order: blockers first, then blocked work. Save each created bead ID so dependencies can reference real IDs.

Prefer writing each task body to a temporary file, then passing its contents as the issue description to avoid shell quoting problems:

```bash
br create "<slice title>" -t task -p 2 \
  --description "$(cat /tmp/slice-body.md)" \
  --json
```

Current `br create` does not support `--body-file` or `--stdin` for one issue.

If there is a source PRD/epic bead, link every implementation task to that epic task.
Prefer creating each slice as a child of the epic with `--parent <epic-id>` so the work graph stays attached to the PRD:

```bash
br create "<slice title>" --parent <epic-id> -t task -p 2 \
  --description "$(cat /tmp/slice-body.md)" \
  --json
```

If child creation is not supported by the installed `br`, create the task normally and then add the version-supported parent/provenance relationship.
Check `br dep add --help`; typical fallback patterns are a parent-child relationship or `discovered-from:<epic-id>`:

```bash
br dep add <task-id> <epic-id> --type parent-child --json
# or, if this project uses provenance links instead of parent-child fallback:
br dep add <task-id> <epic-id> --type discovered-from --json
```

After all tasks exist, add dependency edges between implementation tasks:

```bash
# <dependent> is blocked by <dependency>
br dep add <dependent-id> <dependency-id> --json
```

Use default `br dep add` only for true blockers between implementation tasks.
Do not use blocker edges just to attach tasks to the epic.
Use `--parent <epic-id>` or a typed relationship such as `parent-child` / `discovered-from` based on installed CLI support and project convention.

### Task body template

<task-template>
## Source

Parent/source bead: `<parent-id>` if applicable. Omit if not applicable.

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer busywork.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Classification

- Slice type: HITL or AFK
- Beads type: task, feature, bug, epic, or chore
- Priority: 0-4

## Blocked by

- `<bead-id>` — reason this blocker must complete first

Or: None — can start immediately.

## Notes for future agents

Durable context needed to resume this task after compaction: decisions, relevant constraints, testing expectations, and any known risks.
</task-template>

### 6. Report the created graph

After creation, report:

- The created bead IDs and titles
- Which tasks are ready immediately
- The dependency edges added
- Any HITL tasks requiring user attention

Do not run bare `br sync` or generic session-end storage commands. Run `br sync --flush-only` only when project guidance or the user explicitly asks for a final JSONL export before committing `.beads/`.
