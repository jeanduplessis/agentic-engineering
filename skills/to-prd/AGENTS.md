# AGENTS.md — to-prd skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for turning existing conversation and codebase context into a
product requirements document, then recording the approved PRD as a parent beads epic.

## How the skill works

`SKILL.md` tells the assistant to gather only already-available context, identify the likely implementation
shape, draft a durable product-focused PRD, and record the approved PRD as a beads epic. The skill uses
beads_rust (`br`) for epic creation, asks how to proceed when `br` is unavailable or no beads database exists,
and avoids silently initializing beads.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case force-loads `SKILL.md` and asks for a
PRD draft from supplied feature context without running commands or creating a beads epic; deterministic
checks verify the PRD headings and user-story format.

Run the full validation wrapper from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/to-prd
```

This invokes deterministic `tools.skill_valid`; pass `--allow-live` and select a supported harness only with explicit approval.

## Change guidelines

- Keep `SKILL.md` focused on PRD synthesis and approved beads epic creation, not general project planning or task breakdown.

- Preserve the rule to avoid a requirements interview; use existing context and ask only narrow architectural confirmation questions.

- Preserve approved PRD creation as a beads epic, and keep the fallback path for unavailable `br` or missing beads databases.

- Keep PRDs product-focused and durable; avoid file paths, code snippets, and transient implementation details.

- Update `evals/manifest.json` when the PRD template, approval behavior, or beads-creation contract changes.

- Prefer deterministic eval checks for stable PRD structure and safety behavior; avoid checks that require exact prose.
