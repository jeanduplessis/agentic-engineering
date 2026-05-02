---
name: tdd
description: >
  Guides test-driven development with a red-green-refactor loop and beads_rust (`br`) task tracking.
  Use when the user wants to build features or fix bugs using TDD, mentions red-green-refactor,
  wants integration tests, asks for test-first development, or wants TDD progress recorded in beads tasks.
---

# Test-Driven Development

Build behavior in thin TDD vertical slices.
Use beads_rust (`br`) for durable context, progress, blockers, and follow-up work.
Do not create GitHub tracker entries unless explicitly asked for GitHub; record durable TDD work in beads tasks.

## Beads task protocol

Before planning or coding, connect TDD work to a beads task when it is substantial, user-visible, multi-step, or likely to span context boundaries.

1. **Verify the beads CLI**
   ```bash
   br --version
   ```
   If `br` is unavailable, ask the user how to proceed.

2. **Verify the beads database**
   ```bash
   br info
   ```
   If no database exists, ask the user how to proceed. Do not silently initialize beads unless the user asks for setup.

3. **Inspect existing work**
   Given a bead ID, inspect it first: `br show <id> --json`.
   Do not create a duplicate bead when an existing bead already covers the work.

4. **Select ready work only when asked**
   To pick ready work at the user's request, run: `br ready --json`.

5. **Create one task for new durable work**
   ```bash
   br create "TDD: <short behavior/feature>" -t task -p 2 \
     --description "Goal, public behavior to deliver, and initial test focus." --json
   ```

6. **Claim before implementation**
   ```bash
   br update <id> --claim --json
   ```

7. **Update compact current-state notes**
   Capture current red/green state, behavior covered, failing test name, decisions, blockers, and next test.
   ```bash
   br update <id> --notes "CURRENT: ... TEST: ... NEXT: ..." --json
   ```

8. **Add handoff comments when useful**
   Use comments for longer narrative context a future agent needs after compaction.
   ```bash
   br comments add <id> --message "TDD handoff: ..." --json
   ```

9. **Stay on the current TDD loop**
   Do not derail the current TDD loop for side quests.

10. **Create beads for discovered follow-up work**
   Use `br create "Found while TDD: <follow-up>" -t task -p 2 --deps discovered-from:<id> --json`.
   Add a description with the discovery context and expected behavior.

11. **Close when done**
   Run `br close <id> --reason "Delivered behavior with tests: ..." --json`.

12. **Avoid generic storage steps**
   Do not run bare `br sync`.
   Do not add session-end sync by default.
   Run `br sync --flush-only` only when asked to export JSONL before committing `.beads/`.

For tiny same-session changes, use a local checklist. Promote to a beads task once work branches, blocks, or needs durable handoff context.

### Beads command guardrails

- Prefer `--json` for reads/writes that support it, but keep `br info` as the setup diagnostic.
- Use `br comments add <id> --message ... --json` for handoff comments; do not use legacy singular comment forms.
- If a `br` command fails, check `br <command> --help` and adapt to the installed CLI before proceeding.

## Philosophy

**Core principle**: Tests should verify behavior through public interfaces, not implementation details. Code can change entirely; tests shouldn't.

**Good tests** are integration-style: they exercise real code paths through public APIs.
They describe _what_ the system does, not _how_.
A good test reads like a specification: "user can checkout with valid cart" states the capability.
These tests survive refactors because they ignore internal structure.

**Bad tests** are coupled to implementation.
They mock internal collaborators, test private methods, or verify externally, such as querying a database instead of using the interface.
Warning sign: tests break when you refactor, but behavior has not changed.
If renaming an internal function breaks tests, they tested implementation, not behavior.

See [tests.md](tests.md) for examples and [mocking.md](mocking.md) for mocking guidelines.

## Anti-Pattern: Horizontal Slices

**Do not write all tests first, then all implementation.** This is horizontal slicing - treating RED as "write all tests" and GREEN as "write all code."

This produces weak tests:

- Tests written in bulk test _imagined_ behavior, not _actual_ behavior
- You end up testing the _shape_ of things (data structures, function signatures) rather than user-facing behavior
- Tests become insensitive to real changes - they pass when behavior breaks, fail when behavior is fine
- You outrun your headlights, committing to test structure before understanding the implementation

**Correct approach**: Vertical slices via tracer bullets.
One test → one implementation → repeat.
Each test responds to the previous cycle.
Because you just wrote the code, you know what behavior matters and how to verify it.

```text
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5

RIGHT (vertical):
  RED→GREEN: test1→impl1
  RED→GREEN: test2→impl2
  RED→GREEN: test3→impl3
  ...
```

## Workflow

### 1. Planning

When exploring the codebase, read `CONTEXT.md` if present.
Use its canonical terms in test names and interface vocabulary, and respect relevant ADRs in `docs/adr/`.
If docs are absent, proceed silently.

Before writing code:

- [ ] Load or create the relevant beads task, then claim it when starting durable work
- [ ] Confirm what interface changes are needed
- [ ] Confirm which behaviors to test, prioritizing the most important paths
- [ ] Identify opportunities for [deep modules](deep-modules.md): small interface, deep implementation
- [ ] Design interfaces for [testability](interface-design.md)
- [ ] List the behaviors to test, not implementation steps
- [ ] Record the approved test plan in the beads task notes when it matters for handoff
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most important to test?"

You can't test everything.
Confirm with the user exactly which behaviors matter most.
Focus testing on critical paths and complex logic, not every edge case.

### 2. Tracer Bullet

Write one test that confirms one thing about the system:

```text
RED:   Write test for first behavior → test fails
GREEN: Write minimal code to pass → test passes
```

This tracer bullet proves the path works end-to-end.
Record the first successful tracer bullet in the beads task if it changes the implementation plan or helps a future agent resume.

### 3. Incremental Loop

For each remaining behavior:

```text
RED:   Write next test → fails
GREEN: Minimal code to pass → passes
```

Rules:

- One test at a time
- Only enough code to pass current test
- Don't anticipate future tests
- Keep tests focused on observable behavior
- Update the beads task at meaningful slice boundaries, not after every tiny edit

### 4. Refactor

After all tests pass, look for [refactor candidates](refactoring.md):

- [ ] Extract duplication
- [ ] Deepen modules: move complexity behind simple interfaces
- [ ] Apply SOLID principles where natural
- [ ] Consider what new code reveals about existing code
- [ ] Run tests after each refactor step
- [ ] Record final validation commands and important design decisions in the beads task before closing

**Never refactor while RED.** Get to GREEN first.

## Checklist per cycle

```text
[ ] Test describes behavior, not implementation
[ ] Test uses public interface only
[ ] Test would survive internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
[ ] Beads task notes/comments capture durable state when needed
```
