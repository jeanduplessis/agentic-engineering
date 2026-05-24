# AGENTS.md — to-epic skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for turning existing conversation and codebase context into a product requirements document, then recording the approved PRD as a parent `ait` epic.

## How the skill works

`SKILL.md` tells the assistant to gather available context, identify the likely implementation shape, draft a durable product-focused PRD, and record the approved PRD as an `ait` epic. The skill delegates CLI rules to `ait-cli`, uses `ait --actor agent create --stdin`, asks how to proceed when `ait` is unavailable or no `.ait/` project exists, and avoids silently initializing ait.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case force-loads `SKILL.md` and asks for a PRD draft from supplied feature context without running commands or creating an `ait` epic; deterministic checks verify the PRD headings, user-story format, and `ait` terminology.

Run deterministic validation from the repository root when changing this skill:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m tools.skill_eval skills/to-epic/evals/manifest.json workflow --results /tmp/to-epic-eval --require-real
```

Run live Pi validation only with explicit approval.

## Change guidelines

- Keep `SKILL.md` focused on PRD synthesis and approved `ait` epic creation, not general project planning or task breakdown.
- Preserve the rule to avoid a requirements interview; use existing context and ask only narrow architectural confirmation questions.
- Preserve approved PRD creation as an `ait` epic, and keep the fallback path for unavailable `ait` or missing `.ait/` projects.
- Keep PRDs product-focused and durable; avoid file paths, code snippets, and transient implementation details.
- Update `evals/manifest.json` when the PRD template, approval behavior, or `ait` creation contract changes.
- Prefer deterministic eval checks for stable PRD structure and safety behavior; avoid checks that require exact prose.
