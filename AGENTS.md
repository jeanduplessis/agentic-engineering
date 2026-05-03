# AGENTS.md — Pi agent resource context

This repository (`~/.agents`) is a local Pi resource package: downstream-owned skills,
Pi prompt templates, system-prompt fragments, and repo-level validation/eval tooling.

Pi is the only supported harness target. Optimize tracked resources for Pi behavior and vocabulary.
Do not preserve compatibility with non-Pi harnesses except where required for license or provenance text.

## Directory map

- `skills/` — downstream-owned Pi skills. Read `skills/AGENTS.md` before adding or changing skills.

- `commands/` — Pi Markdown prompt templates exposed as slash commands via `package.json` `pi.prompts`.

- `prompts/` — system-prompt resources only. `prompts/APPEND_SYSTEM.md` is the repo-owned append-system fragment and is not a slash command.

- `tools/` — Python tooling for token counting, LLM-optimization checks, Pi skill evals, and Pi skill validation.
  Read `tools/AGENTS.md` and any tool-local `AGENTS.md` before editing.

- `.beads/` — local beads task state; do not hand-edit unless you are intentionally maintaining task metadata.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and easy to execute. Avoid clever indirection when direct instructions work.

- Prefer Pi package, skill, prompt-template, context-file, and system-prompt terminology.

- Prefer repo-level shared tools over one-off scripts. If a public tool contract changes, update its README, `AGENTS.md`, and tests together.

- Use deterministic validation by default. Do not run live Pi/model-backed evals unless the user explicitly requests or approves them.

- Respect nested `AGENTS.md` files; the closest one to the files being changed has the most specific guidance.

- Nested package staging:
  - After every `git add` and before committing, verify scope with `git diff --cached --name-status`.
  - If unrelated root or sibling files are staged, run `git reset` and restage exact paths from the current cwd, or use:
    ```sh
    git -C <repo-root> add <repo-root-relative-paths>
    ```

- Nested package beads work:
  - Name the target `.beads/` directory before mutating.
  - Keep root `.beads/` out of scope unless the target repo path is the repository root.

## Useful validation commands

For tool changes:

```sh
python3 -m unittest discover -v
```

For skill validation, use the repo-local validation tool:

```sh
./tools/skill_valid/skill_validate.sh skills/<skill-name>
```

Run live validation gates only with explicit approval; the wrapper passes `--allow-live-pi` to `tools.skill_valid`.
