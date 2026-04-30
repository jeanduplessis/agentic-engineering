# Skill eval framework

## Overview

`tools.skill_eval` is the repo-level runner for skill behavior evaluations. It loads skill-owned manifest files, runs each eval case in an isolated sandbox, captures trace artifacts, grades deterministic checks, compares configurations such as `with_skill` and `without_skill`, and writes human/machine-readable reports.

Use it for behavioral evidence from real agent runs. Static and replay harnesses are useful for smoke tests, but they are synthetic and must not be treated as skill-quality benchmarks.

## Quick usage

Run the custom-command workflow suite without live Pi enabled. Because the manifest defaults to the real Pi harness, these runs should be honestly skipped rather than faked:

```bash
python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow \
  --results /tmp/custom-command-real-validation \
  --require-real
```

Run a live Pi evaluation:

```bash
SKILL_EVAL_ALLOW_LIVE_PI=1 \
python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow \
  --results /tmp/custom-command-real \
  --require-real
```

Run unit tests for the framework:

```bash
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
```

Promote confirmed real failures into regression cases:

```bash
python3 -m tools.skill_eval promote-regressions \
  skills/custom-command/evals/manifest.json \
  --results /tmp/custom-command-real \
  --output skills/custom-command/evals/manifest.json \
  --source-bead agents-1cs.7
```

## Concepts

- **manifest suites**: each skill owns an eval manifest under its skill directory. Current executable suite types are `workflow` and `regression`. `trigger` and `capability` suites may be represented in manifests, but the runner reports them as unsupported until those harnesses exist.
- **harness modes**: `static` emits configured text for plumbing smoke tests; `replay` reuses prior captured output; `real` invokes an agent harness such as Pi. Static/replay outputs are synthetic.
- **configurations**: named execution variants such as `with_skill` and `without_skill`. For Pi, `with_skill` force-loads the target skill with `--skill`; `without_skill` runs with `--no-skills` and omits the target skill.
- **grading**: each run writes `grade.json`. Declarative deterministic checks run first; optional skill-local graders can inspect response text and generated artifacts. Legacy prose expectations should remain rubric/context, not literal required output.
- **traces and artifacts**: each run writes `raw_output.json`, `events.jsonl`, `response.md`, `timing.json`, `usage.json`, `metadata.json`, `artifact_manifest.json`, and `workspace_diff.txt`.

## Manifest shape

Minimal manifest:

```json
{
  "schema_version": 1,
  "skill": {"name": "demo", "path": "../SKILL.md"},
  "suites": [
    {
      "name": "workflow",
      "type": "workflow",
      "fixture": {"type": "empty"},
      "cases": [
        {
          "id": "hello",
          "prompt": "Say hello",
          "checks": [{"id": "contains-hello", "type": "required_content", "value": "hello"}]
        }
      ]
    }
  ],
  "configurations": {
    "with_skill": {"harness": "pi", "force_skill": true},
    "without_skill": {"harness": "pi", "force_skill": false}
  }
}
```

Relative `skill.path`, suite `custom_grader`, `legacy_evals`, and copy-fixture paths are resolved relative to the manifest file.

## Harnesses

### Static smoke

Use static smoke when changing framework plumbing and you need a quick schema/trace/report check without a live model. If a manifest defaults to real Pi configs, pass explicit static configs from Python tests or a wrapper.

Static smoke results are labeled synthetic in `summary.json`, `benchmark.json`, per-run `metadata.json`, and `report.md`. Do not compare skill versions with static smoke metrics.

### Real Pi

The Pi harness runs non-interactively with isolation flags:

```text
pi --no-session --no-context-files --no-extensions --no-prompt-templates --no-skills [--skill <skill>] -p <prompt>
```

Live Pi execution is gated. Enable it with either config `allow_live: true` or the environment variable `SKILL_EVAL_ALLOW_LIVE_PI=1`. If Pi credentials, provider config, or the executable are unavailable, runs are skipped or marked as process failures rather than faking outputs.

Use `--require-real` for benchmark-quality runs. It rejects static/replay configurations before execution.

For tests or CI, use a fake Pi executable in configuration. The unit suite validates command construction, `with_skill`/`without_skill`, process failures, and trace bundle shape without calling a live model.

## Reading results

Start with `report.md`, then inspect per-run artifacts:

- `benchmark.json`: configuration totals, pass rates, failed/not-graded counts, status counts, harness mode, synthetic flag, model/provider, metric provenance, and comparison caveats.
- `report.md`: human summary; warns when synthetic/replay metrics are present and explains token/character-count provenance.
- `metadata.json`: manifest version/path, suite/case/configuration, sandbox path, harness contract, loaded skill paths, model/provider.
- `raw_output.json`: process stdout/stderr, exit code, command, skip reason, and raw harness details.
- `events.jsonl`: normalized run/session events currently covering start, harness finish, and run finish.
- `artifact_manifest.json` and `workspace_diff.txt`: files created/modified/deleted inside the sandbox.
- `grade.json`: deterministic and optional judge outcomes.

Process failures are not graded as content failures. Timeouts and nonzero harness exits get run status `process_failed`, `grade.status` of `not_graded`, and `passed: null`.

Token metrics are unavailable unless the harness reports provider token usage. The framework currently records character counts separately; do not treat them as tokens.

A result is trustworthy enough to compare skill versions only when all of these are true:

1. Compared configurations use `real` harness mode and `--require-real` was used.
2. Runs are not skipped or process-failed, or those outcomes are explicitly separated from content grades.
3. `response.md` contains generated agent output, not expected prose or prompt echoes.
4. Grading checks generated artifacts/contracts, not literal legacy expectation sentences.
5. `benchmark.json` shows comparable harness modes and no synthetic/replay caveat.
6. Trace artifacts are sufficient for a reviewer to explain failures.

## Regression workflow

`promote-regressions` reads failed, non-skipped, real runs from a result bundle and appends them to the manifest's `regression` suite. Promoted cases preserve the loaded source prompt/checks, including cases loaded through `legacy_evals`, plus `source_run_id`, `trace_path`, `failure_summary`, source suite/case/configuration, harness mode, and optional source bead. If `--output` writes the manifest to a different directory, relative manifest paths are rewritten so skill paths, graders, legacy eval files, and copy fixtures still resolve.

Regression suites run through the same case runner as workflow suites. After triage and skill fixes, run the `regression` suite with real harness configs to guard against backslides.

## Development notes

- Keep generic framework behavior in `tools/skill_eval/*`.
- Put domain-specific grading in the skill's eval directory, e.g. `skills/custom-command/evals/grader.py`.
- Prefer deterministic checks. LLM judge metadata is represented, but judge execution is intentionally not implemented yet.
- Update this README and `tools/skill_eval/AGENTS.md` when changing harness contracts, result bundle shape, suite support, or trust criteria.
