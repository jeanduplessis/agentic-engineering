---
name: pr-create
description: Create or update a GitHub pull request with a context-rich, structured description. Use when the user asks to "create a PR", "open a pull request", "update the PR", "refresh the PR description", "push this branch to the PR", "submit this branch for review", or "make a PR". Supports optional rebasing on origin/main before pushing. For existing PRs, push the latest code and update the PR description only when current commits make it inaccurate.
---

# PR Create/Update

Create/update a reviewer-focused PR.
Existing PRs: push the branch, keep accurate PR text, and edit the description only when
current commits make it stale, incomplete, misleading, or the user requests a refresh.

## Options

Detect:

- **Draft mode** — "draft PR", "WIP", "not ready for review" → `gh pr create --draft`
- **Rebase first** — "rebase first", "update with main", "rebase on main" → rebase on `origin/main` before pushing
- **Extra focus** — honor added guidance throughout (e.g. "focus summary on auth changes")

If intent is ambiguous, ask once up front, not per option.

## Core rules

Summary:
- Answer **"why does this change exist?"** for human reviewers; the diff answers *what* changed.
- Use conversation history—original request, alternatives, constraints—for motivation.

Format:
- Do NOT follow or inherit from `.github/pull_request_template.md`; this format overrides project PR templates.
- New PRs and rebuilt descriptions use this order: **Summary, Human Verification, Reviewer Notes**.

Existing PRs:
- Do not rewrite for style, phrasing, or template conformance.
- Keep titles unchanged unless the user explicitly asks to change them.

## Workflow

### 1. Collect branch and PR context

Run:

```bash
git status
git branch --show-current
git rev-parse --abbrev-ref HEAD@{upstream} 2>/dev/null | sed 's|origin/||' || echo main
git remote get-url origin
git log origin/main..HEAD --oneline 2>/dev/null || git log main..HEAD --oneline 2>/dev/null || git log HEAD~5..HEAD --oneline
git diff --name-only origin/main...HEAD 2>/dev/null || git diff --name-only main...HEAD 2>/dev/null || git diff --name-only HEAD~5
gh pr view --json number,title,body,url,isDraft,headRefName 2>/dev/null || true
```

Include *all* commits since branch divergence, not just the latest.

### 2. Rebase if requested

If requested:

1. `git fetch origin main`
2. `git rebase origin/main`
3. On conflict:
   - `git rebase --abort`
   - Warn the user and stop
   - Do not create/update the PR until conflicts are resolved manually

### 3. Choose create or update flow

`gh pr view` result:

- PR exists → **update flow**
- No PR → **create flow**

For update flow:

- Push current branch to existing PR.
- Compare current commits, changed files, and conversation context against existing PR title/body.
- Keep title unchanged unless the user explicitly asks.
- Keep body unchanged if it still accurately describes current code.
- Edit body only if current commits make it stale, incomplete, or misleading.
- If unsure whether body is stale, ask before editing.

Treat the body as stale when it:

- Omits material behavior, requirement, or architecture changes now present in branch
- Describes implementation changed or removed by later commits
- Mentions tests, verification, assumptions, or tradeoffs that are no longer true
- Would leave a reviewer with an incorrect understanding of the current PR

### 4. Build title for create flow

Format: `type(scope): <description>` (e.g., `feat(auth): add SSO login`).

Common types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`, `perf`.

Rules:

- <72 characters
- Imperative mood
- No trailing period

### 5. Build or update body

Create flow: generate complete body.
Update flow: preserve accurate user-authored context, issue links, reviewer notes, and verification details.
Update only stale/missing parts. If targeted edits would be confusing, rebuild the body.

#### Summary section

Use:

```markdown
## Summary
[One sentence overview of what this PR does]

### Why this change is needed
[Reasons the change is necessary — the WHY]

### How this is addressed
[What this PR changes/introduces to address the WHY]
```

Guidance:

- Overview: one declarative sentence. No preamble; avoid "This PR…".
- Why: motivation, problem, need, and non-obvious tradeoffs.
- How: behavior/outcome changes, not a file-by-file recap; use bullets for multiple changes.
- Link related issues after "How this is addressed" when applicable (`Closes #123`, `Relates to #456`).
- Use short sentences, plain words, and bullets for scannability.
- Never start bullets with filenames; lead with changed behavior or outcome.
- Put technical implementation details in Reviewer Notes.

#### Human Verification

`## Human Verification` rules:

- Prefill only verification completed in this session.
- Do NOT include lint, format, or typecheck; CI confirms these.
- Include only relevant in-session items: spec alignment, tests verified, code evaluations, browser evaluations.
- Update flow: preserve accurate existing verification; revise only text no longer true or newly relevant.
- If manual testing was performed, summarize it in `<details>`; otherwise omit the block.

#### Reviewer Notes

`## Reviewer Notes`: include `### Human Reviewer Flags` bullets for human-judgment items only:

- Spec introductions or changes
- Architectural changes or deviations
- Trade-off decisions

If none apply, write: "No notable items for human review beyond what the summary covers."

Include `### Code Reviewer Agent` only when technical notes add value beyond the Summary; wrap in collapsed details:

```markdown
### Code Reviewer Agent
<details>
<summary>Code Reviewer Notes</summary>

- ...bullet points...

</details>
```

Focus on technical implementation, followed specs/requirements, and decisions/tradeoffs; use bullets, not paragraphs.

Update flow: preserve accurate reviewer notes; revise only for material new commits, stale guidance, or user-requested focus areas.

### 6. Confirm

For create flow:

- Print the generated title and body.
- Ask for confirmation and edits.
- Apply edits and show final version before writing to GitHub.

For update flow:

- Print the existing PR URL.
- State whether the description is accurate or stale.
- If updating the body, show the proposed final body or a concise before/after diff.
- If not updating the body, say workflow will push code only.
- Ask for confirmation before editing GitHub.

### 7. Push and create/update PR

Push first:

```bash
git push origin <current-branch>
```

Use `--force-with-lease` after rebase.

Then choose one path:

- **Accurate existing PR**: do not edit the description; return PR URL.
- **Stale existing PR**: write approved body to a temp file, run `gh pr edit <number-or-url> --body-file <file>`, then return PR URL.
- **Draft new PR**: run `gh pr create --draft --title <title> --body-file <file>`, then return PR URL.
- **Ready new PR**: run `gh pr create --title <title> --body-file <file>`, then return PR URL.

## Checklist

- Existing PR detected; current branch pushed
- Accurate description unchanged; stale description updated only after confirmation
- New PR title: `type(scope): <description>`, <72 chars, imperative, no trailing period
- Generated/rebuilt body: Summary, Human Verification, Reviewer Notes
- Omit Code Reviewer Agent when unnecessary
- No `.github/pull_request_template.md` content
