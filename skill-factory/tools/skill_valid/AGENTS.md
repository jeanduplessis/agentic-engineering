# skill_valid maintenance context

## Purpose

`tools.skill_valid` orchestrates the Skill Validity decision for one repo-local skill. Keep deterministic
validation as baseline, expose live work only through explicit `--allow-live`, preserve `--allow-live-pi` as an
alias, and keep the friendly wrapper
`./skill-factory/tools/skill_valid/skill_validate.sh skills/<skill-name>`, and the compact stdout JSON contract stable.

## How the tool works

The module implements Validation Gate functions in `tools/skill_valid/__init__.py`; deterministic shared Pi/OpenCode
SKILL.md compatibility/resource checks live in `tools/skill_valid/spec_checks.py`. The target gate runs first because later
gates need a real skill directory. Deterministic prerequisite gates then accumulate results for `skill_spec`,
`evals/manifest.json`, skill-local `AGENTS.md`, `llm_optimal_check`, and live opt-in so users see multiple
missing requirements in one JSON response. Live gates run only after those prerequisites pass or warn, then
execute the validate-skills wrapper prompt and the existing `tools.skill_eval.runner.run_suite` API.

Terminology is defined in `tools/skill_valid/UBIQUITOUS_LANGUAGE.md`. The validate-skills sentinel contract is
documented in `tools/skill_valid/WRAPPER_PROMPT.md`.

## Eval and validation

Run deterministic tests with:

```sh
PYTHONPATH=skill-factory python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
PYTHONPATH=skill-factory python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
```

Tests use fake harnesses, fake skill_eval runners, and fake LLM Optimal Check injectables; do not add live model unit
tests unless explicitly requested. When changing gate order, result fields, wrapper prompt requirements, or
artifact behavior, update tests and `tools/skill_valid/README.md` together.

## Change guidelines

- Preserve live-run safety: no harness/model call before cheap gates pass or warn and harness-neutral live opt-in is present.

- `--include-trigger` validates the natural trigger contract in the cheap manifest gate and, only with live opt-in, adds all suite-local discovery profiles to live evals. It requires Pi and must never silently enable live calls or reuse with/without controls. Check exact case/configuration coverage, rejecting duplicate or missing trigger runs.

- Wrapper must remain deterministic by default and must not append a live opt-in unconditionally.

- Pi and OpenCode-compatible Kilo are supported real harnesses; required eval manifests must pass structural validation before live work.

- Keep deterministic shared compatibility/resource rules in `spec_checks.py`; keep the validate-skills skill focused on qualitative, judgment-based review.

- Keep stdout machine-readable and compact; write diagnostics only to stderr.

- Use `tools.skill_eval.manifest.load_manifest` and `tools.skill_eval.runner.run_suite` instead of duplicating the eval framework.

- Preserve failure artifacts only for failed runs after artifact creation; delete successful temporary artifacts.

- Keep `llm_optimal_check` injectable for pass/warn/fail/tool-error tests.

- Treat skipped, synthetic, process-failed, missing, and not-graded eval runs as invalid.
