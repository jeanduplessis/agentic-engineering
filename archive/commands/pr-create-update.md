---
description: "Create or update a GitHub pull request"
argument-hint: "[draft] [rebase first] [focus/instructions]"
skills:
  - pr-create
---

## Required skills

- `pr-create`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Create or update the current branch's GitHub PR.

User instructions: $ARGUMENTS

Rules:
- Treat arguments as extra intent: draft mode, rebase-first, update/refresh, or reviewer-focus notes.
- If empty, use the default current-branch create/update workflow.
- Follow confirmation rules before pushing, creating, or editing a PR.
