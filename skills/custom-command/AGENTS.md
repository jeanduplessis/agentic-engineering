# AGENTS.md — custom-command skill maintenance

## Purpose

Maintain `SKILL.md` as command-authoring guidance. Distinguish this repository's Pi-owned source from downstream shared commands and harness-local one-offs.

## How the skill works

- Default commands owned by this repo to `harness/pi/commands/<name>.md`.
- Permit harness-specific metadata only when every other target safely ignores it and body preserves baseline behavior.
- Require explicit body instruction to load/follow skills whenever `skill` or `skills` metadata appears.
- Restrict shared sources to `$ARGUMENTS` and simple positional placeholders; reject `$@` and slicing.
- Do not claim this repository activates OpenCode/Kilo commands. Recommend root package discovery for Pi-owned templates and target-harness documentation for other commands.
- Allow native harness-specific syntax only for clearly labeled harness-local one-offs.

## Eval and validation

`evals/manifest.json` declares workflow, trigger, and capability suites. Workflow cases come from `evals/evals.json`; `evals/grader.py` grades generated commands for canonical ownership, portable metadata, explicit skill loading, shared placeholders, absence of legacy pre-expansion, and symlink activation guidance.

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
- Keep shared guidance compatible with both Pi and OpenCode; do not infer portability from one harness accepting syntax.
- Update `evals/evals.json` and `evals/grader.py` together when changing command-output contract.
- Keep `evals/manifest.json` aligned with skill name and eval assets.
- Keep examples behavior-complete without metadata injection, shell pre-expansion, implicit file inclusion, or generated variants.
- Prefer concise executable instructions.
