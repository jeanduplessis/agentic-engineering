# skill_valid maintenance context

## Purpose

`tools.skill_valid` orchestrates the Skill Validity decision for one repo-local skill. Keep the public command `python3 -m tools.skill_valid skills/<skill-name> --allow-live-pi` and the compact stdout JSON contract stable.

## How the tool works

The module implements a fail-fast sequence of Validation Gate functions in `tools/skill_valid/__init__.py`. Cheap gates validate target shape, `evals/manifest.json`, and skill-local `AGENTS.md` before the live-run safety gate allows model calls. Live gates then run the validate-skills wrapper prompt and the existing `tools.skill_eval.runner.run_suite` API.

Terminology is defined in `tools/skill_valid/UBIQUITOUS_LANGUAGE.md`. The validate-skills sentinel contract is documented in `tools/skill_valid/WRAPPER_PROMPT.md`.

## Eval and validation

Run deterministic tests with:

```sh
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
```

Tests use fake Pi and fake skill_eval runners; do not add live Pi unit tests unless explicitly requested. When changing gate order, result fields, wrapper prompt requirements, or artifact behavior, update tests and `tools/skill_valid/README.md` together.

## Change guidelines

- Preserve live-run safety: no Pi/model call before cheap gates pass and live opt-in is present.
- Keep stdout machine-readable and compact; write diagnostics only to stderr.
- Use `tools.skill_eval.manifest.load_manifest` and `tools.skill_eval.runner.run_suite` instead of duplicating the eval framework.
- Preserve failure artifacts only for failed runs after artifact creation; delete successful temporary artifacts.
- Treat skipped, synthetic, process-failed, missing, and not-graded eval runs as invalid.
