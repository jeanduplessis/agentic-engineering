# command_valid maintenance context

## Purpose

`tools.command_valid` statically validates one Pi extended command name and its direct command-file resolution.

## Public CLI/API

- CLI: `python3 -m tools.command_valid <command-name> [--json]`
- API: `validate_command(CommandValidationOptions) -> (exit_code, CommandValidationResult)`
- Default command library: repo-root `commands/`

## Contract

- Validate one command name per invocation.
- Accept command names, not arbitrary paths.
- Keep command discovery non-recursive.
- Require frontmatter with non-empty scalar `description`.
- Recognize only scalar `description`, `argument-hint`, `model`, `thinking`, `skill`, `restore`, plus scoped YAML-list `skills`.
- Fail unknown or unsupported nested/list/malformed frontmatter, invalid `thinking`/`restore`, unsupported legacy body syntax, unsupported placeholders, and missing declared skills.
- Keep stdout friendly by default and compact JSON with `--json`.
- Preserve exit-code classes: `0` valid, `1` invalid command contract, `2` usage/resolution error.
- Do not query live Pi state; this tool is deterministic and static.

## Eval and validation

Run focused tests after changing this tool:

```sh
python3 -m unittest tools.command_valid.tests.test_command_valid -v
```

Run the deterministic suite before handoff:

```sh
python3 -m unittest discover -v
```

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing the CLI/API, result JSON, exit codes, command-name rules, or command-library resolution.
