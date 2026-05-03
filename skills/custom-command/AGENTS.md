# AGENTS.md — custom-command skill maintenance

## Purpose

Maintain `SKILL.md` as the Pi prompt-template authoring and migration guide. Optimize for Pi slash commands, prompt-template discovery, argument placeholders, and legacy syntax cleanup.

## How the skill works

`SKILL.md` defines Pi template locations, frontmatter, argument placeholders, migration rules, naming rules, output format, checklist, and examples. Keep the default path Pi-native: `description`, optional `argument-hint`, Markdown body text, `$ARGUMENTS`/`$@`/`$1`/slicing, and flat kebab-case `.md` filenames.

## Eval and validation

`evals/manifest.json` declares workflow, trigger, and capability suites. Workflow cases come from `evals/evals.json`; `evals/grader.py` grades generated Pi templates for filenames, frontmatter, supported placeholders, absence of legacy pre-expansion, and Pi install/discovery guidance.

Run deterministic tests from the repo root after changes:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
```

Run the full local validity wrapper only with live Pi/model execution approval:

```sh
./tools/skill_valid/skill_validate.sh skills/custom-command
```

## Change guidelines

- Keep the skill Pi-only unless the repo-wide contract changes.
- Update `evals/evals.json`, `evals/grader.py`, and `tools/skill_eval/tests/test_skill_eval.py` when changing expected prompt-template output, migration rules, or checklist behavior.
- Keep `evals/manifest.json` aligned with the skill name and eval assets when adding or removing suites.
- Keep examples Pi-native and executable without hidden pre-expansion.
- Prefer concise direct instructions to broad commentary agents cannot execute.
