---
description: "Create dependency-aware ait issues from a plan, spec, PRD, or epic using the to-issues workflow"
argument-hint: "[ait epic id | document path | current conversation]"
skills:
  - to-issues
  - ait-cli
---

Create dependency-aware ait issues using the `to-issues` skill as the authoritative workflow.

Source: $ARGUMENTS

## Source resolution

- Empty or `current conversation`: use current conversation context.
- Ait epic ID: inspect it with `ait show <id>` and use its content as the source.
- Document path: read it first; use file contents plus relevant conversation context.
- Missing, unreadable, or ambiguous source: ask one concise clarification and stop.

## Workflow

After resolving the source, follow `to-issues` exactly. If this command conflicts with `to-issues`, `to-issues` wins.
