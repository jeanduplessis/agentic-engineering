---
description: "Create an epic bead from current context or a document using the to-prd workflow"
argument-hint: "[document path | current conversation]"
skills:
  - to-prd
  - beads
---

Create an epic bead using the loaded `to-prd` skill as the authoritative workflow.

Source: $ARGUMENTS

## Source resolution

- Empty or `current conversation`: use current conversation context.
- Document path: read it first; use file contents plus relevant conversation context.
- Missing, unreadable, or ambiguous source: ask one concise clarification and stop.

## Workflow

After resolving the source, follow `to-prd` exactly. If this command conflicts with `to-prd`, `to-prd` wins.
