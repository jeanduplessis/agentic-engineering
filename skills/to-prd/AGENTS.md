# AGENTS.md — to-prd skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for turning existing conversation and codebase context into a
product requirements document, then recording the approved PRD as a parent beads epic.

## How the skill works

`SKILL.md` tells the assistant to gather only already-available context, identify the likely implementation
shape, briefly confirm architecture and test focus, draft a durable product-focused PRD, and create a beads
task only after the user approves the PRD. The skill prefers beads (`bd`) over GitHub tracking, verifies `bd
--version` and `bd info` before task creation, and avoids silently initializing beads.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case force-loads `SKILL.md` and asks for a
PRD draft from supplied feature context without running commands or creating a beads task; deterministic
checks verify the PRD headings and user-story format.

Run the full validation wrapper from the repository root:

```sh
./tools/skill_valid/skill_validate.sh skills/to-prd
```

This invokes `tools.skill_valid` and may run live Pi/model gates when deterministic prerequisites pass.

## Change guidelines

- Keep `SKILL.md` focused on PRD synthesis and approved beads epic creation, not general project planning or task breakdown.

- Preserve the rule to avoid a requirements interview; use existing context and ask only narrow confirmation questions about architecture or testing choices.

- Preserve approval before beads creation, and keep `bd` availability checks before any task write.

- Keep PRDs product-focused and durable; avoid file paths, code snippets, and transient implementation details.

- Update `evals/manifest.json` when the PRD template, approval behavior, or beads-creation contract changes.

- Prefer deterministic eval checks for stable PRD structure and safety behavior; avoid checks that require exact prose.
