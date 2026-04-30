# AGENTS.md — agent-lexicon skill maintenance

## Purpose

Maintain `SKILL.md` as a compact workflow for extracting an agent-facing terminology contract from the current conversation. The skill should produce `AGENT_LEXICON.md`, choose canonical terms, flag ambiguity, and add a short terminology pointer to `AGENTS.md` when one exists.

## How the skill works

`SKILL.md` tells the assistant to scan conversation context for behaviorally important domain terms, detect synonyms and overloaded terms, choose one canonical term per concept, write operational agent rules, rewrite `AGENT_LEXICON.md`, and summarize terminology decisions inline.

Preserve the core behavior when editing: agent-facing definitions, opinionated canonical terms, avoided aliases, explicit ambiguity decisions, execution-relevant relationships, full rewrites on rerun, and a short `AGENTS.md` pointer without duplicating the lexicon.

## Eval and validation

`evals/manifest.json` defines the forced workflow evaluation for this skill. It loads `SKILL.md`, copies `evals/fixtures/project`, provides a SaaS billing-domain conversation, and expects the assistant to create `AGENT_LEXICON.md` and update the existing fixture `AGENTS.md` terminology pointer.

`evals/grader.py` is the skill-local deterministic grader. It checks that `AGENT_LEXICON.md` exists, has the required headings and canonical table shape, includes core domain terms, flags the overloaded word "account", and keeps the `AGENTS.md` pointer short.

Run the deterministic local validity gate before handing off changes:

```sh
python3 -m tools.skill_valid skills/agent-lexicon
```

Without live approval, this should pass deterministic gates and then report `live_opt_in` as not allowed.

Run live validation only with explicit approval:

```sh
python3 -m tools.skill_valid skills/agent-lexicon --allow-live-pi
```

## Change guidelines

- Keep `SKILL.md` concise and directly executable; avoid broad DDD theory unless it changes behavior.
- Update `evals/manifest.json` when the workflow prompt or expected behavior changes.
- Update `evals/grader.py` when the required output contract changes.
- Keep eval checks deterministic and focused on externally visible artifacts, especially `AGENT_LEXICON.md` and the `AGENTS.md` terminology pointer.
- Preserve cross-agent portability and the repo-wide skill conventions in `skills/AGENTS.md`.
