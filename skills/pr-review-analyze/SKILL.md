---
name: pr-review-analyze
description: Address unresolved review comments from selected automated reviewers on a GitHub pull request, then fix, reply, resolve threads, self-review, commit, and push. Runs only when the user explicitly invokes it (for example `/pr-review-analyze`), optionally with a PR URL; never acts on human comments implicitly.
disable-model-invocation: true
---

# PR review analyze

## Required skill

Load and follow the `gh-pr-review` skill before continuing; reuse it if already loaded. If it is unavailable, stop and report it.

## Context

- PR: the URL the user gave after the skill name.
- Review scope: selected automated review authors only.

If the user gave no PR URL, run this command to resolve the current branch's PR URL:

```bash
gh pr view --json url --jq '.url'
```

If the PR URL is absent or ambiguous after resolution, ask one concise clarification and stop.

## Task

Address PR comments from the selected automated review authors. Execute steps in order. Never expand the action scope to all reviewers or human comments implicitly.

### Step 1: Gather prior-run context

Before reading review comments, inspect recent git history for prior changes and rationale:

    git log --oneline -10

Read commit messages carefully. MUST NOT undo or contradict prior commits unless a new review comment explicitly requests it.

### Step 2: Select reviewers and read full history (context pass)

Discover review authors with a read-only `gh pr-review view <pr-url>` call. Identify the automated review accounts relevant to this task from author identities and review context; do not assume every author is a bot. Use authors explicitly selected by the user, or present the candidate logins and ask the user to confirm before taking action. If no relevant automated author is found or identity is unclear, report that and stop.

Keep the confirmed login set fixed for this run. Run the following filtered commands once per selected login; unfiltered discovery is context only, not permission to act on human comments.

Fetch ALL selected-reviewer comments (resolved and unresolved) to absorb the full conversation, including prior replies explaining fixes and rationale:

    gh pr-review view <pr-url> --reviewer <selected-login>

Read-only context. Do NOT act on resolved comments.

### Step 3: Fetch unresolved actionable comments (action pass)

Fetch comments needing action from each selected author only:

    gh pr-review view <pr-url> --reviewer <selected-login> --unresolved --not-outdated

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
