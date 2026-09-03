# AGENTS.md — epic-orchestrate skill

## Purpose

Maintains Pi `/epic-orchestrate` orchestration: parent-controlled ait epic implementation through formal gates, durable state, strict lifecycle ownership, and recovery behavior. Preserve sequential current-session fallback when optional runners are unavailable.

## How the skill works

- `SKILL.md` contains the trigger description and executable workflow.
- `references/gate-contracts.md` defines gate executor permissions and pass criteria.
- `references/orchestration-protocol.md` defines gate execution fallback, queue, lifecycle, commit, and final epic rules.
- `references/failure-recovery.md` captures resume and known failure handling.
- `evals/manifest.json`, `evals/evals.json`, and `evals/grader.py` cover deterministic workflow contracts.

## Eval and validation

Use deterministic checks by default:

```sh
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/epic-orchestrate/evals/manifest.json workflow --results /tmp/epic-orchestrate-eval --require-real
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/epic-orchestrate
```

The `tools.skill_eval` run may skip when its configured live harness is unavailable. Do not run live model-backed evals without explicit user approval.

## Change guidelines

- Preserve parent-only issue lifecycle, closure, and commit ownership.
- Preserve gate executor no-stage/no-commit/no-close/no-update rules.
- Preserve ait CLI-only mutation; never direct-edit `.ait/` files.
- Keep native subagent/current harness runner support optional and preserve complete sequential current-session fallback.
- Keep Pi self-invocation optional; preserve current-session execution.
- Resolve this repository's `harness/pi/commands/<name>.md` first; keep Pi project/global prompt locations optional.
- Preserve append-only resume state.
- Preserve generated-script preflight (`bash -n` plus compatibility checks).
- Preserve invariant validation coverage for invalidating mutation paths.
- Keep references concise; move details from `SKILL.md` only when it improves execution reliability.
