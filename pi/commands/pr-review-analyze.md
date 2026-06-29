---
description: "Analyze the review comments on a PR"
argument-hint: "[PR URL]"
skills:
  - gh-pr-review
---

## Required skills

- `gh-pr-review`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

## Context

- GitHub PR argument: $ARGUMENTS
- Code reviewer: `kilo-code-bot`

If no PR URL is supplied, run this command to resolve the current branch's PR URL:

```bash
gh pr view --json url --jq '.url'
```

If the PR URL is absent or ambiguous after resolution, ask one concise clarification and stop.

## Task

Address code-reviewer PR comments. Execute steps in order.

### Step 1: Gather prior-run context

Before reading review comments, inspect recent git history for prior changes and rationale:

    git log --oneline -10

Read commit messages carefully. MUST NOT undo or contradict prior commits unless a new review comment explicitly requests it.

### Step 2: Read full comment history (context pass)

Fetch ALL comments (resolved and unresolved) to absorb the full conversation, including prior replies explaining fixes and rationale:

    gh pr-review view <pr-url> --reviewer kilo-code-bot

Read-only context. Do NOT act on resolved comments.

### Step 3: Fetch unresolved actionable comments (action pass)

Fetch comments needing action:

    gh pr-review view <pr-url> --reviewer kilo-code-bot --unresolved --not-outdated

Analyze and fix only these comments. If none, skip to Step 7.

### Step 4: Analyze and fix each unresolved comment

For each unresolved comment:

1. Identify the feedback root cause.
2. Cross-reference git log (Step 1) and resolved comment history (Step 2) to see whether prior commits already touched this code and why.
3. If valid and unaddressed, fix it.
4. If feedback conflicts with a prior fix, explain the conflict in your reply instead of blindly reverting the earlier change.

### Step 5: Reply and resolve

For each comment addressed in Step 4:

1. Reply with applied fix or why you disagree it is valid.
2. Resolve the thread.

### Step 6: Self-review implementation

Before committing, self-review for correctness, simplicity, alignment with addressed review comments, and regressions introduced by the changes. Fix issues found.

### Step 7: Commit and push

After self-review completes and all comments are answered and resolved, commit and push.
