---
description: "Create an ait epic from current context or a document using the to-epic workflow"
argument-hint: "[--with-issues] [document path | current conversation]"
skills:
  - to-epic
  - to-issues
  - ait-cli
---

Create an ait epic using the `to-epic` skill as the authoritative workflow.

Arguments: $ARGUMENTS

Optional flags:

- `--with-issues` or `--create-issues`: after creating the epic, automatically create dependency-aware implementation issues for it using `to-issues`.

## Source resolution

- Ignore `--with-issues` / `--create-issues` when determining the source.
- Empty or `current conversation`: use current conversation context.
- Document path: read it first; use file contents plus relevant conversation context.
- Missing, unreadable, or ambiguous source: ask one concise clarification and stop.

## Workflow

After resolving the source, follow `to-epic` exactly. If this command conflicts with `to-epic`, `to-epic` wins.

If `--with-issues` or `--create-issues` is present and the epic is created successfully:

1. Use the created ait epic ID as the source/parent for issue creation.
2. Follow `to-issues` exactly to draft and create the implementation issue graph.
3. Report the epic ID, created issue IDs, ready issues, dependencies, and HITL issues.

If epic creation fails, do not create issues; report the failure and next safe action.
