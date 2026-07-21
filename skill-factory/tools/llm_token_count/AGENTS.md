# llm_token_count maintenance context

## Purpose

`tools.llm_token_count` provides exact token metrics for reusable validation and rewrite tooling. Preserve the CLI/API contract and the legacy `skills/llm-optimized-rewrite/scripts/count_tokens.py` wrapper.

## How the tool works

The module reads stdin for CLI use and exposes `count_text(text, model=None, encoding=None)` for in-process callers. It uses `tiktoken`, defaults to `gpt-5` with the `o200k_base` fallback, and treats special-token sentinel strings as ordinary text.

## Eval and validation

Run:

```sh
PYTHONPATH=skill-factory python3 -m unittest tools.skill_eval.tests.test_llm_optimized_smell_test -v
```

That suite covers the repo-level CLI/API and the legacy wrapper contract.

## Change guidelines

- Keep JSON fields exactly `tokens`, `encoding`, `source`, and `characters` unless a bead explicitly changes the contract.
- Do not bury token counting inside `llm_optimal_check`; it must remain independently reusable.
- Preserve legacy bootstrap environment variables and default venv location.
- Do not estimate counts when exact `tiktoken` counts are available.
