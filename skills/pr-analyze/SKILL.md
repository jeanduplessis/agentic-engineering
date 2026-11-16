---
name: pr-analyze
description: Read-only analysis of a GitHub pull request for logic bugs, missed edge cases, unresolved review threads, PR-body discrepancies, and test-quality gaps; posts a GitHub review only after explicit approval. Runs only when the user explicitly invokes it (for example `/pr-analyze`) with a PR URL or number and optional focus.
disable-model-invocation: true
---

# PR analyze

## Input

Use the text the user gave after the skill name:

- First token: the PR URL or PR number.
- Everything after it: extra focus or instructions; preserve quoted or space-containing text.
- PR target missing or ambiguous: ask one concise clarification and stop.

## Process

### 1. Gather context

- Read repo instructions first.
- Read PR body, metadata, unresolved GitHub review threads (not only PR issue comments), and final combined diff with `gh`.
- For each unresolved thread/comment, state whether you agree and why.
- If the PR touches a `.specs/` domain, read the relevant spec before reviewing.
- For every changed file, read enough current-file/caller/callee context to verify behavior.
- If local files lack PR-head contents, inspect PR-head files read-only with `gh`/GitHub API; do not checkout.

### 2. Analyze through Review focus

- Review the final combined diff, not commits alone.
- Report only issues visible on changed lines.
- Do not report speculative, style-only, or pre-existing issues outside the diff.
- For each changed item below, explicitly check real-world edge states:
  `??`, `||`, fallback/default, duplicate/retry path, webhook, marker, status field, timestamp, queue/lease, cleanup, or finalization path.
- Verify each finding against changed code before reporting.

### 3. Present findings

- Use Output format.
- If no verified issues exist, say “No issues found” and list files reviewed.
- Ask whether to submit a GitHub review: `[Y]es` / `[N]o`.
- Do not post GitHub comments unless the user explicitly answers yes.

### 4. Submit review

- Only submit if the user explicitly answers yes.
- Before posting, first output each PR review comment message and the overall review message.
- Ask how to submit: `[A]pprove`, `[C]omment`, or `[R]equest Changes`.
- Wait for the user's choice.
- Then post one PR review comment per finding on the exact changed line; dedupe existing comments; include warning, trace, and impact.
- If no findings exist, submit only the overall review message; do not add line comments.

## Rules

- Until the user explicitly approves submitting a GitHub review, remain read-only.
- Never edit files, run tests/builds/app code, commit, checkout, rebase, stash, or mutate git state.
- After approval, the only allowed mutation is posting the requested GitHub review.
- If final diff, PR body, unresolved comments, or required context cannot be inspected read-only, say what is blocked and stop.

## Review focus

- Logic flaws, bugs, missed edge cases, unsafe fallback behavior, retry/idempotency issues, and error-handling gaps.
- State-machine/status-transition mistakes and queue/lease/cleanup/finalization races.
- Incorrect assumptions about nullish, empty, duplicate, stale, reordered, or partially failed states.
- PR body/implementation discrepancies.
- Lost, bypassed, duplicated, or incorrectly gated PostHog event tracking.
- Overfitted tests, unnecessary assertions, brittle implementation-detail checks, or tests without meaningful behavior verification.

## Severity

- CRITICAL: likely security issue, data loss, outage, or blocking correctness bug.
- WARNING: concrete bug, broken contract, edge-case failure, or unsafe behavior.
- SUGGESTION: non-blocking test, maintainability, or clarity issue visible on changed lines.

## Output format

1. Summary table: counts by severity: `CRITICAL`, `WARNING`, `SUGGESTION`.
2. Files reviewed.
3. Unresolved review comments checked: agreement and rationale.
4. PR body discrepancies checked.
5. PostHog tracking paths checked.
6. Test quality checked.
7. For each finding, use exactly:

**[SEVERITY]** `path/to/file.ts:line` - Brief description

**Evidence:**
```diff
<relevant changed lines>
```

Trace:
1. <What changed>
2. <What surrounding context/callers/state paths were checked>
3. <Why this is concrete>

Impact: <What breaks; conditions>
