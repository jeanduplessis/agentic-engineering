# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are personalized for how I work.

## Setup

Run `./setup.sh` to interactively install tools, link selected skills into Pi, Kilo, or the global `~/.agents/skills` directory, and install Pi or Kilo harness artifacts. Skill and Pi extension selection is explicit; nothing is installed by default. Æ is the name of this setup, not a separate command.

## Pi resources

Pi-owned prompt templates live in `harness/pi/commands/*.md`. Root `package.json` exposes them through `pi.prompts`; edit those files directly. This repository does not provide shared Pi/OpenCode command sources or activate OpenCode/Kilo commands.

Pi extensions live in `harness/pi/extensions/`. This checkout is their source of truth. `./setup.sh` links each selected extension into `~/.pi/agent/extensions/<name>` as a symlink, so edits in this repository take effect without copying. Extensions are selected one by one; none are linked automatically.

An extension with npm dependencies (for example `openai-images`) needs `npm install` inside its directory in this checkout. `node_modules/` and extension-written runtime state are untracked.

This repository's skills remain under `skills/`. They are written for shared behavior across supported harnesses. Install or link them according to the target harness's documented discovery mechanism; installation paths are separate from this source checkout.

Use this repository as a local Pi package:

```sh
pi install /absolute/path/to/this-repository
```

For a one-run load without changing settings:

```sh
pi -e /absolute/path/to/this-repository
```

## Resource layout

- `harness/pi/commands/` contains Pi-owned slash-command prompt templates.
- `harness/pi/extensions/` contains Pi extensions, each linked into Pi individually by `./setup.sh`.
- `skills/` contains shared-harness skills.
- `prompts/` contains system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current repository-owned prompt resource.
- `skill-factory/` contains skill authoring, validation, and evaluation resources.
- `tools/ghh/`, `tools/gs/`, and `tools/gw/` are independent tool packages.

Commands are flat. Recursive command directories, project-local command ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution remain outside the Pi extension's V1 scope.
