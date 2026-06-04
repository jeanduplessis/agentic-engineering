# AGENTS.md — custom-command skill maintenance

## Purpose

Maintain `SKILL.md` as shared Pi/OpenCode command-authoring guidance. Optimize for one canonical shared source, portable baseline behavior, explicit body skill loading, safe placeholders, and symlink activation. Keep harness-local one-offs distinct from shared repo commands.

## How the skill works

- Default commands owned by this repo to canonical `commands/<name>.md` shared sources.
- Permit harness-specific metadata only when every other target safely ignores it and body preserves baseline behavior.
- Require explicit body instruction to load/follow skills whenever `skill` or `skills` metadata appears.
- Restrict shared sources to `$ARGUMENTS` and simple positional placeholders; reject `$@` and slicing.
- Prohibit built, generated, copied, or hand-synchronized harness variants; recommend package discovery or symlinks.
- Allow native harness-specific syntax only for clearly labeled harness-local one-offs.

## Eval and validation

`evals/manifest.json` declares workflow, trigger, and capability suites. Workflow cases come from `evals/evals.json`; `evals/grader.py` grades generated commands for canonical ownership, portable metadata, explicit skill loading, shared placeholders, absence of legacy pre-expansion, and symlink activation guidance.

Run deterministic checks from repo root:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow --results /tmp/custom-command-eval --require-real
python3 -m tools.llm_optimal_check skills/custom-command/SKILL.md
```

No-live `--require-real` run must skip honestly. Run live harness eval only with explicit approval.

## Change guidelines

- Change files only within `skills/custom-command/` unless user expands scope.
- Keep shared guidance compatible with both Pi and OpenCode; do not infer portability from one harness accepting syntax.
- Update `evals/evals.json` and `evals/grader.py` together when changing command-output contract.
- Keep `evals/manifest.json` aligned with skill name and eval assets.
- Keep examples behavior-complete without metadata injection, shell pre-expansion, implicit file inclusion, or generated variants.
- Prefer concise executable instructions.
