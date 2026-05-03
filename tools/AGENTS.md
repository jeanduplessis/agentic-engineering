# tools maintenance context

## Purpose

This directory contains repo-level Python tools used by agents to evaluate, validate, and optimize skills.
Prefer these shared tools over skill-local scripts when adding automation. Read the tool-specific `AGENTS.md`
before changing a tool's internals.

## Available tools

- `tools.llm_token_count`: Purpose: Exact token metrics for LLM-facing text.. Primary CLI/API: `python3 -m
  tools.llm_token_count [--json]`; `count_text(text, model=None, encoding=None)`. Notes: Uses `tiktoken`,
  defaults to `gpt-5` / `o200k_base`, and backs the legacy rewrite-skill `count_tokens.py` wrapper..

- `tools.llm_optimal_check`: Purpose: Deterministic LLM optimization-readiness check for Markdown/prompt/skill
  text.. Primary CLI/API: `python3 -m tools.llm_optimal_check <path>`; `check_path(path)`. Notes: Emits
  `{status, score, metrics, findings}`. `warn` is advisory; `fail` blocks `skill_valid`. Backs the legacy
  `smell_test.py` wrapper..

- `tools.skill_eval`: Purpose: Skill behavior evaluation framework.. Primary CLI/API: `python3 -m
  tools.skill_eval <manifest> <suite> --results <dir>`. Notes: Runs workflow/regression suites, writes trace
  bundles, supports static/replay/real harness modes, and labels synthetic results honestly..

- `tools.skill_valid`: Purpose: End-to-end validity gate for one repo-local skill.. Primary CLI/API: `python3
  -m tools.skill_valid skills/<skill-name> --allow-live-pi`; `validate_skill(...)`;
  `./tools/skill_valid/skill_validate.sh skills/<skill-name>`. Notes: Orchestrates target, manifest,
  AGENTS.md, `llm_optimal_check`, live opt-in, validate-skills, and live eval gates. Stdout is compact JSON.
  The shell wrapper renders a friendly human summary..

- `tools.command_valid`: Purpose: Deterministic validation for one clean Pi extended command.. Primary CLI/API:
  `python3 -m tools.command_valid <command-name> [--json]`; `validate_command(CommandValidationOptions)`.
  Notes: Uses repo-root `commands/` by default; validates kebab/reserved names, direct `<name>.md` resolution,
  scalar frontmatter, supported fields, valid `thinking`/`restore`, body placeholders/syntax, and declared
  skill resolution; emits friendly stdout by default and compact JSON with `--json`; does not query live Pi state..

## Selection guide

- Need exact token counts for a snippet or file content: use `tools.llm_token_count`.

- Need deterministic optimization findings for a prompt, command, or `SKILL.md`: use `tools.llm_optimal_check`.

- Need behavior evidence from a skill-owned eval manifest: use `tools.skill_eval`.

- Need to validate one Pi command name and direct command-file resolution: use `tools.command_valid`.

- Need to decide whether a repo-local skill is valid: use `tools.skill_valid` or the friendly `tools/skill_valid/skill_validate.sh` wrapper.

- Need to preserve old rewrite-skill workflows: keep using the compatibility wrappers, but implement shared behavior in repo-level tools.

## Cross-tool contracts

- `llm_optimal_check` depends on `llm_token_count`; do not duplicate token counting there.

- `skill_valid` calls `llm_optimal_check` through an injectable API and calls `skill_eval.runner.run_suite` in process.

- `skill_valid` must not call live Pi/model gates before deterministic gates pass or warn and live opt-in is present.

- `skill_eval` static/replay outputs are synthetic; do not present them as benchmark-quality real behavior.

- Tool CLIs should keep stdout machine-readable when documented as JSON contracts; diagnostics go to stderr.

## Validation commands

Run focused tests after changing a tool:

```sh
python3 -m unittest tools.command_valid.tests.test_command_valid -v
python3 -m unittest tools.skill_eval.tests.test_llm_optimized_smell_test -v
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
```

Run the deterministic suite before handoff:

```sh
python3 -m unittest discover -v
```

Do not add live Pi/model tests unless explicitly requested. Existing unit tests use fakes for live gates.

## Change guidelines

- Update the relevant tool-specific `README.md`, `AGENTS.md`, and tests when changing a public CLI/API contract.

- Keep compatibility wrappers thin; canonical implementations belong under `tools/`.

- Prefer importable APIs for in-process orchestration and deterministic tests.

- Preserve failure artifacts only when a tool explicitly documents that behavior.
