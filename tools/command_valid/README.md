# command_valid

Deterministic validator for one Pi extended command name.

## CLI

```sh
python3 -m tools.command_valid <command-name>
python3 -m tools.command_valid <command-name> --json
```

Default command library: `commands/` under the repo root. Override for tests or alternate checkouts:

```sh
python3 -m tools.command_valid code-review --repo-root /path/to/repo
python3 -m tools.command_valid code-review --commands-dir /path/to/commands
```

## Contract

`command_valid` validates one clean Pi-only command:

- command name must be lowercase kebab-case;
- command name must not be reserved by Pi;
- command must resolve to one direct `<command-name>.md` file in the command library;
- validation does not recurse into subdirectories;
- command file must start with frontmatter and a non-empty scalar `description`;
- recognized fields: scalar `description`, `argument-hint`, `model`, `thinking`, `skill`, `restore`, plus scoped YAML-list `skills`;
- unknown fields fail validation;
- unsupported nested/list/malformed frontmatter fails validation;
- `thinking` must be `off`, `minimal`, `low`, `medium`, `high`, or `xhigh`;
- `restore` must be `true` or `false`;
- unsupported legacy body syntax such as shell/file expansion fails validation;
- unsupported placeholders such as `${@:N}` fail validation;
- declared `skill` and `skills` entries must resolve to readable local skills;
- validation is static and does not query Pi's live model registry.

Exit codes:

- `0`: valid command name and file resolution;
- `1`: invalid command contract, such as non-kebab-case or reserved name;
- `2`: usage or resolution error, such as missing command name or missing file.

`--json` emits compact JSON on stdout. Friendly output is the default.
