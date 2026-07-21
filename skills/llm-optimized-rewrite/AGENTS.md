# llm-optimized-rewrite maintenance context

## Purpose

`llm-optimized-rewrite` guides agents through meaning-preserving compression of prompts, specs, commands, skills, and other technical prose. Maintain `SKILL.md` so agents preserve requirements, schemas, values, ambiguity, trigger behavior, and confirmation boundaries while using exact token counts.

## How the skill works

`SKILL.md` defines the agent workflow: read/snapshot file-backed text, identify rewrite opportunities by risk and savings, count exact snippets, present batch or individual review prompts, apply only confirmed edits, and finish with a diff summary. The bundled wrappers `scripts/smell_test.py` and `scripts/count_tokens.py` delegate to repo-level tools while working from downstream project directories.

## Eval and validation

Primary validation:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/llm-optimized-rewrite
```

Deterministic skill eval manifest: `evals/manifest.json`.

Legacy exploratory eval cases remain in `evals/evals.json`; do not treat them as the canonical `skill_valid` manifest unless intentionally migrating them into `evals/manifest.json`.

Before changing tool-facing behavior, smoke-test wrappers from a non-repo directory. Resolve `<repo-root>` to the package checkout and `<skill-dir>` to `<repo-root>/skills/llm-optimized-rewrite`:

```sh
cd /tmp
python3 <skill-dir>/scripts/smell_test.py <skill-dir>/SKILL.md
python3 <skill-dir>/scripts/count_tokens.py <<'TEXT'
hello world
TEXT
```

## Change guidelines

- Keep `SKILL.md` concise, procedural, and strict about preserving exact meaning and constraints.
- Keep confirmation options and review formats stable; evals depend on the batch confirmation contract.
- Prefer skill-local wrapper commands over `PYTHONPATH=skill-factory python3 -m tools...` in instructions that may run from downstream projects.
- Update `evals/manifest.json` when changing required workflow behavior.
- Update this `AGENTS.md` when adding or removing maintained resources, wrapper scripts, or eval files.
