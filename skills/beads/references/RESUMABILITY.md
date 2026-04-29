# Writing resumable beads

A bead should let a future agent resume without rediscovering the same facts. Write for an agent that has the repository and bd database but not this conversation.

## What to capture

When creating or updating an issue, include:

- **Goal** — what outcome matters.
- **Current state** — what has already been done or verified.
- **Next step** — the single most useful action to resume.
- **Decisions** — tradeoffs and why a path was chosen.
- **Files/commands** — exact paths, tests, scripts, PRs, CI runs, or logs.
- **Blockers** — what is waiting on whom/what.
- **Acceptance** — how to know the issue is done.

## Good note shape

```text
CURRENT: Parser accepts formula templates and creates parent/child beads. Unit tests pass in cmd/bd/formula_test.go.
DECISIONS: Kept formula variables simple to avoid code execution.
BLOCKED: Need product decision on where shared formula files should live.
NEXT: Add integration test that instantiates an example workflow and verifies dependency edges.
VALIDATE: go test ./cmd/bd -run TestFormulaWorkflow
```

## Creating with enough context

```bash
bd create "Add validation errors" \
  -t task -p 2 \
  --description "Goal: make invalid workflow templates explain path + field + suggested fix. Current parser returns generic errors. Validate with malformed examples." \
  --json
```

For long descriptions, use `--body-file` or `--stdin` when supported by the installed command:

```bash
bd create "Document handoff" --body-file handoff.md --json
cat handoff.md | bd create "Document handoff" --stdin --json
```

For long handoffs on an existing issue, comments are often safer than trying to pack everything into one shell argument:

```bash
bd comment bd-42 --file handoff.md --json
cat handoff.md | bd comment bd-42 --stdin --json
```

## Update cadence

Update bd at natural persistence boundaries:

- before compaction/session end;
- before switching to another issue;
- after a major design decision;
- when a blocker appears or clears;
- after discovering linked work;
- before closing.

Do not update bd after every tiny checklist step unless that step changes future resumption context.

## Closing well

A close reason should be useful later:

```bash
bd close bd-42 --reason "Implemented token refresh in auth/session.go; added TestRefreshExpiredToken; follow-up UX polish tracked as bd-91" --json
```

Avoid vague reasons such as `done` when the issue involved significant choices.
