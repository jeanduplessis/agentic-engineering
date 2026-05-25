# Orchestration Protocol

## Queue

Refresh before each issue:

```bash
ait show <epic-id>
ait list --parent <epic-id>
ait ready --grouped
ait list --lane Blocked
```

Select only:

- descendants under the epic;
- concrete executable task/bug/chore issues, not the epic/container itself;
- open or in-progress when already claimed by this orchestration run;
- ready/unblocked;
- not deferred or explicitly HITL unless the user authorizes HITL work.

Skip already closed descendants.

If no ready issue exists and open descendants remain, stop and report blockers from `ait show`, `ait list --parent <epic-id>`, `ait ready --grouped`, and `ait list --lane Blocked`.

## Lifecycle and closure

Only the parent mutates lifecycle state by default.

Parent may claim a selected issue before implementation:

```bash
ait --actor agent claim <issue-id>
```

Close an issue only after:

1. implementation gate PASS;
2. validation gate PASS;
3. review gate PASS;
4. post-review validation PASS if review changed the diff;
5. all satisfied acceptance criteria are marked done when ait schema/content requires it.

Use `ait update` with JSON Patch to mark acceptance criteria or agent notes. Use `test` before `replace` when avoiding lost updates.

```bash
cat <<'JSON' | ait --actor agent update <issue-id> --stdin
[
  {"op":"test","path":"/content/acceptance_criteria/0/done","value":false},
  {"op":"replace","path":"/content/acceptance_criteria/0/done","value":true}
]
JSON
```

Close with a concrete reason:

```bash
ait --actor agent close <issue-id> --reason "Delivered <summary>; validated with <commands>."
```

If a child closes or mutates an issue that was open when selected, stop and report inconsistent state.

If close fails with `close_incomplete_acceptance_criteria` or `close_open_children`, finish or update the listed blockers; do not force-close without explicit user approval.

## Commits

Because the worktree starts clean, stage only paths changed during the issue plus ait state files produced by CLI mutation/export when needed.

Do not use `git add .` unless every changed path has been inspected and belongs to the issue.

Required checks:

```bash
git status --short
git diff --name-status
git diff --cached --name-status
```

Commit format:

```bash
git commit -m "<issue-id>: <issue title>"
```

Require clean worktree after each issue commit.

## Final epic pass

After all descendant issues close:

1. Run read-only final epic validation.
2. Run full code review over the branch diff/current changes.
3. Rerun epic validation if final review changed the diff.
4. Mark epic acceptance criteria done when needed.
5. Close the epic only after final gates pass.
6. Run `ait check`.
7. Commit final ait/review changes if any.
