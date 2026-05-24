# AGENTS.md — epic-implement skill

## Purpose

Maintains the Pi skill for `/epic-implement` orchestration: parent-controlled beads epic implementation through child Pi gates, durable state, strict closure ownership, and recovery behavior.

## How the skill works

- `SKILL.md` contains the trigger description and executable workflow.
- `references/gate-contracts.md` defines child gate permissions and pass criteria.
- `references/orchestration-protocol.md` defines queue, closure, commit, and final epic rules.
- `references/failure-recovery.md` captures resume and known failure handling.
- `evals/manifest.json`, `evals/evals.json`, and `evals/grader.py` cover deterministic workflow contracts.

## Eval and validation

Use deterministic checks by default:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m tools.skill_eval skills/epic-implement/evals/manifest.json workflow --results /tmp/epic-implement-eval --require-real
python3 -m tools.skill_valid skills/epic-implement
```

The `tools.skill_eval` run should skip honestly unless live Pi is approved. Run live Pi evals only with explicit user approval.

## Change guidelines

- Preserve parent-only bead closure.
- Preserve child gate no-stage/no-commit/no-close rules.
- Preserve append-only resume state.
- Preserve generated-script preflight (`bash -n` plus compatibility checks).
- Preserve invariant validation coverage for invalidating mutation paths.
- Keep references concise; move details from `SKILL.md` only when it improves execution reliability.
