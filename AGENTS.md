# AGENTS.md — agent resource context

This repository is a local agent-resource package. Pi is the only supported live harness; this repository owns its skills, commands, and extensions. Model providers used inside Pi, including the Kilo AI gateway, are separate from harness support.

## Directory map

- `skills/` — Pi agent skills. Read `skills/AGENTS.md` before changing a skill.
- `harness/pi/` — Pi-owned resources: `APPEND_SYSTEM.md` is the canonical root-agent policy, `commands/` contains Pi prompt templates, `docs/` contains Pi-owned plans and runbooks, and `extensions/` contains the canonical sources of this repository's Pi extensions. `./setup.sh` links the root policy into `~/.pi/agent/APPEND_SYSTEM.md` only when selected; edit the repository source. Read the closest `AGENTS.md` before changing an extension.
- `prompts/` — system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current prompt resource, not a slash command.
- `skill-factory/` — skill authoring, validation, and evaluation resources. Read its closest `AGENTS.md` before editing.
- `tools/ghh/`, `tools/gs/`, and `tools/gw/` — independent tool packages. Read each package's `AGENTS.md` before editing.
- `tests/` — offline `setup.sh` selection and installation tests.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and executable.
- Respect nested `AGENTS.md` files; the closest file takes precedence.
- Keep Pi skill behavior complete in source instructions. Optional metadata or acceleration must retain a safe fallback when unavailable.
- When a public resource or tool contract changes, coordinate its documentation, `AGENTS.md`, and tests or eval fixtures that define the contract.
- Document all changes in the root `CHANGELOG.md` under `Unreleased` before pushing changes from this repository to `origin`.
- Prefer deterministic validation. Do not run live harness or model-backed evaluations without explicit approval.
- Pi harness setup requires explicit component selection, then item selection for commands, extensions, and optional harness skills; root files and other directories such as `docs` are atomic choices. Nothing is selected by default. Confirm the complete selected plan before linking; cancelling any Pi picker cancels that Pi plan. Leave unselected installs untouched.
- Pi extension sources live only in `harness/pi/extensions/`. `./setup.sh` links selected extensions into `~/.pi/agent/extensions/`; never treat the Pi agent directory as an extension source or edit through it as if it were a copy.
- Inspect `git status` and relevant diffs before editing. Stage exact intended paths, and verify the staged scope with `git diff --cached --name-status` before committing. Do not use broad reset commands as staging advice.

## Validation

Validate setup selection offline with isolated install targets:

```sh
bash -n setup.sh
python3 -m unittest discover -s tests -v
```

Run repository Python tests from the root:

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

Validate one skill through the focused wrapper:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/<skill-name>
```
