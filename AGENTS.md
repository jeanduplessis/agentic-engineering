# AGENTS.md — agent resource context

This repository is a local agent-resource package. Skills are shared across supported harnesses; Pi commands are owned only by this repository's Pi harness.

## Directory map

- `skills/` — shared-harness agent skills. Read `skills/AGENTS.md` before changing a skill.
- `harness/pi/` — Pi-owned resources: `commands/` contains Pi prompt templates and `extensions/` contains Pi extensions. Read the closest `AGENTS.md` before changing an extension.
- `prompts/` — system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current prompt resource, not a slash command.
- `skill-factory/` — skill authoring, validation, and evaluation resources. Read its closest `AGENTS.md` before editing.
- `tools/ghh/`, `tools/gs/`, and `tools/gw/` — independent tool packages. Read each package's `AGENTS.md` before editing.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and executable.
- Respect nested `AGENTS.md` files; the closest file takes precedence.
- Preserve equivalent shared-skill behavior across Pi and OpenCode-compatible harnesses. Harness-specific metadata or acceleration must be safely ignorable and have a complete shared fallback.
- When a public resource or tool contract changes, coordinate its documentation, `AGENTS.md`, and tests or eval fixtures that define the contract.
- Prefer deterministic validation. Do not run live harness or model-backed evaluations without explicit approval.
- Inspect `git status` and relevant diffs before editing. Stage exact intended paths, and verify the staged scope with `git diff --cached --name-status` before committing. Do not use broad reset commands as staging advice.

## Validation

Run repository Python tests from the root:

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

Validate one skill through the focused wrapper:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/<skill-name>
```
