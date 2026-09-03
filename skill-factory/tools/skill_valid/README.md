# skill_valid

`skill_valid` validates one repo-local skill through deterministic compatibility/resource gates, maintenance-doc
gates, and a deterministic LLM optimization-readiness gate. Optional live validation adds a validate-skills
qualitative review and behavior evals through Pi.

## Usage

Machine-readable JSON:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/<skill-name>
```

Friendly human summary:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/<skill-name>
```

The wrapper invokes deterministic validation by default, renders gate statuses, prints `llm_optimal_check`
findings inline, and preserves the underlying exit code. Pass `--allow-live` (or set `SKILL_VALID_ALLOW_LIVE=1`)
to enable live gates. Set `SKILL_VALIDATE_RAW_JSON=1` to append raw JSON or `SKILL_VALIDATE_VERBOSE=1` to show
`skill_valid` stderr logs.

Optional live execution overrides are applied to both live gates:

```sh
PYTHONPATH=skill-factory python3 -m tools.skill_valid skills/<skill-name> \
  --allow-live \
  --harness pi \
  --provider openrouter \
  --model gpt-5 \
  --thinking low
```

`--allow-live` or `SKILL_EVAL_ALLOW_LIVE=1` is required before live harness/model work runs. `--allow-live-pi`
and `SKILL_EVAL_ALLOW_LIVE_PI=1` remain backwards-compatible aliases. Without live opt-in, passing deterministic
gates produce a valid result and live gates remain `not_run`. Deterministic failures are accumulated so the JSON
reports multiple missing requirements at once; those
failures do not create live-run artifacts or call a harness. The `llm_optimal_check` gate may return `warn`; warnings
are visible but non-blocking.

### Optional Pi trigger suite

Pass `--include-trigger` to validate the `trigger` suite's natural-discovery contract. With separate
`--allow-live`, the live eval gate also runs its suite-local discovery configurations (or the default Pi
`discovery` profile). This requires the Pi harness and adds cases × discovery profiles to the process budget;
provider/model/thinking overrides also apply to these profiles. Without live opt-in, no processes run.

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/human-writing --include-trigger
# Add --allow-live --harness pi only after approving the additional live run budget.
```

Skipped, invalid, missing, duplicated, or failed trigger runs fail live validation. Do not confuse a completed
process with successful activation/avoidance. See [skill_eval](../skill_eval/README.md#natural-trigger-evals-pi-only)
for the target-only read profile, evidence contract, configuration fields, and limitations. Use `skill_eval`
directly to retain successful benchmark artifacts; this validator still deletes successful temporary runs.

## stdout JSON contract

The only machine contract is one compact stdout JSON object. Progress and diagnostics go to stderr.

```json
{
  "valid": false,
  "target": "skills/example",
  "gates": {
    "target": {"status": "passed", "message": "..."},
    "skill_spec": {

      "status": "failed",
      "message": "...",
      "details": {
        "checks": [
          {"id": "name.format", "status": "failed", "message": "..."}
        ]

      }
    },
    "eval_manifest": {"status": "failed", "message": "..."},
    "agents_md": {"status": "failed", "message": "..."},
    "llm_optimal_check": {
      "status": "warn",

      "message": "...",
      "details": {
        "report": {
          "status": "warn",
          "score": 85,
          "metrics": {"tokens": 1200},

          "findings": []
        }
      }
    },
    "live_opt_in": {"status": "passed", "message": "..."},
    "validate_skills": {"status": "not_run", "message": "..."},

    "live_eval": {"status": "not_run", "message": "..."}
  }
}
```

Exit code is `0` only when `valid` is `true`. Gate statuses are `passed`, `warn`, `failed`, or `not_run`; only
`passed` and `warn` can coexist with `valid=true`.

## Gate order

1. `target` — target must be one direct directory under `skills/` with `SKILL.md`. If this fails, the target cannot be inspected further.

2. `skill_spec` — parses `SKILL.md` without external dependencies.

   - Runs deterministic Pi skill compatibility, resource-reference, and repo-contract checks.
   - Pi loadability and repo-contract violations fail.
   - Deterministic best-practice concerns warn without blocking validity, such as weak trigger wording or
      list-form `allowed-tools`.
   - Safely ignored harness capability fields such as `disable-model-invocation` and `user-invocable` are allowed only when baseline behavior does not depend on them.

3. `eval_manifest` — required `evals/manifest.json` must load through `tools.skill_eval`, declare a non-empty
   `workflow` suite, align skill name/path with the target, define a supported real-harness `with_skill`
   configuration with force-skill enabled, and reference existing eval assets. Missing or invalid manifests fail before live work.

4. `agents_md` — skill-local `AGENTS.md` must include Purpose, How the skill works, Eval and validation,
   Change guidelines, plus concrete references to `SKILL.md`, `evals/manifest.json`, and manifest-declared eval assets.


5. `llm_optimal_check` — runs `tools.llm_optimal_check.check_path` on only the target skill's `SKILL.md`.

   - Checker `pass` maps to gate `passed`.
   - Checker `warn` maps to non-blocking gate `warn`.
   - Checker `fail` maps to gate `failed`.
   - Tool errors fail closed.
   - Details embed a compact report with status, score, useful metrics, and all findings, excluding bulky
     preview/body fields.

6. `live_opt_in` — rejects unsupported harness overrides, then records whether live validation was explicitly enabled. Without opt-in, deterministic
   validity is decided here and live gates remain `not_run`.

7. `validate_skills` — when enabled, runs the Pi harness with the validate-skills instructions.
   The wrapper prompt in `WRAPPER_PROMPT.md` requires a final `SKILL_VALID_RESULT=<json>` sentinel.

8. `live_eval` — when enabled, runs `tools.skill_eval.runner.run_suite` in-process for
   `workflow` and optional `regression`, using only a generated live `with_skill` configuration and
   `require_real=True`. With `--include-trigger`, also runs the Pi `trigger` suite using its discovery profiles,
   not a generated with-skill configuration.

`skill_spec`, `eval_manifest`, `agents_md`, `llm_optimal_check`, and `live_opt_in` are all checked before live
gates so the result reports deterministic prerequisites together. Live gates run only when those prerequisite
gates pass or warn and live validation was explicitly enabled.

## Failure artifacts

`skill_valid` does not persist a success report. Temporary child artifacts are deleted on full success. If a
live gate created artifacts and validation fails, the stdout JSON includes `failure_artifacts` pointing to the
preserved directory. Preserved artifacts include validate-skills raw stdout/stderr and skill_eval child
outputs for suites that ran.
