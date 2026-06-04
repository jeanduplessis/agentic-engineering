# command_valid maintenance context

## Purpose

`tools.command_valid` statically validates one command from shared canonical Pi/OpenCode source and its direct command-file resolution.

## Public CLI/API

- CLI: `python3 -m tools.command_valid <command-name> [--json]`
- API: `validate_command(CommandValidationOptions) -> (exit_code, CommandValidationResult)`
- Default canonical source: repo-root `commands/`
- Preserve CLI, result JSON schema, and exit classes: `0` valid, `1` invalid contract, `2` usage/resolution error.

## Contract

- Validate one command name per invocation; accept names, not paths; keep discovery non-recursive.
- Require frontmatter with non-empty scalar `description`.
- Accept harmless Pi/OpenCode union fields, including scalar `agent` and boolean `subtask`, without requiring either adapter to implement their semantics.
- Reject duplicate frontmatter and invalid boolean/routing values.
- Accept `$ARGUMENTS` and simple positional placeholders such as `$1`; reject `$@` and `${@:...}`.
- Reject OpenCode shell/file interpolation, but do not treat package suffixes such as `react-doctor@latest` as file interpolation.
- Require declared skills to be unique lowercase kebab-case names, resolve locally, and exactly match the ordered explicit `Required skills` body section.
- Require every canonical command in the expected inventory to pass shared validation.
- Do not query live Pi or OpenCode state; this tool is deterministic and static.

## Eval and validation

```sh
python3 -m unittest tools.command_valid.tests.test_command_valid -v
python3 -m unittest discover -v
```

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing CLI/API, result JSON, exit codes, command-name rules, source resolution, or shared command contract.
