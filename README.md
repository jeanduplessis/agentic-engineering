# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are personalized for how I work.

## Pi resources

Pi-owned prompt templates live in `harness/pi/commands/*.md`. Root `package.json` exposes them through `pi.prompts`; edit those files directly. This repository does not provide shared Pi/OpenCode command sources or activate OpenCode/Kilo commands.

Pi extensions live in `harness/pi/extensions/`. Activate an extension through Pi's local extension discovery configuration; keep activation symlinks local and untracked.

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
- `harness/pi/extensions/` contains Pi extensions.
- `skills/` contains shared-harness skills.
- `prompts/` contains system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current repository-owned prompt resource.
- `skill-factory/` contains skill authoring, validation, and evaluation resources.
- `tools/gs/` and `tools/gw/` are independent tool packages.

Commands are flat. Recursive command directories, project-local command ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution remain outside the Pi extension's V1 scope.
