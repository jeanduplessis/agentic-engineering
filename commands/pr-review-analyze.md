---
description: Analyze the review comments on a PR
agent: general
---

## Context

- GitHub PR: !`gh pr view --json url --jq '.url'`
- Code reviewer: `kilo-code-bot`

## Task

Use the gh-pr-review skill with @general to address code-reviewer comments on the PR. Execute steps in order.

### Step 1: Gather prior-run context

Before reading review comments, inspect recent git history to learn what changed and why:

    git log --oneline -10

Read commit messages carefully. MUST NOT undo or contradict prior commits unless a new review comment explicitly requests it.

### Step 2: Read full comment history (context pass)

Fetch ALL comments (resolved and unresolved) to absorb the full conversation, including prior replies explaining fixes and reasons:

    gh pr-review view <pr-url> --reviewer kilo-code-bot

Read-only context. Do NOT act on resolved comments.

### Step 3: Fetch unresolved actionable comments (action pass)

Fetch comments that still need action:

    gh pr-review view <pr-url> --reviewer kilo-code-bot --unresolved --not-outdated

Analyze and fix only these comments. If none, skip to Step 7.

### Step 4: Analyze and fix each unresolved comment

For each unresolved comment:

1. Identify the feedback root cause.
2. Cross-reference the git log (Step 1) and resolved comment history (Step 2) to see whether prior commits already touched this code and why.
3. If feedback is valid and not already addressed, fix it.
4. If feedback conflicts with a prior fix, explain the conflict in your reply instead of blindly reverting the earlier change.

### Step 5: Reply and resolve

For each comment addressed in Step 4:

1. Reply with the applied fix, or why you disagree it is valid.
2. Resolve the thread.

### Step 6: Run KISS agent (changed files only)

Run @kiss to keep code changes simple. Scope it ONLY to files modified while addressing review comments in this run. Do not simplify or refactor other files.

### Step 7: Commit and push

After @kiss completes and all comments are answered and resolved, commit and push.
