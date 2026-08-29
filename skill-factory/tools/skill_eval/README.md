# Skill eval framework

## Overview

`tools.skill_eval` is the repo-level runner for skill behavior evaluations. It loads skill-owned manifest
files, runs each eval case in an isolated sandbox, captures trace artifacts, grades deterministic checks,
compares configurations such as `with_skill` and `without_skill`, and writes human/machine-readable reports.

Use it for behavioral evidence from real agent runs. Static and replay harnesses are useful for smoke tests,
but they are synthetic and must not be treated as skill-quality benchmarks.

## Quick usage

Run the custom-command workflow suite without live Pi enabled. Because the manifest defaults to the real Pi
harness, these runs should be honestly skipped rather than faked:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow \
  --results /tmp/custom-command-real-validation \
  --require-real
```

Run a live evaluation through manifest-selected real harness:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/custom-command/evals/manifest.json workflow \
  --results /tmp/custom-command-real \
  --require-real \
  --allow-live
```

`SKILL_EVAL_ALLOW_LIVE=1` provides equivalent harness-neutral opt-in. `--allow-live-pi` and
`SKILL_EVAL_ALLOW_LIVE_PI=1` remain compatibility aliases.

Run unit tests for the framework:

```bash
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
```

Promote confirmed real failures into regression cases:

```bash
PYTHONPATH=skill-factory python3 -m tools.skill_eval promote-regressions \
  skills/custom-command/evals/manifest.json \
  --results /tmp/custom-command-real \
  --output skills/custom-command/evals/manifest.json \
  --source-bead agents-1cs.7
```

## Concepts

- **manifest suites**: each skill owns an eval manifest under its skill directory. Current executable suite
  types are `workflow`, `regression`, and Pi-only `trigger`. `capability` suites remain unsupported.

- **harness modes**: `static` emits configured text for plumbing smoke tests; `replay` reuses prior captured
  output; `real` invokes an agent harness such as Pi or OpenCode-compatible Kilo. Static/replay outputs are synthetic.

- **configurations**: named execution variants such as `with_skill` and `without_skill`. For Pi, the legacy
  `force_skill: true` flag advertises the target with `--skill`; it does not guarantee a body read.
  `without_skill` omits the target. Suite-local `configurations` override manifest-level profiles.
  Trigger suites default to `{"discovery": {"harness": "pi"}}`, never the with/without pair.

- **grading**: each run writes `grade.json`. Declarative deterministic checks run first; optional skill-local
  graders can inspect response text and generated artifacts. Legacy prose expectations should remain
  rubric/context, not literal required output.

- **traces and artifacts**: each run writes `raw_output.json`, `events.jsonl`, `response.md`, `timing.json`,
  `usage.json`, `metadata.json`, `artifact_manifest.json`, and `workspace_diff.txt`.

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

Use static smoke when changing framework plumbing and you need a quick schema/trace/report check without a
live model. If a manifest defaults to real Pi configs, pass explicit static configs from Python tests or a
wrapper.

Static smoke results are labeled synthetic in `summary.json`, `benchmark.json`, per-run `metadata.json`, and
`report.md`. Do not compare skill versions with static smoke metrics.

### Real Pi

The Pi harness runs non-interactively with isolation flags:

```text
pi --no-session --no-context-files --no-extensions --no-prompt-templates --no-skills [--skill <skill>] -p <prompt>
```

Live execution is gated. Enable it with config `allow_live: true`, CLI `--allow-live`, or environment variable
`SKILL_EVAL_ALLOW_LIVE=1`. Legacy Pi-specific opt-ins remain aliases. If credentials, provider config, or the
executable are unavailable, runs are skipped or marked as process failures rather than faking outputs.

### Real Kilo

The `kilo` harness uses OpenCode-compatible `kilo run --pure --format default`. Forced skills are attached with
`--file <SKILL.md>` and an explicit force-load instruction because Kilo/OpenCode exposes no Pi-style `--skill`
run flag. Provider and model become `--model provider/model`; thinking maps to `--variant`.

Use `--require-real` for benchmark-quality runs. It rejects static/replay configurations before execution.

For tests or CI, use a fake Pi executable in configuration. The unit suite validates command construction,
`with_skill`/`without_skill`, process failures, and trace bundle shape without calling a live model.

## Natural trigger evals (Pi only)

A trigger suite measures whether the agent selects the target for an ordinary task. The target is available
in both positive and negative cases. Do not force a skill command, attach its body, or tell the agent which
skill to choose. Cases must include the source text or copy fixture needed to perform the task.

```json
{
  "name": "trigger",
  "type": "trigger",
  "mode": "natural",
  "configurations": {"discovery": {"harness": "pi"}},
  "cases": [
    {"id": "yes", "prompt": "Draft an email requesting the worker logs by Friday.", "should_trigger": true},
    {"id": "no", "prompt": "Explain a cache miss in chat.", "should_trigger": false}
  ]
}
```

`should_trigger` is a required boolean. Optional `expected_skill` names the manifest target for positives;
negative cases use null or omit it. Response checks and custom graders belong in workflow suites instead.
`force_skill`, non-Pi harnesses, and synthetic/replay configurations are rejected for trigger execution.

```sh
# No model calls: validate the contract, snapshot inputs, and record skipped runs.
PYTHONPATH=skill-factory python3 -m tools.skill_eval skills/human-writing/evals/manifest.json trigger \
  --configuration discovery --results /tmp/human-writing-trigger-check --require-real
# Add --allow-live only after approving the case/configuration budget; use a fresh results path.
```

`--configuration NAME` is repeatable. Trigger profiles accept exact `provider`, `model`, and `thinking`
values, `executable`, `timeout_seconds` (default 120), `allow_live`, `env`, and optional `extensions`: local
provider-extension entry points resolved relative to the manifest. Explicit extensions are trusted code;
no extension discovery or package installation is enabled. Native Kilo CLI trigger execution is not supported.

The `pi-target-only-read-v1` profile:

- Snapshots the target `SKILL.md`, case prompts, and fixture before the first process. Skill helper files are
  not exposed. This tests discovery and an initial read, not completion of arbitrary skill workflows.
- Uses Pi's normal discovery instructions, JSON mode, only the built-in `read` tool, no saved session,
  no context files, no project trust, no ambient skills/extensions/templates, and no local/global system
  prompt overrides. Authentication and model configuration still come from the normal Pi environment.
- Loads the repo-owned `skill-eval-observer` extension explicitly. It records the rendered catalog and
  observed model/tools without logging private system instructions. Reads outside the fixture and frozen
  target are blocked, including symlink escapes. This is not an OS sandbox for trusted extensions.
- Correlates assistant tool requests, read starts, read completions, and tool-result messages. All assistant
  text is retained separately from thinking/tool results. A successful non-empty read is the activation
  proxy; it does not establish that all instructions were read or followed.
- Requires one complete, error-free agent run and a verified target-only catalog. Retries, assistant errors,
  truncated responses, missing events, changed inputs, or profile mismatches are not graded as avoidance.
  A failed target read is a loading error for a positive case and a false positive for a negative case.

Do not use cases where the target `SKILL.md` itself is the document being edited or discussed: file access
would be ambiguous evidence of activation. The read-only, single-skill profile is deliberately narrower than
normal coding sessions; it does not measure competition among installed skills.

Trigger results require an empty/new directory. `plan.json` records the frozen hashes, profile, observer,
provider extension hashes, and process-run count (cases × selected configurations). No runner retries or
regrading occur. Pi-internal retries invalidate the probe; the process count is not an API-request budget.
Set repetition/model budgets before running, use separate result directories, and retain original grades.

Each run also writes `pi-events.jsonl` (raw native JSON stream), `observer-context.jsonl` (separate catalog
observations), and `trigger.json` (validated observations). Pi redirects extension stdout to stderr, so the
observer writes directly to its sidecar; stderr is preserved as diagnostics, never parsed as catalog evidence.
Missing or malformed observer records invalidate the probe. Reports separate
activation, avoidance, misses, false positives, invalid runs, and loading errors. Activation/avoidance rates
exclude invalid runs and loading errors; an unavailable rate is null, not zero or success.

Trigger failure promotion is explicitly rejected: ordinary workflow regressions would lose natural
selection semantics. Retain the evidence and add a trigger case instead. `skill_valid --include-trigger`
adds this suite to validation; it still requires separate live opt-in before any model calls.

## Reading results

Start with `report.md`, then inspect per-run artifacts:

- `benchmark.json`: configuration totals, pass rates, failed/not-graded counts, status counts, harness mode,
  synthetic flag, model/provider, metric provenance, and comparison caveats.

- `report.md`: human summary; warns when synthetic/replay metrics are present and explains token/character-count provenance.

- `metadata.json`: manifest version/path, suite/case/configuration, sandbox path, harness contract, skill-path evidence, model/provider.
  Pi workflow runs record configured `skill_paths_advertised` and leave `skill_paths_loaded` empty because
  text-mode output cannot prove reads. Pi trigger runs populate both from observed evidence.

- `raw_output.json`: process stdout/stderr, exit code, command, skip reason, and raw harness details.

- `events.jsonl`: normalized run/session events covering start, harness finish, and run finish, plus target
  read attempts/completions for trigger runs. The complete Pi stream is retained in `pi-events.jsonl`.

- `artifact_manifest.json` and `workspace_diff.txt`: files created/modified/deleted inside the sandbox.

- `grade.json`: deterministic and optional judge outcomes.

Process failures are not graded as content failures. Timeouts and nonzero harness exits get run status
`process_failed`, `grade.status` of `not_graded`, and `passed: null`.

Token metrics are unavailable unless the harness reports provider token usage. The framework currently records
character counts separately; do not treat them as tokens.

A result is trustworthy enough to compare skill versions only when all of these are true:

1. Compared configurations use `real` harness mode and `--require-real` was used.

2. Runs are not skipped or process-failed, or those outcomes are explicitly separated from content grades.

3. `response.md` contains generated agent output, not expected prose or prompt echoes.

4. Grading checks generated artifacts/contracts, not literal legacy expectation sentences.

5. `benchmark.json` shows comparable harness modes and no synthetic/replay caveat.

6. Trace artifacts are sufficient for a reviewer to explain failures.

## Regression workflow

`promote-regressions` reads failed, non-skipped, real runs from a result bundle and appends them to the
manifest's `regression` suite. Promoted cases preserve the loaded source prompt/checks, including cases loaded
through `legacy_evals`, plus `source_run_id`, `trace_path`, `failure_summary`, source
suite/case/configuration, harness mode, and optional source bead. If `--output` writes the manifest to a
different directory, relative manifest paths are rewritten so skill paths, graders, legacy eval files, and
copy fixtures still resolve.

Regression suites run through the same case runner as workflow suites. After triage and skill fixes, run the
`regression` suite with real harness configs to guard against backslides.

## Development notes

- Keep generic framework behavior in `tools/skill_eval/*`.

- Put domain-specific grading in the skill's eval directory, e.g. `skills/custom-command/evals/grader.py`.

- Prefer deterministic checks. LLM judge metadata is represented, but judge execution is intentionally not implemented yet.

- Update this README and `tools/skill_eval/AGENTS.md` when changing harness contracts, result bundle shape, suite support, or trust criteria.
