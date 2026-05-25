# Gate Contracts

## recon

Read-only.

Must inspect:

- ait epic;
- child/descendant issues;
- `CONTEXT.md` if present;
- `SPEC.md` if present;
- relevant ADRs;
- likely code seams;
- tests;
- commands/routes/config/public APIs.

PASS means enough context exists for downstream gates.

## tdd-task

Implementation gate for one concrete ait issue.

Allowed:

- edit code/tests;
- run tests;
- propose follow-up ait issues for discovered out-of-scope work;
- create follow-up ait issues only when the parent prompt explicitly permits it.

Forbidden unless explicitly permitted by the parent prompt:

- staging;
- committing;
- closing issues;
- updating issues;
- adding issue comments;
- force-closing issues;
- direct `.ait/` file edits.

Must:

- read recon output;
- inspect issue acceptance criteria;
- use TDD where feasible;
- avoid sibling scope;
- report changed files and validation commands.

PASS means implementation is ready for independent validation.

## task-validate

Read-only validation gate for one issue.

Forbidden:

- edits;
- ait mutations;
- comments;
- staging;
- commits.

Must:

- validate each acceptance criterion with proof;
- run targeted commands;
- for relationship/invariant tasks, test invalidating mutation paths, not only direct create/update paths.

PASS only if every acceptance criterion passes and validation commands pass.

## code-review

Review gate.

Allowed:

- edit code/tests to fix findings.

Forbidden:

- staging;
- committing;
- issue closure;
- issue comments;
- issue updates;
- force-close;
- direct `.ait/` file edits.

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
