# skill_valid

`skill_valid` validates one repo-local skill through deterministic gates, a live validate-skills review, and live behavior evals.

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

`--allow-live-pi` or `SKILL_EVAL_ALLOW_LIVE_PI=1` is required before any live Pi/model work runs. Cheap deterministic failures do not create live-run artifacts or call Pi.

## stdout JSON contract

The only machine contract is one compact stdout JSON object. Progress and diagnostics go to stderr.

```json
{"valid":false,"target":"skills/example","gates":{"target":{"status":"passed","message":"..."},"eval_manifest":{"status":"failed","message":"..."},"agents_md":{"status":"not_run","message":"..."},"live_opt_in":{"status":"not_run","message":"..."},"validate_skills":{"status":"not_run","message":"..."},"live_eval":{"status":"not_run","message":"..."}}}
```

Exit code is `0` only when `valid` is `true`.

## Gate order

1. `target` — target must be one direct directory under `skills/` with `SKILL.md`.
2. `eval_manifest` — `evals/manifest.json` must load through `tools.skill_eval`, declare a non-empty `workflow` suite, align skill name/path with the target, define a Pi `with_skill` configuration with force-skill enabled, and reference existing eval assets.
3. `agents_md` — skill-local `AGENTS.md` must include Purpose, How the skill works, Eval and validation, Change guidelines, plus concrete references to `SKILL.md`, `evals/manifest.json`, and manifest-declared eval assets.
4. `live_opt_in` — requires `--allow-live-pi` or `SKILL_EVAL_ALLOW_LIVE_PI=1`.
5. `validate_skills` — runs Pi with only the validate-skills skill and read-only tools. The wrapper prompt in `WRAPPER_PROMPT.md` requires a final `SKILL_VALID_RESULT=<json>` sentinel.
6. `live_eval` — runs `tools.skill_eval.runner.run_suite` in-process for `workflow` and optional `regression`, using only a generated live `with_skill` configuration and `require_real=True`.

## Failure artifacts

`skill_valid` does not persist a success report. Temporary child artifacts are deleted on full success. If a live gate created artifacts and validation fails, the stdout JSON includes `failure_artifacts` pointing to the preserved directory. Preserved artifacts include validate-skills raw stdout/stderr and skill_eval child outputs for suites that ran.
