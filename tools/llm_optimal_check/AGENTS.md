# llm_optimal_check maintenance context

## Purpose

`tools.llm_optimal_check` provides the canonical deterministic LLM optimization-readiness checker. Preserve the CLI/API JSON contract and the legacy `skills/llm-optimized-rewrite/scripts/smell_test.py` compatibility wrapper.

## How the tool works

The checker excludes leading YAML frontmatter from analysis, detects token-cost and reliability heuristics, scores findings from 100, and maps scores to `pass`, `warn`, or `fail`. It calls `tools.llm_token_count.count_text` for exact token metrics.

Terminology is defined in `tools/llm_optimal_check/UBIQUITOUS_LANGUAGE.md`.

## Eval and validation

Run:

```sh
python3 -m unittest tools.skill_eval.tests.test_llm_optimized_smell_test -v
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
```

The first suite covers the standalone checker and legacy wrapper. The second covers the `skill_valid` gate integration.

## Change guidelines

- Keep report keys exactly `status`, `score`, `metrics`, and `findings` unless a bead explicitly changes the contract.
- Preserve finding fields: `rule_id`, `severity`, `category`, `location`, `evidence`, `message`, and `suggestion`.
- Keep `warn` non-blocking for `skill_valid`; keep `fail` blocking.
- Do not add LLM judging to this deterministic checker.
- Do not broaden `skill_valid` scope beyond primary `SKILL.md` without updating the PRD/bead and tests.
