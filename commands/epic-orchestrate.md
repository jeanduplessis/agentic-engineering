---
description: "Implement an ait epic through the epic-orchestrate skill workflow"
argument-hint: "<ait-epic-id> [instructions]"
skills:
  - epic-orchestrate
  - ait-cli
---

Implement one existing ait epic using the loaded `epic-orchestrate` skill as the authoritative workflow.

Args: $ARGUMENTS

## Arguments

- First arg = ait epic ID. If missing or ambiguous, ask one concise clarification and stop.
- Rest = orchestration constraints/focus notes to pass through to child gates.
- Work only under the supplied epic. Do not create a replacement epic.

## Workflow

Follow `epic-orchestrate` exactly for setup checks, child gate prompts, gate interpretation, issue closure, commits, resume state, final validation/review, epic closure, and failure recovery.

If this command conflicts with `epic-orchestrate`, `epic-orchestrate` wins.
