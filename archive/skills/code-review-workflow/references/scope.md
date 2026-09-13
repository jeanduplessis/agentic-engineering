# Scope Discovery

Discover the set of changed files to review using read-only git commands only.

## Step 1: Inspect Repository State

Run:

```bash
git status --short --untracked-files=all
```

```bash
git diff
```

```bash
git diff --cached
```

## Step 2: Resolve Base Branch

Resolve the base branch dynamically instead of assuming `main` or `master`.
Prefer the remote-tracking ref when available so the review compares against the up-to-date branch tip rather than a stale local branch:

```bash
BASE_BRANCH="$(git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null)"
BASE_BRANCH="${BASE_BRANCH#refs/remotes/origin/}"
BASE_REF=""

if [ -n "$BASE_BRANCH" ] && git show-ref --verify --quiet "refs/remotes/origin/$BASE_BRANCH"; then
  BASE_REF="origin/$BASE_BRANCH"
fi

if [ -z "$BASE_REF" ]; then
  for candidate in main master develop trunk; do
    if git show-ref --verify --quiet "refs/remotes/origin/$candidate"; then
      BASE_BRANCH="$candidate"
      BASE_REF="origin/$candidate"
      break
    fi
    if git show-ref --verify --quiet "refs/heads/$candidate"; then
      BASE_BRANCH="$candidate"
      BASE_REF="$candidate"
      break
    fi
  done
fi
```

If `BASE_REF` is non-empty, inspect branch history and branch diff too:

```bash
git log --oneline "$BASE_REF"..HEAD 2>/dev/null
```

```bash
git diff "$BASE_REF"...HEAD 2>/dev/null
```

## Step 3: Build Candidate Review Scope

Build the candidate review scope as the union of:

- unstaged tracked changes from `git diff`
- staged changes from `git diff --cached`
- untracked files from `git status --short --untracked-files=all`
- branch changes from `git diff "$BASE_REF"...HEAD` when a base ref is available and there are commits ahead

## Step 4: Apply Scope Override

Then apply the optional caller-provided scope override:

- Concrete file or directory paths: keep only matching files from the candidate review scope.
- Natural-language description: inspect the candidate review scope, determine which changed files best match the request, and keep only that subset.
- No override: keep the full candidate review scope.

Rules:

- If both local changes and branch changes exist, review both and de-duplicate overlapping files.
- If no base ref can be determined, state that explicitly and review local tracked and untracked changes only.
- If all sources are empty, report that there is nothing to review.
- If the optional override removes every file from scope, report that no changed files matched the requested scope.

## Step 5: Emit Resolved Review Scope

Output a `Resolved Review Scope` block in this format:

```
## Resolved Review Scope

**Base ref:** <base ref used, or "none">
**Scope note:** <brief explanation of what was included and why>

| File | Status | Sources |
|------|--------|---------|
| path/to/file.ts | modified | unstaged, branch |
| path/to/new.ts | added | staged |
| path/to/old.ts | deleted | branch |
| ... | ... | ... |
```

This block is the contract passed to reviewer sub-agents. They use it instead of re-running scope discovery.
