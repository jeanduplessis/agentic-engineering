# AGENTS.md — agent resource context

This repository (`~/.agents`) is a local agent resource package: downstream-owned skills,
shared Pi/OpenCode commands, system-prompt fragments, adapters, and repo-level validation/eval tooling.

Pi and OpenCode are equal baseline harness targets. All canonical resources must preserve equivalent behavior in both. Harness-specific metadata, adapters, and acceleration are allowed only when other harnesses ignore them safely and the source retains a complete shared fallback.

## Directory map

- `skills/` — downstream-owned shared-harness skills. Read `skills/AGENTS.md` before adding or changing skills.

- `commands/` — canonical shared Pi/OpenCode Markdown command source, exposed to Pi through `package.json` and adapters through symlinks. Never create generated adapter copies.

- `extensions/extended-commands/` — permissive Pi adapter over canonical commands; activation is an untracked Pi discovery symlink.

- `prompts/` — system-prompt resources only. `prompts/APPEND_SYSTEM.md` is the repo-owned append-system fragment and is not a slash command.

- `tools/` — Python tooling for token counting, LLM-optimization checks, shared-harness skill evals, and skill validation.
  Read `tools/AGENTS.md` and any tool-local `AGENTS.md` before editing.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and easy to execute. Avoid clever indirection when direct instructions work.

- Prefer Pi package, skill, prompt-template, context-file, and system-prompt terminology only for Pi-specific capabilities; use harness-neutral terms for shared contracts.

- Prefer repo-level shared tools over one-off scripts. If a public tool contract changes, update its README, `AGENTS.md`, and tests together.

- Use deterministic validation by default. Do not run live harness/model-backed evals unless the user explicitly requests or approves them.

- Respect nested `AGENTS.md` files; the closest one to the files being changed has the most specific guidance.

- Nested package staging:
  - After every `git add` and before committing, verify scope with `git diff --cached --name-status`.
  - If unrelated root or sibling files are staged, run `git reset` and restage exact paths from the current cwd, or use:
    ```sh
    git -C <repo-root> add <repo-root-relative-paths>
    ```

## Useful validation commands

For tool changes:

```sh
python3 -m unittest discover -v
```

For skill validation, use the repo-local validation tool:

```sh
./tools/skill_valid/skill_validate.sh skills/<skill-name>
```

Run live validation gates only with explicit approval; pass `--allow-live` and select the intended supported harness when needed.

<!-- AIT START -->
# Agent Issue Tracker (ait)

This repo uses `ait` CLI for structured, durable, repo-local issue tracking. 

## Project State

- Project data lives in `.ait/`.
- The CLI is the mutation surface; do not edit `.ait/state.sqlite` or `.ait/issues.jsonl` directly.
- Non-view commands return JSON envelopes: success is `{"ok": true, "data": ...}`; failure is `{"ok": false, "error": ...}`.
- Mutating commands require an actor: pass `--actor agent` or set `AIT_ACTOR`.

## Usage

When working with `ait`, load and follow the `ait-cli` skill.

Use the skill for creating, claiming, updating, closing, listing, inspecting, validating, or resuming issues; finding ready work; managing dependencies; and any workflow needing persistent issue state.

## Safety Rules

- Do not run bare `ait` in automation; it opens the TUI.
- Do not initialize, import, export, or force-close unless requested or clearly required.
- Use `ait check` before handoff and after unusual failures.
- On command failure, report `error.code`, `error.message`, and next safe action.
<!-- AIT END -->
