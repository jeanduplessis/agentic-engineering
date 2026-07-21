# command_valid maintenance context

## Purpose

`tools.command_valid` statically validates one Pi-owned command and its direct command-file resolution.

## Public CLI/API

- CLI: `PYTHONPATH=skill-factory python3 -m tools.command_valid <command-name> [--json]`
- API: `validate_command(CommandValidationOptions) -> (exit_code, CommandValidationResult)`
- Default source: repo-root `harness/pi/commands/`.
- Preserve CLI, result JSON schema, and exit classes: `0` valid, `1` invalid contract, `2` usage/resolution error.

## Contract

- Validate one command name per invocation; accept names, not paths; keep discovery non-recursive.
- Require frontmatter with non-empty scalar `description`.
- Accept the supported command frontmatter fields, including scalar `agent` and boolean `subtask`.
- Reject duplicate frontmatter and invalid boolean/routing values.
- Accept `$ARGUMENTS` and simple positional placeholders such as `$1`; reject `$@` and `${@:...}`.
- Reject OpenCode shell/file interpolation because these files are Pi prompt templates, but do not treat package suffixes such as `react-doctor@latest` as file interpolation.
- Require declared skills to be unique lowercase kebab-case names, resolve locally, and exactly match the ordered explicit `Required skills` body section.
- Require every Pi command in the expected inventory to pass validation.
- Do not query live harness state; this tool is deterministic and static.

## Eval and validation

```sh
PYTHONPATH=skill-factory python3 -m unittest tools.command_valid.tests.test_command_valid -v
PYTHONPATH=skill-factory python3 -m unittest discover -s skill-factory -v
```

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing CLI/API, result JSON, exit codes, command-name rules, source resolution, or the Pi command contract.
