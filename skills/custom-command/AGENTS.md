# AGENTS.md — custom-command skill maintenance

## Purpose

Maintain `SKILL.md` as command-authoring guidance. Distinguish this repository's Pi-owned source from Pi project/global one-offs.

## How the skill works

- Default commands owned by this repo to `harness/pi/commands/<name>.md`.
- Use only metadata supported by the selected Pi template or extension; the body must preserve baseline behavior.
- Require explicit body instruction to load/follow skills whenever `skill` or `skills` metadata appears.
- Restrict repository sources to `$ARGUMENTS` and simple positional placeholders; reject `$@` and slicing.
- Recommend root package discovery for repository templates and native Pi prompt locations for project/global one-offs.
- Allow native Pi argument syntax only for clearly labeled Pi-local one-offs; repository templates retain the narrower validator contract.

## Eval and validation

`evals/manifest.json` declares workflow, trigger, and capability suites. Workflow cases come from `evals/evals.json`; `evals/grader.py` grades generated commands for canonical ownership, Pi metadata, explicit skill loading, repository placeholders, absence of legacy pre-expansion, and symlink activation guidance.

Run deterministic checks from repo root:

```sh
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow --results /tmp/custom-command-eval --require-real
PYTHONPATH=skill-factory python3 -m tools.llm_optimal_check skills/custom-command/SKILL.md
```

No-live `--require-real` run must skip honestly. Run live harness eval only with explicit approval.
Trigger suites now support Pi-only natural discovery; capability remains unsupported. Before live trigger evaluation,
provide a failing-test fixture for the negative case so it measures selection on an executable task.

## Change guidelines

- Change files only within `skills/custom-command/` unless user expands scope.
- Keep Pi scope and discovery explicit; do not imply that bare Pi applies extension-only metadata.
- Update `evals/evals.json` and `evals/grader.py` together when changing command-output contract.
- Keep `evals/manifest.json` aligned with skill name and eval assets.
- Keep examples behavior-complete without metadata injection, shell pre-expansion, implicit file inclusion, or generated variants.
- Prefer concise executable instructions.
