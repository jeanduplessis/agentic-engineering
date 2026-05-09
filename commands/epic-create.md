---
description: "Create an epic bead from current context or a document using the to-prd workflow"
argument-hint: "[document path | current conversation]"
skills:
  - to-prd
  - beads
---

Create an epic bead via the loaded `to-prd` workflow.

Source: $ARGUMENTS

## Source

- Empty or `current conversation`: use current conversation context.
- Document path: read first; use file contents plus relevant conversation context.
- Missing, unreadable, or ambiguous: ask one concise clarification and stop.

## Workflow

Follow `to-prd` exactly:

1. Gather context from the resolved source. If useful, inspect repo architecture, similar features, test patterns, `CONTEXT.md`, and relevant ADRs.
2. Identify implementation shape; briefly confirm architecture/test choices without a requirements interview.
3. Draft the PRD with the `to-prd` template.
4. After approval, verify beads with `br --version` and `br info`.
5. Create a `br` task from the approved PRD:
   - type: `epic`
   - priority: `2` unless context implies otherwise
   - label: `prd` when supported

Use `br`, not GitHub, unless explicitly requested.
If no beads database exists, ask how to proceed; do not initialize silently.
Do not run bare `br sync`.

## Final

Report the epic bead ID/title and tell the user to attach follow-up implementation tasks to it as parent/source epic.
