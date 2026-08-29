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

- Trigger suites execute only through Pi in natural mode, using a frozen target-only, read-only profile and trace-based grading. Capability suites remain explicitly unsupported.

- Suite-local configurations override manifest profiles. Trigger defaults are discovery-only; never infer avoidance from a without-skill control.

- Real harness adapters are Pi (`harness: "pi"`) and OpenCode-compatible Kilo (`harness: "kilo"`). Live
  execution must be gated by `allow_live: true`, `--allow-live`, or `SKILL_EVAL_ALLOW_LIVE=1`; Pi-specific
  opt-ins remain backwards-compatible aliases.

## Important contracts

- Do not fake real outputs. If live execution is unavailable, skip honestly.

- Trigger activation requires a successful non-empty target read. Avoidance requires no target-read attempt and a complete valid trace; missing catalog or execution evidence is not a pass. Failed positive reads are not graded, while negative read attempts are false positives.

- Keep raw Pi events, separate `observer-context.jsonl` catalog evidence, all assistant text, observed model identity, and frozen input hashes. Pi redirects extension stdout; never depend on it for observer records or infer catalog exposure from stderr. Reject result-directory reuse and trigger-to-workflow regression promotion. Do not serialize config environment values.

- Explicit provider extensions are trusted code; the read boundary is not an OS sandbox. Do not expose ambient skills, prompts, context files, or unrestricted tools.

- Process failures are not content failures. Timeouts/nonzero exits should produce `status: "process_failed"`, `grade.status: "not_graded"`, and `passed: null`.

- Static/replay configs must be rejected when `require_real=True` / `--require-real` is used.

- Relative manifest paths are resolved from the manifest directory, including skill paths, custom graders,
  legacy eval files, and copy fixtures. If promotion writes a manifest to a different directory, rewrite those
  relative paths for the new location.

- Keep result bundle JSON machine-readable and stable unless tests/docs are updated in the same change.

## Where things live

- `manifest.py`: manifest dataclasses and loader.

- `runner.py`: suite execution, harness dispatch, trace bundle writing.

- `grading.py`: generic deterministic response checks and custom-grader loading.

- `trigger.py`: trigger contract validation, frozen inputs, Pi observation parsing, and selection grading.

- `harness/pi/extensions/skill-eval-observer/`: CLI-only catalog observer and read boundary (canonical source at repo root).

- `reporting.py`: benchmark JSON and Markdown report rendering.

- `regression.py`: promotion of failed real runs into regression cases.

- `sandbox.py`: isolated per-run fixture workspaces.

- `tools/skill_eval/tests/test_skill_eval.py`: framework and custom-command vertical-slice coverage (`tools.skill_eval.tests.test_skill_eval`).

- `README.md`: user-facing overview, commands, and trust criteria.

## Validation

Run after changes:

```bash
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval tools.skill_eval.tests.test_trigger -v
node --test harness/pi/extensions/skill-eval-observer/tests/observer.test.mjs
```

For live behavioral validation, only when explicitly requested or approved:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval <manifest> workflow --results <dir> --require-real --allow-live
```
