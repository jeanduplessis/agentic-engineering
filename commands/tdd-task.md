---
description: "Implement one bead task using TDD"
argument-hint: "<task-bead-id> [instructions]"
skills:
  - tdd
  - beads
---

Implement exactly one beads task with TDD.

Args: $ARGUMENTS

## Arguments

- First arg = task bead ID. If missing/ambiguous, ask one concise clarification and stop.
- Rest = implementation constraints/focus notes.
- Scope only the supplied bead. Do not implement siblings or an epic child queue.

## 1. Verify and inspect

Run:

```bash
br --version
br info
br show <task-id> --json
br dep list <task-id> --direction down --json
br dep list <task-id> --direction up --type parent-child --json
```

If `br` is unavailable, no beads database exists, or the task ID is invalid, report it and ask before changing setup.

Confirm it is a concrete task/bug suitable for direct implementation.
If it is an epic/container with open children, stop and recommend `/tdd-epic <task-id>` unless the user
explicitly wants this parent bead implemented directly.
If it has unclosed blockers, report them and stop.

## 2. Claim and plan

Claim:

```bash
br update <task-id> --claim --json
```

Inspect guidance/code:

- Read `CONTEXT.md` if present.
- Respect relevant ADRs in `docs/adr/` if present.
- Derive public interface and behavior from bead description, acceptance criteria, project docs, and codebase.
- Extract explicit acceptance criteria and track which criteria each TDD slice is proving.

Before coding, update TDD state:

```bash
br update <task-id> \
  --notes "CURRENT: planning. TEST: none yet. NEXT: first behavior test. CONSTRAINTS: <user constraints>." \
  --json
```

If required behavior/interface is ambiguous, ask one concise clarification and stop.

## 3. TDD loop

Implement vertical slices:

1. Write one behavior test through the public interface.
2. Run the focused test; verify expected failure.
3. Implement the smallest passing change.
4. Run the focused test; verify it passes.
5. When a slice proves an acceptance criterion complete, immediately mark that criterion completed in the bead acceptance criteria, preserving criterion text/order and leaving unproven criteria unchecked:

   ```bash
   br update <task-id> \
     --acceptance-criteria "<same criteria with newly completed items marked [x]>" \
     --json
   ```

6. Refactor only while green.
7. Repeat until acceptance criteria are met and marked complete.

Rules:

- Do not write all tests upfront.
- Test observable behavior, not implementation details.
- Do not add speculative features.
- Do not derail into side quests.
- Prefer focused validation during slices; run broader relevant validation before closure.

At meaningful boundaries, update notes:

```bash
br update <task-id> \
  --notes "CURRENT: <red/green state>. TEST: <test/validation>. NEXT: <next behavior or done>. DECISIONS: <important choices>." \
  --json
```

## 4. Follow-ups and blockers

If new work appears, do not silently expand scope. Create a follow-up linked to the current task:

```bash
br create "Found while TDD: <short title>" \
  -t task -p 2 \
  --deps discovered-from:<task-id> \
  --description "Observed while implementing <task-id>: <context, expected behavior, and why it is deferred>." \
  --json
```

Stop without closing when:

- relevant tests fail;
- requirements/interface are unclear;
- an external dependency blocks completion;
- passing the test requires scope outside this bead.

Before stopping, record durable state:

```bash
br update <task-id> \
  --notes "CURRENT: blocked. TEST: <failing/passing validation>. NEXT: <needed decision/action>. BLOCKER: <blocker>." \
  --json
```

For unrelated validation failures, record the failure and create a `discovered-from:<task-id>` follow-up unless project guidance says to fix it now.

## 5. Close

Close only when acceptance criteria are met, completed criteria are marked in the bead, and relevant validation passes:

```bash
br close <task-id> \
  --reason "Delivered with TDD. Tests/validation: <commands>. Key files: <paths>." \
  --json
```

Sync guardrail:

- Do not run bare `br sync`.
- Run `br sync --flush-only` only when asked to export JSONL before committing `.beads/`.

## 6. Final response

Report:

- Task ID and title.
- Behaviors delivered.
- Tests and validation commands run.
- Files changed.
- Follow-up beads created.
- Remaining blockers, if any.
