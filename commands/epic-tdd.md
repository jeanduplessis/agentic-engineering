---
description: "Implement an epic bead's child tasks in dependency order using TDD"
argument-hint: "<epic-bead-id> [instructions]"
---

Orchestrate TDD implementation for an epic bead and descendants.

Arguments: $ARGUMENTS

## Arguments

- First argument must be the epic bead ID. If missing/ambiguous, ask one concise clarification and stop.

- Treat the rest as implementation constraints/focus notes.

- Do not create an epic; work only under the supplied epic.

## Skills

Load and follow `beads` and `tdd`.

## 1. Verify and inspect

Run:

```bash
bd --version
bd info
bd show <epic-id> --json
bd children <epic-id> --json
bd ready --parent <epic-id> --json
bd blocked --parent <epic-id>
```

If `bd` is unavailable, no beads database exists, or the epic ID is invalid, report it and ask before changing setup.

Confirm the bead is an epic or parent/container. If it has no children, report no subtasks and stop.

## 2. Queue

Use beads as the ordering source:

- Scope: descendant tasks under the epic, excluding closed children.

- Prefer `bd ready --parent <epic-id> --json`; ready = open and unblocked.

- Sort ready work by priority, dependency order, then oldest created.

- Never start a child with unclosed blockers.

- If no child is ready and open children remain, report blocked children and stop.

Before coding, append:

```bash
bd update <epic-id> --append-notes "ORCHESTRATION: starting TDD pass. READY: <ids>. BLOCKED: <ids>. NOTES: <user constraints>." --json
```

## 3. TDD child loop

Repeat until every descendant child is closed or all remaining work is blocked:

1. Refresh state:
   ```bash
   bd children <epic-id> --json
   bd ready --parent <epic-id> --json
   ```
2. Pick the next ready child by queue rules.

3. Inspect and claim:
   ```bash
   bd show <child-id> --json
   bd update <child-id> --claim --json
   ```
4. Implement using `tdd`:

   - Derive public interface and test behavior from bead description, acceptance criteria, project docs, and codebase.

   - If behavior/interface is ambiguous, ask before implementing that child.

   - Write one behavior test; verify expected failure.

   - Implement the smallest passing change.

   - Repeat one vertical slice at a time; do not write all tests upfront.

   - Refactor only while green.

   - After each slice, run relevant tests; before closure, run appropriate broader validation.

5. At meaningful slice boundaries, update notes:

   ```bash
   bd update <child-id> \
     --notes "CURRENT: <red/green state>. TEST: <test/validation>. NEXT: <next behavior or done>. DECISIONS: <important choices>." \
     --json
   ```

6. If new work appears, do not derail; create a follow-up child linked to the current child:

   ```bash
   bd create "Found while TDD: <short title>" \
     -t task -p 2 --parent <epic-id> \
     --deps discovered-from:<child-id> \
     --description "Observed while implementing <child-id>: <context, expected behavior, and why it is deferred>." \
     --json
   ```

7. Close the child only when acceptance criteria are met and validation passes:

   ```bash
   bd close <child-id> \
     --reason "Delivered with TDD. Tests/validation: <commands>. Key files: <paths>." \
     --json
   ```

8. Append epic progress:

   ```bash
   bd update <epic-id> \
     --append-notes "PROGRESS: closed <child-id>. VALIDATION: <commands>. NEXT READY: <ids>. BLOCKED: <ids>." \
     --json
   ```

## 4. Blockers and failures

- If a test cannot become green without scope change, record the red state in child notes and stop.

- If a child is blocked by missing requirements, an external dependency, or an unrelated failing test,
  mark/note the blocker; continue only if another child is ready.

- If validation fails for unrelated reasons, record the failure and create a `discovered-from:<child-id>` follow-up unless project guidance says fix it now.

- Do not close:

  - a child with failing relevant tests.

  - the epic while any child remains open, blocked, deferred, or in progress.

## 5. Finish the epic

When no open descendants remain:

1. Run final relevant validation for the whole epic.

2. Inspect completion state:
   ```bash
   bd children <epic-id> --json
   bd epic status --json
   bd epic close-eligible --dry-run --json
   ```
3. Close the epic only if beads reports it eligible or all children are closed:
   ```bash
   bd close <epic-id> --reason "Implemented all child tasks with TDD. Final validation: <commands>." --json
   ```

## 6. Final response

Report:

- Epic ID and title.

- Children completed in order.

- Tests and validation commands run.

- Files changed.

- Follow-up beads created.

- Remaining blockers, if any.
