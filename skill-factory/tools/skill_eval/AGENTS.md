# AGENTS.md — skill_eval context

This directory contains the repo-level skill evaluation framework. Keep it small, deterministic by default,
and explicit about whether results are synthetic or real.

## Design intent

- Run skill-owned eval manifests through one central runner.

- Capture enough evidence for human review: raw output, response, timing, usage placeholders, metadata,
  artifacts, workspace diff, events, grade, benchmark, and report.

- Compare named configurations such as `with_skill` and `without_skill` without hiding caveats.

- Treat static and replay harnesses as synthetic. They are for smoke/plumbing checks, not behavioral skill-quality claims.

- Use real harness runs, plus `--require-real`, for benchmark-quality evidence.

## Current execution support

- Workflow suites run through the normal case runner.

- Regression suites run through the same case runner as workflow suites.

- Trigger and capability suites may be represented in manifests, but execution is currently unsupported and should return an explicit unsupported summary.

- Real harness adapters are Pi (`harness: "pi"`) and OpenCode-compatible Kilo (`harness: "kilo"`). Live
  execution must be gated by `allow_live: true`, `--allow-live`, or `SKILL_EVAL_ALLOW_LIVE=1`; Pi-specific
  opt-ins remain backwards-compatible aliases.

## Important contracts

- Do not fake real outputs. If live execution is unavailable, skip honestly.

- Process failures are not content failures. Timeouts/nonzero exits should produce `status: "process_failed"`, `grade.status: "not_graded"`, and `passed: null`.

- Static/replay configs must be rejected when `require_real=True` / `--require-real` is used.

- Relative manifest paths are resolved from the manifest directory, including skill paths, custom graders,
  legacy eval files, and copy fixtures. If promotion writes a manifest to a different directory, rewrite those
  relative paths for the new location.

- Keep result bundle JSON machine-readable and stable unless tests/docs are updated in the same change.

## Where things live

- `manifest.py`: manifest dataclasses and loader.

- `runner.py`: suite execution, harness dispatch, trace bundle writing.

- `grading.py`: generic deterministic checks and custom-grader loading.

- `reporting.py`: benchmark JSON and Markdown report rendering.

- `regression.py`: promotion of failed real runs into regression cases.

- `sandbox.py`: isolated per-run fixture workspaces.

- `tools/skill_eval/tests/test_skill_eval.py`: framework and custom-command vertical-slice coverage (`tools.skill_eval.tests.test_skill_eval`).

- `README.md`: user-facing overview, commands, and trust criteria.

## Validation

Run after changes:

```bash
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
```

For live behavioral validation, only when explicitly requested or approved:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval <manifest> workflow --results <dir> --require-real --allow-live
```
