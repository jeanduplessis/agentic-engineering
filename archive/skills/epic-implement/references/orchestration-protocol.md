# Orchestration Protocol

## Gate execution

Run every gate to completion in workflow order. Use native subagents first when the current harness exposes them, then the current harness's non-interactive runner, then sequential current-session execution as the required fallback. Pi self-invocation is optional acceleration, never a dependency.

Current-session fallback must preserve the same gate prompt, permissions, output footer, and parent interpretation. Return to the parent role before closure, staging, or commits. Do not parallelize gates sharing a worktree or depending on earlier output. Record each gate's execution method and output path.

## Queue

Refresh before each task:

```bash
br dep tree <epic-id> --direction up --json
br ready --parent <epic-id> --recursive --json
br blocked --json
```

Select only:

- descendants under the epic;
- concrete tasks/bugs;
- open;
- ready;
- unblocked;
- not deferred.

Skip already closed descendants.

If no ready task exists and open descendants remain, stop and report blockers.

## Closure

Only the parent closes tasks.

Close a task only after:

1. implementation gate PASS;
2. validation gate PASS;
3. review gate PASS;
4. post-review validation PASS if review changed the diff.

If a gate executor closes a task that was open when selected, stop and report inconsistent state.

## Commits

Because the worktree starts clean, stage only paths changed during the task plus relevant bead state.

Do not use `git add .` unless every changed path has been inspected and belongs to the task.

Required checks:

```bash
git status --short
git diff --name-status
git diff --cached --name-status
```

Commit format:

```bash
git commit -m "<task-id>: <task title>"
```

Require clean worktree after each task commit.

## Final epic pass

After all descendant tasks close:

1. Run read-only final epic validation.
2. Run full code review over the branch diff/current changes.
3. Rerun epic validation if final review changed the diff.
4. Close the epic only after final gates pass.
5. Commit final bead/review changes if any.
