# AGENTS.md — context skill maintenance

## Purpose

Maintain `SKILL.md` as the workflow for creating and updating `CONTEXT.md`: the local agent-facing domain language and context map. The skill replaces the former `agent-lexicon` / `AGENT_LEXICON.md` contract while preserving the core behavior of canonical terminology, ambiguity detection, and concise agent rules.

## How the skill works

`SKILL.md` tells the assistant to scan conversation context, existing `CONTEXT.md`, legacy `AGENT_LEXICON.md`, legacy `CONTEXT-MAP.md`, and relevant ADRs for behaviorally important domain terms, context ownership, boundaries, relationships, synonyms, and overloaded terms. It rewrites `CONTEXT.md`, keeps ADRs separate but referenced, and adds a short `AGENTS.md` pointer when one exists.

Preserve core behavior when editing: agent-facing definitions, opinionated canonical terms, avoided aliases, explicit ambiguity decisions, execution-relevant relationships, context ownership/boundary mapping, full rewrites on rerun, and a short `AGENTS.md` pointer without duplicating the context contract.

## Eval and validation

`evals/manifest.json` defines the forced workflow evaluation for this skill. It loads `SKILL.md`, copies `evals/fixtures/project`, provides a SaaS billing-domain conversation, and expects the assistant to create `CONTEXT.md` and update the existing fixture `AGENTS.md` domain-context pointer.

`evals/grader.py` is the skill-local deterministic grader. It checks that `CONTEXT.md` exists, has the required headings and canonical table shape, includes core domain terms, flags the overloaded word "account", includes agent-facing rules, and keeps the `AGENTS.md` pointer short.

Run deterministic validation from the repository root:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/context
```

Run live harness validation only with explicit approval:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/context --allow-live --harness kilo
```

## Change guidelines

- Keep `SKILL.md` compact and directly executable; avoid tutorial prose.
- Keep `CONTEXT.md` agent-facing, not human-facing product docs or implementation docs.
- Keep ADRs separate; reference them only when they constrain terminology, ownership, boundaries, or agent behavior.
- Preserve migration from legacy `AGENT_LEXICON.md` and `CONTEXT-MAP.md` inputs.
- Update `evals/manifest.json` and `evals/grader.py` when the public artifact contract changes.
- Keep eval checks deterministic and focused on externally visible artifacts, especially `CONTEXT.md` and the `AGENTS.md` domain-context pointer.
