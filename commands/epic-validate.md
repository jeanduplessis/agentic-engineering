---
description: "Validate an epic's requirements against implemented code"
argument-hint: "<epic-bead-id> [scope notes]"
skills:
  - beads
---

Validate documented epic requirements against implemented code.

Arguments: $ARGUMENTS

## Argument handling

- First arg: epic bead ID; if missing/ambiguous, ask one concise clarification and stop.
- Treat remaining args as validation scope notes, branch/test constraints, or implementation pointers.
- Read-only by default: do not edit code, close beads, change task status, or add bead comments unless explicitly asked.

## 1. Verify and load epic context

Run:

```bash
br --version
br info
br show <epic-id> --json
br dep list <epic-id> --direction up --type parent-child --json
br dep tree <epic-id> --direction up --json
```

If `br` is unavailable, no beads DB exists, or epic ID is invalid, report and ask before setup changes.
Confirm bead is an epic/parent/container. If no subtasks exist, validate only epic requirements and state none were found.
Collect title, description, acceptance criteria, user stories, notes, close reason, and relevant `br` comments for the epic and each descendant.
If a command lacks comments/fields, use `br <command> --help` to find the read-only command; do not mutate state.

## 2. Build the requirements matrix

Extract each discrete requirement from epic and descendants:

- User stories: `As a... I want... so that...` or equivalent user-goal statements.
- Acceptance criteria: checklist items, MUST/SHOULD rules, expected behavior, validation requirements, constraints, edge cases, nonfunctional requirements, and explicit out-of-scope statements.
- Completion claims: implemented behavior in notes/close reasons.

Create stable IDs:

- Epic user stories: `E-US-#`.
- Epic acceptance criteria: `E-AC-#`.
- Subtask user stories: `<task-id>-US-#`.
- Subtask acceptance criteria: `<task-id>-AC-#`.
- Task completion claims not already covered by AC/user stories: `<task-id>-CL-#`.

Merge exact duplicates and preserve all source bead IDs. Keep overlapping requirements separate when scope, actor, edge case, or obligation level differs.
Flag epic/subtask contradictions before code validation.

## 3. Resolve implementation scope

Use scope notes and repo evidence. Inspect read-only state:

```bash
git status --short
git branch --show-current
git remote -v
git rev-parse --show-toplevel
git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || true
git diff --name-only
git diff --cached --name-only
git diff --name-only <base>...HEAD
```

If no base branch exists, use working-tree changes and files referenced by bead notes, close reasons, comments, docs, tests, and code searches.
Search `rg` or equivalent for requirement terms, feature names, public interfaces, routes, commands, config keys, and test names.

Implementation scope includes:

- production code claiming to satisfy each requirement;
- tests exercising it;
- docs/config/migrations/scripts required for the behavior;
- related code paths needed to verify edge cases/invariants.

If no implementation path is discoverable, mark the requirement `UNKNOWN` until proven otherwise; do not infer satisfaction from closed tasks.

## 4. Validate each requirement

Inspect relevant code/tests for each requirement. Assign one verdict:

- `PASS`: code and, where appropriate, tests show satisfaction.
- `PARTIAL`: core behavior exists, but scope, edge cases, tests, or integrations are incomplete.
- `FAIL`: code contradicts or omits the requirement.
- `UNKNOWN`: evidence is insufficient, ambiguous, or outside accessible code.
- `N/A`: requirement is explicitly out of scope or not code-implementable; explain why.

Validation rules:

- Verify requirement text, not task status/implementation intent.
- AC: check every condition/boundary/actor/data state/error path/stated nonfunctional constraint.
- User stories: verify end-to-end user goal completion, not just a helper or partial UI/API.
- SHOULD: mark `PARTIAL`/`FAIL` when omitted unless omission is allowed.
- Missing tests are risk; fail only when AC requires tests or behavior cannot otherwise be verified.
- Unreachable/dead/feature-flag-disabled/docs-only code is insufficient unless explicitly allowed.
- Ensure negative/out-of-scope requirements are not accidentally implemented.

Record per row:

- requirement ID and source bead ID/title;
- requirement text summary;
- verdict;
- implementation evidence: paths and relevant symbols/line refs when available;
- test/validation evidence, including commands/results;
- gaps, risks, recommended next action.

## 5. Run validation commands

Prefer targeted, deterministic validation. Choose commands from:

- test commands named in bead close reasons/notes/comments;
- project package scripts or documented validation commands;
- test files directly covering implementation scope;
- existing repo conventions.

Ask approval before expensive/destructive/external-service/migration/live-integration commands.
If tests are unavailable or fail for unrelated reasons, report separately and explain confidence impact.

## 6. Findings and recommendations

Group findings by requirement, then severity:

- `CRITICAL`: required user story/AC is absent, contradicted, or unsafe.
- `HIGH`: requirement is partial or untested in ways likely to break users.
- `MEDIUM`: evidence is incomplete, edge cases are weak, or important behavior lacks tests.
- `LOW`: minor documentation/naming/traceability issue.

Each finding includes:

```markdown
### <SEVERITY> — <requirement-id>: <short title>

**Source:** <bead id/title and quoted requirement>
**Verdict:** PASS | PARTIAL | FAIL | UNKNOWN | N/A
**Evidence:** <file paths, symbols, line refs, commands, outputs>
**Gap:** <what is missing, wrong, or uncertain>
**Recommendation:** <specific next action>
```

Skip `PASS` rows from findings unless they carry notable risk; include all rows in the matrix.

## Final response

Return:

1. **Scope:** epic ID/title; descendant task IDs reviewed; branch/base; implementation files inspected; validation commands run.
2. **Summary:** verdict/severity counts; contradictions and open subtasks.
3. **Requirements matrix:** one compact row per requirement.
4. **Findings:** actionable issues using the format above.
5. **Recommendations:** prioritized next steps, including subtasks/follow-up beads to create, tests to add/run, and whether the epic appears ready to close.

Do not claim the epic is complete unless every non-`N/A` user story/AC is `PASS` and relevant validation commands pass.
