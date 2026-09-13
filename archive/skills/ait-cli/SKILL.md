---
name: ait-cli
description: Use the ait CLI as durable, structured, repository-local task memory. Trigger when a user asks to track, create, claim, update, close, list, inspect, validate, or resume ait issues; find ready work; manage dependencies; or use ait instead of beads. Use for agent workflows that need persistent issue state in .ait/.
license: MIT
compatibility: Requires the ait CLI in PATH, or the ait Rust repo so `cargo run --quiet --` can invoke it. Requires an existing `.ait/` project unless the user asks to initialize one.
allowed-tools: Bash(ait:*) Bash(cargo:*) Bash(git:*) Read
---

# ait CLI

Use `ait` as structured, JSON-first, repository-local task memory for agent work.

## First principles

- Prefer `ait` when the repo has `.ait/` and the user wants durable task state.
- Do not use `br`/beads for `ait` projects unless the user asks.
- Do not run bare `ait` in automation: no subcommand opens the TUI.
- Treat the CLI as the only mutation surface. Do not edit `.ait/state.sqlite` or `.ait/issues.jsonl` directly.
- Do not initialize, import, force-close, delete, repair, or rewrite `.ait/` unless the user explicitly asks or approves.
- Use non-view commands only; every non-view command returns a JSON envelope.
- Parse `ok`. Continue only when `ok: true`; on `ok: false`, report `error.code`, `error.message`, and relevant `error.details`.
- Use `--pretty` only for human readability; never depend on formatting.
- Use `--project-dir <path>` only when discovery would target the wrong `.ait/`.
- Mutating commands require an actor. Pass `--actor <name>` or set `AIT_ACTOR`; prefer the harness/user identity, otherwise `--actor agent`.

If `ait` is unavailable but the current repo is the ait Rust repo, use:

```bash
cargo run --quiet -- <ait args>
```

## Startup checks

Run before substantial work:

```bash
ait check
ait ready --grouped
ait list --status in_progress
```

If no `.ait/` exists, ask before:

```bash
ait --actor agent init --project <ONE_TO_THREE_UPPERCASE_ALNUM_STARTING_WITH_LETTER>
```

## Read work

```bash
ait ready                 # executable ready leaf issues
ait ready --grouped       # ready work grouped by parent context
ait list                  # all issues
ait list --status open
ait list --type task
ait list --lane Blocked   # Blocked, Ready, In-progress, Closed
ait show <ISSUE_ID>
ait schema all
ait schema create-input
ait schema update-input
```

Use `ready` for selecting implementation work. `list` is inventory; it may include containers and closed work.

## Create issues

Create from JSON on stdin. Required fields: `title`, `issue_type` (`epic|task|bug|chore`). Common fields: `priority` (`P0`-`P4`), `parent`, `assignee`, `identifier`, `content`.

```bash
cat <<'JSON' | ait --actor agent create --stdin
{
  "title": "Implement parser error handling",
  "issue_type": "task",
  "priority": "P1",
  "content": {
    "goal": "Return stable JSON errors for parser failures.",
    "context": "CLI output must stay machine-readable.",
    "acceptance_criteria": [
      {"text": "Invalid arguments return ok=false with a stable error code"},
      {"text": "Regression tests cover the parse failure"}
    ],
    "verification": ["cargo test invalid_cli_parse_errors_emit_json_error_envelopes_without_stderr"],
    "files": [{"path": "src/main.rs", "reason": "CLI parse handling"}]
  }
}
JSON
```

Child issues use `parent: <ROOT_ID>`. `ait` assigns child IDs as `<ROOT_ID>.<n>`. Do not create nested children unless current `ait` behavior explicitly supports them.

## Claim and progress

Claim before substantial edits:

```bash
ait --actor agent claim <ISSUE_ID>
```

Record handoff/progress as comments for durable narrative context:

```bash
cat <<'TEXT' | ait --actor agent comment add <ISSUE_ID> --stdin
CURRENT: implemented parser handling.
NEXT: run full regression suite.
VALIDATE: cargo test
TEXT
```

Use comments for handoffs. Use structured updates for issue state/content changes.

## Update issues

`ait update` accepts an RFC 6902 JSON Patch subset: only `test` and `replace`. Use `test` before `replace` when avoiding lost updates.

```bash
cat <<'JSON' | ait --actor agent update <ISSUE_ID> --stdin
[
  {"op":"test","path":"/content/acceptance_criteria/0/done","value":false},
  {"op":"replace","path":"/content/acceptance_criteria/0/done","value":true},
  {"op":"replace","path":"/content/agent_notes","value":["Implemented JSON parse error envelope."]}
]
JSON
```

Read-only/generated paths are rejected, including:

- `/id`, `/issue_type`, `/parent`;
- `/created_at`, `/updated_at`;
- `/content/schema_version`;
- `/comments`, `/dependencies`, `/dependents`;
- `/child_summaries`, `/readiness`, `/close_blockers`.

Use command-specific verbs instead of patching read-only relationships or lifecycle helpers.

## Dependencies and readiness

Dependency direction: `ait dep add ISSUE TARGET --type blocks` means `ISSUE` is blocked by `TARGET`; `TARGET` blocks `ISSUE` until `TARGET` closes.

```bash
ait --actor agent dep add <ISSUE_ID> <BLOCKING_TARGET_ID> --type blocks
ait --actor agent dep add <ISSUE_ID> <RELATED_ID> --type related
ait --actor agent dep remove <ISSUE_ID> <TARGET_ID> --type blocks
```

Readiness lanes:

- `Blocked`: open issue has unresolved `blocks` dependencies.
- `Ready`: open issue has no unresolved `blocks` dependencies.
- `In-progress`: claimed/in-progress issue, regardless of blockers.
- `Closed`: closed issue.

`ait ready` returns only ready executable leaf issues.

## Close issues

Normal close is allowed only when all acceptance criteria are done and all children are closed.

```bash
ait --actor agent close <ISSUE_ID> --reason "Delivered X; validated with Y."
```

Do not use `--force` unless the user explicitly approves and provides a reason:

```bash
ait --actor agent close <ISSUE_ID> --force --reason "Superseded by <ISSUE_ID>."
```

If close fails with `close_incomplete_acceptance_criteria` or `close_open_children`, finish or update the listed blockers instead of forcing by default.

## Export, import, and check

```bash
ait check
ait --actor agent export
ait --actor agent import
```

- `check` is safe/read-only; run it before handoff and after unusual failures.
- `export` rebuilds the git-friendly JSONL mirror from authoritative state; it mutates files and requires an actor.
- `import` rebuilds/updates authoritative state from JSONL; it mutates state. Ask before import unless the user requested recovery/migration.

## Error handling

All command failures return:

```json
{"ok": false, "error": {"code": "...", "message": "...", "details": {}}}
```

Common codes: `project_not_found`, `project_already_exists`, `invalid_project_id`, `invalid_json`, `invalid_schema`, `actor_required`, `write_lock_busy`, `issue_not_found`, `parent_not_found`, `dependency_not_found`, `dependency_already_exists`, `invalid_issue_type`, `invalid_status`, `invalid_priority`, `invalid_identifier`, `identifier_collision`, `patch_invalid`, `patch_read_only_path`, `patch_test_failed`, `close_incomplete_acceptance_criteria`, `close_open_children`, `force_reason_required`, `comment_empty`, `jsonl_export_failed`, `jsonl_import_failed`, `schema_not_found`, `clipboard_failed`, `internal_error`.

On failure, report the command, error code, concise blocker, and next safe action.

## Handoff checklist

Before pausing or handing off:

```bash
ait check
ait show <ISSUE_ID>
git status --short
```

Add a comment with:

- `CURRENT`: what changed;
- `NEXT`: next action;
- `DECISIONS`: important choices;
- `VALIDATE`: commands run/results;
- `BLOCKERS`: blockers or `none`.
