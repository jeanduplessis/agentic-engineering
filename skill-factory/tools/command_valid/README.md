# command_valid

Deterministic validator for one Pi-owned command.

## CLI

```sh
PYTHONPATH=skill-factory python3 -m tools.command_valid <command-name>
PYTHONPATH=skill-factory python3 -m tools.command_valid <command-name> --json
```

Default source: repo-root `harness/pi/commands/`. Override for tests or alternate checkouts:

```sh
PYTHONPATH=skill-factory python3 -m tools.command_valid code-review --repo-root /path/to/repo
PYTHONPATH=skill-factory python3 -m tools.command_valid code-review --commands-dir /path/to/commands
```

## Contract

`command_valid` validates one Pi prompt template:

- command name must be lowercase kebab-case and not reserved by Pi;
- command must resolve to one direct `<command-name>.md` file; discovery is non-recursive;
- frontmatter must include a non-empty scalar `description`;
- supported fields are accepted: scalar `description`, `argument-hint`, `model`, `thinking`, `skill`, `restore`, `agent`, `subtask`, plus YAML-list `skills`;
- unknown, duplicate, malformed, nested, or unsupported list frontmatter fails;
- `thinking` must be `off`, `minimal`, `low`, `medium`, `high`, or `xhigh`; `restore` and `subtask` must be `true` or `false`;
- source placeholders may use `$ARGUMENTS` and simple positional `$1`, `$2`, etc.; `$@` and `${@:...}` fail;
- OpenCode shell interpolation such as ``!`cmd` `` and file interpolation such as `@src/file.ts` fail;
- package suffixes such as `react-doctor@latest` are ordinary text and do not fail;
- declared `skill` and `skills` entries must be unique lowercase kebab-case names, resolve locally, and exactly match the order of an explicit `## Required skills` body list;
- validation is static and does not query live Pi state.

Inventory tests assert the expected command set and require every `harness/pi/commands/*.md` file to pass this contract.

Exit codes and result schema remain stable:

- `0`: valid command;
- `1`: invalid command contract;
- `2`: usage or resolution error.

`--json` emits compact JSON on stdout. Friendly output remains default.
