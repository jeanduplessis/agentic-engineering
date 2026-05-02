---
name: gh-pr-review
description: Read and respond to GitHub PR review comments. Use this skill when working with pull request reviews, replying to review threads, resolving review comments, or checking unresolved feedback on a PR.
---

# gh-pr-review

GitHub CLI extension for reading/responding to PR review comments. Outputs structured JSON for coding-agent workflows.

## Installation

```bash
gh extension install jeanduplessis/gh-pr-review
```

## Commands

### View reviews

```bash
gh pr-review view [<pr-url>] [-R owner/repo] [--pr <number>] [--reviewer <login>] [--states <APPROVED|CHANGES_REQUESTED|COMMENTED|DISMISSED>] [--unresolved] [--not-outdated] [--tail <n>]
```

Returns `ReviewReport` with reviews, inline comments, and thread replies.

### Reply to a thread

```bash
gh pr-review reply [<pr-url>] [-R owner/repo] [--pr <number>] --thread-id <PRRT_...> --body <text>
```

Posts a thread reply. Returns `{ "comment_node_id": "PRRC_..." }`.

### List threads

```bash
gh pr-review threads [<pr-url>] [-R owner/repo] [--pr <number>] [--unresolved]
```

Returns `ThreadSummary[]`.

### Resolve a thread

```bash
gh pr-review resolve [<pr-url>] [-R owner/repo] [--pr <number>] --thread-id <PRRT_...>
```

Resolves a thread. Returns `{ "thread_node_id": "PRRT_...", "is_resolved": true }`.

### Unresolve a thread

```bash
gh pr-review unresolve [<pr-url>] [-R owner/repo] [--pr <number>] --thread-id <PRRT_...>
```

Unresolves a thread. Returns `{ "thread_node_id": "PRRT_...", "is_resolved": false }`.

## Workflow: address PR feedback

1. View all comments: `gh pr-review view --pr 42`
2. Focus actionable feedback: `gh pr-review view --pr 42 --unresolved --not-outdated`
3. Filter reviewer: `gh pr-review view --pr 42 --reviewer octocat`
4. List unresolved threads: `gh pr-review threads --pr 42 --unresolved`
5. Reply after fixing: `gh pr-review reply --pr 42 --thread-id PRRT_... --body "Fixed in latest commit"`
6. Resolve addressed threads: `gh pr-review resolve --pr 42 --thread-id PRRT_...`

## Best practices

- Use `--unresolved --not-outdated` for actionable feedback.
- Use `--tail 3` for recent discussion in long threads.
- After code changes, reply explaining what changed.
- Resolve only after addressing feedback.
- Use `--states CHANGES_REQUESTED` to prioritize blocking reviews.

## Output

Commands write JSON to stdout. Errors write `{ "error": "message" }` to stderr and exit 1.
