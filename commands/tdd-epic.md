---
description: "Implement an epic bead's child tasks in dependency order using TDD"
argument-hint: "<epic-bead-id> [instructions]"
skill: tdd
---

Orchestrate TDD for an epic bead and descendants with `br`.

Arguments: $ARGUMENTS

## Arguments

- First arg must be the epic bead ID. If missing/ambiguous, ask one concise clarification and stop.
- Treat remaining args as implementation constraints/focus notes.
- Do not create an epic; work only under the supplied epic.

## Skills

Load and follow `beads` and `tdd`.

## 1. Verify and inspect

Run:

```bash
br --version
br info
br show <epic-id> --json
br dep list <epic-id> --direction up --type parent-child --json
br dep tree <epic-id> --direction up --json
br ready --parent <epic-id> --recursive --json
br blocked --json
```

If `br` is unavailable, no beads database exists, or the epic ID is invalid, report and ask before changing setup.

Confirm bead is an epic or parent/container.
Get direct children from `br dep list ... --direction up --type parent-child`.
If no children, report no subtasks and stop.

## 2. Queue

Use `br` as ordering source:

- Scope: descendant tasks under the epic, excluding closed children.
- Prefer `br ready --parent <epic-id> --recursive --json`; ready = open, unblocked, not deferred.
- Sort ready work by priority, dependency order, then oldest created.
- Never start a child with unclosed blockers.
- If no child is ready and open children remain:
  - run `br blocked --json`;
  - intersect blocked IDs with epic descendants from `br dep tree <epic-id> --direction up --json`;
  - report blocked children and stop.

Before coding, add orchestration context comment:

```bash
br comments add <epic-id> --message "ORCHESTRATION: starting TDD pass. READY: <ids>. BLOCKED: <ids>. NOTES: <user constraints>." --json
```

## 3. TDD child loop

Repeat until every descendant child is closed or all remaining work is blocked:

1. Refresh state:
   ```bash
   br dep tree <epic-id> --direction up --json
   br ready --parent <epic-id> --recursive --json
   br blocked --json
   ```
2. Pick next ready child by queue rules.

3. Inspect and claim:
   ```bash
   br show <child-id> --json
   br update <child-id> --claim --json
   ```
4. Implement with `tdd`:

   - Derive public interface and test behavior from bead description, acceptance criteria, project docs, and codebase.
   - If behavior/interface is ambiguous, ask before implementing that child.
   - Write one behavior test; verify expected failure.
   - Implement the smallest passing change.
   - Repeat one vertical slice at a time; do not write all tests upfront.
   - Refactor only while green.
   - After each slice, run relevant tests; before closure, run appropriate broader validation.

5. At meaningful slice boundaries, update notes:

   ```bash
   br update <child-id> \
     --notes "CURRENT: <red/green state>. TEST: <test/validation>. NEXT: <next behavior or done>. DECISIONS: <important choices>." \
     --json
   ```

6. If new work appears, do not derail; create a follow-up child linked to the current child:

   ```bash
   br create "Found while TDD: <short title>" \
     -t task -p 2 --parent <epic-id> \
     --deps discovered-from:<child-id> \
     --description "Observed while implementing <child-id>: <context, expected behavior, and why it is deferred>." \
     --json
   ```

7. Close the child only when acceptance criteria are met and validation passes:

   ```bash
   br close <child-id> \
     --reason "Delivered with TDD. Tests/validation: <commands>. Key files: <paths>." \
     --json
   ```

8. Append epic progress as a comment:

   ```bash
   br comments add <epic-id> \
     --message "PROGRESS: closed <child-id>. VALIDATION: <commands>. NEXT READY: <ids>. BLOCKED: <ids>." \
     --json
   ```

## 4. Blockers and failures

- Test needs scope change to turn green: record the red state in child notes and stop.
- Missing requirements, external dependency, or unrelated failing test: record the blocker. Continue only if another child is ready.
- Unrelated validation failure: record the failure and create a `discovered-from:<child-id>` follow-up unless project guidance says fix it now.
- Do not close:
  - a child with failing relevant tests;
  - the epic while any child remains open, blocked, deferred, or in progress.

## 5. Finish the epic

When no open descendants remain, run final relevant validation for the whole epic.

Inspect completion state:

```bash
br dep tree <epic-id> --direction up --json
br epic status --json
br epic close-eligible --dry-run --json
```

Close the epic only if `br` reports it eligible or all children are closed:

```bash
br close <epic-id> --reason "Implemented all child tasks with TDD. Final validation: <commands>." --json
```

Sync guardrail:

- Do not run bare `br sync`.
- Run `br sync --flush-only` only when asked for final JSONL export before committing `.beads/`.

## 6. Final response

Report:

- Epic ID and title.
- Children completed in order.
- Tests and validation commands run.
- Files changed.
- Follow-up beads created.
- Remaining blockers, if any.
