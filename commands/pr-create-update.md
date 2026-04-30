---
description: "Create or update a GitHub pull request using the pr-create skill"
argument-hint: "[draft] [rebase first] [focus/instructions]"
---

Use `pr-create` to create/update the current branch's GitHub PR.

User instructions: $ARGUMENTS

Rules:
- Pass arguments to `pr-create` as extra intent: draft mode, rebase-first, update/refresh, or reviewer-focus notes.
- If empty, use `pr-create`'s default current-branch create/update workflow.
- Follow `pr-create` confirmation rules before pushing, creating, or editing a PR.
