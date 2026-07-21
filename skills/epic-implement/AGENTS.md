# AGENTS.md — epic-implement skill

## Purpose

Maintains harness-neutral `/epic-implement` orchestration: parent-controlled beads epic implementation through formal gates, durable state, strict closure ownership, and recovery behavior. Pi and OpenCode/Kilo must work; no specific harness may be required.

## How the skill works

- `SKILL.md` contains the trigger description and executable workflow.
- `references/gate-contracts.md` defines gate executor permissions and pass criteria.
- `references/orchestration-protocol.md` defines gate execution fallback, queue, closure, commit, and final epic rules.
- `references/failure-recovery.md` captures resume and known failure handling.
- `evals/manifest.json`, `evals/evals.json`, and `evals/grader.py` cover deterministic workflow contracts.

## Eval and validation

Use deterministic checks by default:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/epic-implement/evals/manifest.json workflow --results /tmp/epic-implement-eval --require-real
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/epic-implement
```

The `tools.skill_eval` run may skip when its configured live harness is unavailable. Do not run live model-backed evals without explicit user approval.

## Change guidelines

- Preserve parent-only bead closure and commit ownership.
- Preserve gate executor no-stage/no-commit/no-close rules.
- Keep native subagent/current harness runner support optional and preserve complete sequential current-session fallback.
- Never require Pi; Pi self-invocation may remain optional acceleration.
- Resolve this repository's `harness/pi/commands/<name>.md` first; keep arbitrary harness prompt locations optional.
- Preserve append-only resume state.
- Preserve generated-script preflight (`bash -n` plus compatibility checks).
- Preserve invariant validation coverage for invalidating mutation paths.
- Keep references concise; move details from `SKILL.md` only when it improves execution reliability.
