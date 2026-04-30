# skill_valid

`skill_valid` validates one repo-local skill through deterministic spec/resource gates, maintenance-doc gates, a deterministic LLM optimization-readiness gate, a live validate-skills qualitative review, and live behavior evals.

## Usage

```sh
python3 -m tools.skill_valid skills/<skill-name> --allow-live-pi
```

Optional live execution overrides are applied to both live gates:

```sh
python3 -m tools.skill_valid skills/<skill-name> \
  --allow-live-pi \
  --provider anthropic \
  --model claude-sonnet \
  --thinking low
```

`--allow-live-pi` or `SKILL_EVAL_ALLOW_LIVE_PI=1` is required before any live Pi/model work runs. Deterministic failures are accumulated so the JSON reports multiple missing requirements at once; those failures do not create live-run artifacts or call Pi. The `llm_optimal_check` gate may return `warn`; warnings are visible but non-blocking.

## stdout JSON contract

The only machine contract is one compact stdout JSON object. Progress and diagnostics go to stderr.

```json
{"valid":false,"target":"skills/example","gates":{"target":{"status":"passed","message":"..."},"skill_spec":{"status":"failed","message":"...","details":{"checks":[{"id":"name.format","status":"failed","message":"..."}]}},"eval_manifest":{"status":"failed","message":"..."},"agents_md":{"status":"failed","message":"..."},"llm_optimal_check":{"status":"warn","message":"...","details":{"report":{"status":"warn","score":85,"metrics":{"tokens":1200},"findings":[]}}},"live_opt_in":{"status":"passed","message":"..."},"validate_skills":{"status":"not_run","message":"..."},"live_eval":{"status":"not_run","message":"..."}}}
```

Exit code is `0` only when `valid` is `true`. Gate statuses are `passed`, `warn`, `failed`, or `not_run`; only `passed` and `warn` can coexist with `valid=true`.

## Gate order

1. `target` — target must be one direct directory under `skills/` with `SKILL.md`. If this fails, the target cannot be inspected further.
2. `skill_spec` — parses `SKILL.md` without external dependencies and runs deterministic Agent Skills spec, Claude compatibility, resource-reference, and portability checks. Spec violations fail; deterministic best-practice concerns (for example weak trigger wording or list-form `allowed-tools`) warn without blocking validity.
3. `eval_manifest` — `evals/manifest.json` must load through `tools.skill_eval`, declare a non-empty `workflow` suite, align skill name/path with the target, define a Pi `with_skill` configuration with force-skill enabled, and reference existing eval assets.
4. `agents_md` — skill-local `AGENTS.md` must include Purpose, How the skill works, Eval and validation, Change guidelines, plus concrete references to `SKILL.md`, `evals/manifest.json`, and manifest-declared eval assets when a manifest could be loaded.
5. `llm_optimal_check` — runs `tools.llm_optimal_check.check_path` on only the target skill's `SKILL.md`. Checker `pass` maps to gate `passed`; checker `warn` maps to non-blocking gate `warn`; checker `fail` maps to gate `failed`. Tool errors fail closed. Details embed a compact report with status, score, useful metrics, and all findings, excluding bulky preview/body fields.
6. `live_opt_in` — requires `--allow-live-pi` or `SKILL_EVAL_ALLOW_LIVE_PI=1`.
7. `validate_skills` — runs Pi with only the validate-skills skill and read-only tools. The wrapper prompt in `WRAPPER_PROMPT.md` requires a final `SKILL_VALID_RESULT=<json>` sentinel.
8. `live_eval` — runs `tools.skill_eval.runner.run_suite` in-process for `workflow` and optional `regression`, using only a generated live `with_skill` configuration and `require_real=True`.

`skill_spec`, `eval_manifest`, `agents_md`, `llm_optimal_check`, and `live_opt_in` are all checked before live gates so the result reports deterministic prerequisites together. The live gates run only when those prerequisite gates pass or warn.

## Failure artifacts

`skill_valid` does not persist a success report. Temporary child artifacts are deleted on full success. If a live gate created artifacts and validation fails, the stdout JSON includes `failure_artifacts` pointing to the preserved directory. Preserved artifacts include validate-skills raw stdout/stderr and skill_eval child outputs for suites that ran.
