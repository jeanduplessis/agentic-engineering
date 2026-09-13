# Gate Contracts

These contracts apply identically whether a gate runs through a native subagent, current harness runner, optional Pi self-invocation, or sequential current-session fallback. Executor choice never changes permissions, pass criteria, footer requirements, or parent-only lifecycle/commit ownership.

## recon

Read-only.

Must inspect:

- epic bead;
- descendants;
- `CONTEXT.md` if present;
- `SPEC.md` if present;
- relevant ADRs;
- likely code seams;
- tests;
- commands/routes/config/public APIs.

PASS means enough context exists for downstream gates.

## tdd-task

Implementation gate for one concrete task.

Allowed:

- edit code/tests;
- run tests;
- create follow-up beads for discovered out-of-scope work.

Forbidden:

- staging;
- committing;
- closing beads.

Must:

- read recon output;
- inspect task ACs;
- use TDD where feasible;
- avoid sibling scope;
- report changed files and validation commands.

PASS means implementation is ready for independent validation.

## task-validate

Read-only validation gate for one task.

Forbidden:

- edits;
- bead updates;
- comments;
- staging;
- commits.

Must:

- validate each AC with proof;
- run targeted commands;
- for relationship/invariant tasks, test invalidating mutation paths, not only direct create/update paths.

PASS only if every AC passes and validation commands pass.

## code-review

Review gate.

Allowed:

- edit code/tests to fix findings.

Forbidden:

- staging;
- committing;
- bead closure;
- bead comments.

Must review:

- correctness;
- security;
- data/resource handling;
- errors;
- tests;
- SPEC compliance;
- lifecycle semantics;
- language/framework quality relevant to the repo.

PASS only if no blocking findings remain.

## epic-validate

Read-only final validation.

Must validate:

- epic requirement;
- descendant requirements;
- branch diff;
- final behavior;
- relevant broad tests;
- relationship/invariant invalidating mutation paths where applicable.

PASS only if every non-N/A requirement passes.
