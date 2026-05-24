---
name: to-issues
description: Breaks a plan, spec, PRD, or ait epic into independently grabbable ait (`ait`) issues using tracer-bullet vertical slices. Use when the user wants to convert a plan into implementation issues, create ait tasks, or break work down into dependency-aware ait issues.
---

# To Issues

Break requirements into independently grabbable `ait` issues using vertical slices (tracer bullets).
Create the resulting work in `ait`, with dependency links that make `ait ready` useful.
When using `ait`, load and follow the `ait-cli` skill.

## Process

### 1. Gather context

Work from whatever is already in the conversation context.

If the user passes an `ait` epic ID, fetch it with:

```bash
ait show <id>
```

If needed, inspect related context:

```bash
ait list
ait ready --grouped
ait show <id>
```

If the source is a local file in the repo, read it directly.
If the source is only in the conversation, use the conversation context.

### 2. Explore the codebase, if useful

If you have not already explored the codebase, do so enough to understand the current state, likely integration points, and testing patterns.

Issue titles and content should use project domain vocabulary from specs, `CONTEXT.md`, or relevant ADRs in `docs/adr/`.
If docs are absent, proceed silently.

### 3. Draft vertical slices

Break the plan into **tracer bullet** issues.
Each issue is a thin vertical slice that cuts through all required integration layers end-to-end, not a horizontal slice of one layer.

Slices may be **HITL** or **AFK**:

- **HITL** slices require human interaction, such as an architectural decision, design review, credential setup, or product approval.
- **AFK** slices can be implemented and validated without human interaction.

Where possible, prefer AFK and put HITL issues at the front of the dependency tree.

<vertical-slice-rules>
- Each slice delivers a narrow but complete path through every required layer.
- A completed slice is independently demoable or verifiable.
- Prefer many thin slices over a few thick ones.
- Dependencies should represent real ordering constraints, not vague relatedness.
- Each issue should include enough context for a future agent to implement it after context compaction.
- Include relevant file paths/function names that will be durable during execution.
</vertical-slice-rules>

### 4. Create the ait issues

If `ait` is not installed or no `.ait/` project exists, ask the user how they want to proceed. Do not silently initialize ait unless the user asked for setup.

Create issues in dependency order: blockers first, then blocked work. Save each created issue ID so dependencies can reference real IDs.

Create each issue from JSON on stdin and pass an actor:

```bash
cat <<'JSON' | ait --actor agent create --stdin
{
  "title": "<slice title>",
  "issue_type": "task",
  "priority": "P2",
  "content": {
    "source": "<plan, spec, PRD, or parent issue ID>",
    "goal": "<concise vertical-slice goal>",
    "context": "<durable context needed after compaction>",
    "what_to_build": "<end-to-end behavior, not layer-by-layer busywork>",
    "acceptance_criteria": [
      {"text": "<observable criterion 1>"},
      {"text": "<observable criterion 2>"}
    ],
    "verification": ["<test or validation command/approach>"],
    "files": [
      {"path": "<durable path>", "reason": "<why it is relevant>"}
    ],
    "agent_notes": [
      "Slice type: AFK or HITL",
      "Priority: P0-P4",
      "Blocked by: <issue-id> — <reason>, or None",
      "Notes for future agents: <decisions, constraints, risks>"
    ]
  }
}
JSON
```

If there is a source PRD/epic issue, link every implementation issue to that epic issue by setting `parent` during creation:

```bash
cat <<'JSON' | ait --actor agent create --stdin
{
  "title": "<slice title>",
  "issue_type": "task",
  "priority": "P2",
  "parent": "<epic-id>",
  "content": {
    "source": "<epic-id>",
    "goal": "<concise vertical-slice goal>",
    "context": "<durable context needed after compaction>",
    "what_to_build": "<end-to-end behavior>",
    "acceptance_criteria": [{"text": "<observable criterion>"}],
    "verification": ["<test or validation approach>"],
    "agent_notes": ["Slice type: AFK or HITL"]
  }
}
JSON
```

After all issues exist, add dependency edges between implementation issues:

```bash
# <dependent> is blocked by <dependency>
ait --actor agent dep add <dependent-id> <dependency-id> --type blocks
```

Use `blocks` dependencies only for true blockers between implementation issues.
Do not use dependency edges just to attach tasks to the epic; use `parent` for that.

### Issue content template

<issue-template>
## Source

Parent/source issue: `<parent-id>` if applicable. Omit if not applicable.
Reference the user stories being implemented.

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer busywork.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Classification

- Slice type: HITL or AFK
- AIT type: task
- Priority: P0-P4

## Blocked by

- `<issue-id>` — reason this blocker must complete first

Or: None — can start immediately.

## Notes for future agents

Durable context needed to resume this issue after compaction: decisions, relevant constraints, testing expectations, and any known risks.
</issue-template>

### 5. Report the created graph

After creation, report:

- The created ait issue IDs and titles
- Which issues are ready immediately
- The dependency edges added
- Any HITL issues requiring user attention
