# AGENTS.md — agent resource context

This repository is a local agent-resource package. T3 Code orchestrates the user's agents. Supported harnesses are Claude Code (one per T3 Code instance, e.g. work and personal), OpenAI Codex, Grok Build, Pi and Kilo. Skills are shared by every harness; Pi additionally gets this repository's commands, extensions, root policy and subagent policy. Model providers used inside Pi, including the Kilo AI gateway, are separate from harness support. The skill eval runner's live mode supports Pi only.

## Directory map

- `skills/` — Agent Skills for every harness. Read `skills/AGENTS.md` before changing a skill.
- `harness/pi/` — Pi-owned resources: `APPEND_SYSTEM.md` is the canonical root-agent policy, `commands/` contains Pi prompt templates, `docs/` contains Pi-owned plans and runbooks, and `extensions/` contains the canonical sources of this repository's Pi extensions. `ae` links the root policy into the Pi agent directory only when selected; edit the repository source. Read the closest `AGENTS.md` before changing an extension.
- `harness/pi/subagents/` — owned reviewer definition, strict same-parent-model settings overlay, stdlib installer, and bounded review eval fixture. It is an atomic setup component, not a whole-directory install. Do not edit installed agents or the `pi-subagents` package as repository source.
- `prompts/` — system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current prompt resource, not a slash command.
- `skill-factory/` — skill authoring, validation, and evaluation resources. Read its closest `AGENTS.md` before editing.
- `tools/ae/` — `ae`, the installer that `./setup.sh` builds and runs. It owns harness detection and every install path.
- `tools/genie/` (binary `g`), `tools/ghh/`, `tools/gs/`, and `tools/gw/` — independent tool packages.
- Read each tool package's `AGENTS.md` before editing it.
- `tests/` — offline end-to-end tests of `setup.sh` and `ae` against a temporary `HOME`.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and executable.
- Respect nested `AGENTS.md` files; the closest file takes precedence.
- Keep skill behavior complete in source instructions and harness-neutral. Name a harness-specific tool only with a fallback ("if your harness supports X; otherwise ..."). Optional metadata or acceleration must retain a safe fallback when unavailable.
- When a public resource or tool contract changes, coordinate its documentation, `AGENTS.md`, and tests or eval fixtures that define the contract.
- Document all changes in the root `CHANGELOG.md` under `Unreleased` before pushing changes from this repository to `origin`.
- Prefer deterministic validation. Do not run live harness or model-backed evaluations without explicit approval.
- Setup contract, enforced by `ae` (see `tools/ae/README.md`):
  - Pickers start from what's installed; nothing new is queued until the user chooses it.
  - Every change is shown as a plan and applied only after confirmation. Cancelling changes nothing.
  - `ae` creates and removes only symlinks into this checkout. Anything else in the way is a conflict, replaced only after the user approves it, with files and directories backed up first.
  - Unselected installs and anything Æ doesn't own stay untouched.
  - Each selected harness loads one copy of a skill, taking the shared folders `~/.claude/skills` and `~/.agents/skills` into account.
  - Pi root files and directories such as `docs` are atomic choices.
- The `subagents` setup choice links only `agents/reviewer.md` and merges only `subagents.modelScope` into settings, with backups and JSON preflight. Preserve unrelated settings/agents; refuse symlinked settings. Native children use the active parent model unless the user explicitly approves an exception. Reviewer shell/test/browser capability does not authorize source fixes; Bash is not a sandbox. Verify effective project/provider overrides and selected skills before delegation.
- Pi extension sources live only in `harness/pi/extensions/`. `ae` links selected extensions into the Pi agent directory's `extensions/`; never treat the Pi agent directory as an extension source or edit through it as if it were a copy.
- Inspect `git status` and relevant diffs before editing. Stage exact intended paths, and verify the staged scope with `git diff --cached --name-status` before committing. Do not use broad reset commands as staging advice.

## Validation

Validate the installer offline with isolated install targets:

```sh
bash -n setup.sh
cargo test --locked --manifest-path tools/ae/Cargo.toml
python3 -m unittest discover -s tests -v
```

Never run `ae` or `./setup.sh` against the user's real harness folders to test a change. Use the tests' temporary `HOME`, or `ae ... --dry-run`.

Run repository Python tests from the root:

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

Validate one skill through the focused wrapper:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/<skill-name>
```
