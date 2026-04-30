# AGENTS.md — shared agent tooling context

This repository (`~/.agents`) is a shared home for agentic coding harness resources: installable skills, reusable custom commands/prompts, and repo-level tooling that supports skill validation and evaluation.

## Compatibility goals

Aim for portable behavior across:

1. Common public conventions, especially the Agent Skills specification: https://agentskills.io/specification
2. OpenCode: https://opencode.ai/docs/
3. Pi: https://pi.dev/docs

When compatibility conflicts arise, prefer the smallest shared subset and document any agent-specific behavior explicitly in the file or directory that needs it.

## Directory map

- `skills/` — installable agent skills. Read `skills/AGENTS.md` before adding or changing skills.
- `commands/` — Markdown custom commands intended to stay broadly compatible across supported agents.
- `prompts/` — reusable prompt/system fragments.
- `tools/` — Python tooling for token counting, LLM-optimization checks, skill evals, and skill validation. Read `tools/AGENTS.md` and any tool-local `AGENTS.md` before editing.
- `.beads/` — local beads task state; do not hand-edit unless you are intentionally maintaining task metadata.

## Working conventions

- Keep LLM-facing Markdown concise, explicit, and easy to execute. Avoid clever indirection when direct instructions work.
- Preserve cross-agent portability for skills, commands, and prompts unless the user specifically asks for an agent-specific feature.
- Prefer repo-level shared tools over one-off scripts. If a public tool contract changes, update its README, `AGENTS.md`, and tests together.
- Use deterministic validation by default. Do not run live Pi/model-backed evals unless the user explicitly requests or approves them.
- Respect nested `AGENTS.md` files; the closest one to the files being changed has the most specific guidance.

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
