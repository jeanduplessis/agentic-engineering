# skill_valid maintenance context

## Purpose

`tools.skill_valid` orchestrates the Skill Validity decision for one repo-local skill. Keep the public command
`python3 -m tools.skill_valid skills/<skill-name> --allow-live-pi`, the friendly wrapper
`./tools/skill_valid/skill_validate.sh skills/<skill-name>`, and the compact stdout JSON contract stable.

## How the tool works

The module implements Validation Gate functions in `tools/skill_valid/__init__.py`; deterministic SKILL.md
spec/resource checks live in `tools/skill_valid/spec_checks.py`. The target gate runs first because later
gates need a real skill directory. Deterministic prerequisite gates then accumulate results for `skill_spec`,
`evals/manifest.json`, skill-local `AGENTS.md`, `llm_optimal_check`, and live opt-in so users see multiple
missing requirements in one JSON response. Live gates run only after those prerequisites pass or warn, then
execute the validate-skills wrapper prompt and the existing `tools.skill_eval.runner.run_suite` API.

Terminology is defined in `tools/skill_valid/UBIQUITOUS_LANGUAGE.md`. The validate-skills sentinel contract is
documented in `tools/skill_valid/WRAPPER_PROMPT.md`.

## Eval and validation

Run deterministic tests with:

```sh
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
```

Tests use fake Pi, fake skill_eval runners, and fake LLM Optimal Check injectables; do not add live Pi unit
tests unless explicitly requested. When changing gate order, result fields, wrapper prompt requirements, or
artifact behavior, update tests and `tools/skill_valid/README.md` together.

## Change guidelines

- Preserve live-run safety: no Pi/model call before cheap gates pass or warn and live opt-in is present.

- Keep deterministic spec/resource rules in `spec_checks.py`; keep the validate-skills skill focused on qualitative, judgment-based review.

- Keep stdout machine-readable and compact; write diagnostics only to stderr.

- Use `tools.skill_eval.manifest.load_manifest` and `tools.skill_eval.runner.run_suite` instead of duplicating the eval framework.

- Preserve failure artifacts only for failed runs after artifact creation; delete successful temporary artifacts.

- Keep `llm_optimal_check` injectable for pass/warn/fail/tool-error tests.

- Treat skipped, synthetic, process-failed, missing, and not-graded eval runs as invalid.
