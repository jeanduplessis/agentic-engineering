---
name: example-good
description: Helps agents summarize short project notes when the user asks for a concise status update, key risks, or next actions from local notes.
license: MIT
metadata:
  tags: example, validation
---

# Example Good

When the user provides local project notes and asks for a status update, identify completed work, current risks, and next actions.

## Steps

1. Read the provided notes.
2. Group facts into completed work, risks, and next actions.
3. Ask one clarifying question if the requested audience or time period is unclear.

## Output

Use three headings: `Completed`, `Risks`, and `Next actions`.
