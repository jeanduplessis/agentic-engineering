---
description: "Implement an epic bead through the epic-implement skill workflow"
argument-hint: "<epic-bead-id> [instructions]"
skills:
  - epic-implement
  - beads
---

## Required skills

- `epic-implement`
- `beads`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Implement one existing epic bead using the loaded `epic-implement` skill as the authoritative workflow.

Args: $ARGUMENTS

## Arguments

- First arg = epic bead ID. If missing or ambiguous, ask one concise clarification and stop.
- Rest = orchestration constraints/focus notes to pass through to child gates.
- Work only under the supplied epic. Do not create a replacement epic.

## Workflow

Follow `epic-implement` exactly for setup checks, child gate prompts, gate interpretation, task closure, commits, resume state, final validation/review, epic closure, and failure recovery.

If this command conflicts with `epic-implement`, `epic-implement` wins.
