---
description: "Validate one bead task's acceptance criteria with proof"
argument-hint: "<task-bead-id> [scope notes]"
skills:
  - beads
---

## Required skills

- `beads`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Validate one bead task by proving whether each acceptance criterion is met.

Arguments: $ARGUMENTS

## Argument handling

- First arg: bead task ID. If missing or ambiguous, ask one concise clarification and stop.
- Treat remaining args as validation scope notes, branch/test constraints, or implementation pointers.
- Read-only by default: do not edit files, close/update beads, add comments, or change status unless explicitly asked.

## 1. Load bead content

Run:

```bash
br --version
br info
br show <task-id> --json
br dep list <task-id> --direction down --json
br dep list <task-id> --direction up --json
```

If `br` is unavailable, no beads DB exists, or the task ID is invalid, report it and ask before setup changes.
Confirm the bead is a concrete task/bug. If it is an epic/container with open children, stop and recommend `/epic-validate <task-id>`.
Collect title, description, explicit acceptance criteria, notes, close reason, and relevant comments. If comments are not included by `br show`, use `br --help`/`br <command> --help` to find the read-only comments command.

## 2. Extract acceptance criteria

Build an AC list only from explicit acceptance criteria in the bead content:

- checklist items under Acceptance Criteria/AC/Done When;
- MUST/SHALL acceptance rules;
- required validation/test criteria stated as AC.

Do not invent AC from implementation notes, status, or broad task description. If no explicit AC exists, report `UNKNOWN: no explicit acceptance criteria found` and stop unless the user asks for inferred criteria.
Assign stable IDs: `AC-1`, `AC-2`, ... Preserve each criterion's exact quoted text.
Split compound criteria when separate proof is needed for independent behavior, edge cases, or validation requirements.

## 3. Resolve implementation scope

Inspect read-only repo state:

```bash
git status --short
git branch --show-current
git rev-parse --show-toplevel
git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || true
git diff --name-only
git diff --cached --name-only
git diff --name-only <base>...HEAD
```

Use scope notes plus bead references to find relevant implementation paths. Search with `rg` for task title terms, AC terms, feature names, public APIs, routes, commands, config keys, and tests.
Scope includes production code, tests, docs/config/migrations/scripts required to satisfy the AC, and related edge-case paths.
If no implementation path is discoverable for an AC, mark it `UNKNOWN` until proven; do not infer satisfaction from task status, notes, or close reason.

## 4. Prove each acceptance criterion

For each AC, inspect code/tests and provide proof. Verdicts:

- `PASS`: proof shows every condition in the AC is satisfied, with relevant validation passing.
- `PARTIAL`: core behavior exists, but a condition, edge case, integration, or required validation is incomplete.
- `FAIL`: code contradicts or omits the AC.
- `UNKNOWN`: evidence is insufficient, ambiguous, inaccessible, or not traceable to implementation.
- `N/A`: AC is explicitly non-code or out of scope; explain why.

Proof rules:

- Validate AC text, not intent or completion claims.
- Quote or precisely summarize the exact code/test behavior that satisfies each AC.
- Provide file paths, symbols, and line refs when available.
- Include validation command(s) and result(s) for each AC when applicable.
- Missing tests are a risk; fail only if the AC requires tests or behavior cannot otherwise be verified.
- Feature-flag-disabled, unreachable, dead, docs-only, or uncalled code is insufficient unless explicitly allowed by the AC.

Run targeted deterministic validation from package scripts, docs, bead notes, or directly relevant tests. Ask approval before expensive, destructive, external-service, migration, or live-integration commands.

## Final response

Return:

1. **Scope:** task ID/title; branch/base; files inspected; validation commands run.
2. **Summary:** AC verdict counts and highest severity gap.
3. **Acceptance criteria proof matrix:** one row per AC with:
   - AC ID
   - quoted AC text
   - verdict
   - implementation proof: file/line/symbol evidence
   - validation proof: command/result or why not run
   - gap/risk
4. **Findings:** only non-`PASS` rows, each with severity, source AC quote, evidence, gap, and specific recommendation.
5. **Closure assessment:** say whether the bead appears ready to close. Do not claim ready unless every AC is `PASS` and relevant validation passes.
