# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are personalized for how I work.

## Setup

Run `./setup.sh` to interactively install tools, link selected skills into Pi or the global `~/.agents/skills` directory, and install Pi harness artifacts. Skills and Pi resources require explicit selection and confirmation. Æ is the name of this setup, not a separate command.

Under **Harness**, select components first. Root files such as `APPEND_SYSTEM.md` are independent choices. The `commands`, `extensions`, and optional harness `skills` components each open an item picker. Other resources, such as `docs`, are selected as whole files or directories; `docs` is linked as one directory, not file by file.

Nothing is selected by default in either Pi picker. Enter names or numbers, or type `all` explicitly at each level. Review the selected source-to-destination plan and confirm before any Pi links are created. Cancelling any Pi picker cancels the entire Pi plan; empty components are skipped. Unselected existing installs stay untouched.

## Pi resources

Pi's root-agent policy lives in [`harness/pi/APPEND_SYSTEM.md`](harness/pi/APPEND_SYSTEM.md). Edit this repository source, not the installed link. Selecting `APPEND_SYSTEM.md` under **Harness** in `./setup.sh` links it to `~/.pi/agent/APPEND_SYSTEM.md` (or `$PI_AGENT_DIR/APPEND_SYSTEM.md`) after approval of the plan; an existing file is backed up after confirmation, and replacing a conflicting symlink also requires confirmation. The policy owns orchestration decisions; the installed `pi-subagents` skill owns invocation details.

Pi-owned prompt templates live in `harness/pi/commands/*.md`. In setup, choose **Harness → commands**, then select individual templates or explicitly select `all`; each selected template is linked into `~/.pi/agent/prompts/`. Root `package.json` exposes them through `pi.prompts`; edit those files directly. Pi is the only supported live harness.

Use [`/wat [optional focus]`](harness/pi/commands/wat.md) to simplify the last assistant response into a plain-language takeaway and up to three short bullets, without continuing the task.

Pi extensions live in `harness/pi/extensions/`. This checkout is their source of truth. `./setup.sh` links each selected extension into `~/.pi/agent/extensions/<name>` as a symlink, so edits in this repository take effect without copying. Choose **Harness → extensions**, then select individual extensions or explicitly select `all`; none are linked automatically.

The [`kilo-pi-provider`](harness/pi/extensions/kilo-pi-provider/README.md) extension provides Kilo AI gateway access inside Pi, including the balance display in `custom-footer`. This is model-provider support, not support for the standalone Kilo harness. It remains available under **Harness → extensions**.

An extension with npm dependencies (for example `openai-images`) needs `npm install` inside its directory in this checkout. `node_modules/` and extension-written runtime state are untracked.

The repository-owned [`compaction-model`](harness/pi/extensions/compaction-model/README.md) extension routes Pi's native compaction through a dedicated model. Select it in setup, then configure `compactionModel` in Pi's settings; no third-party extension package is needed.

The [`prompt-stash`](harness/pi/extensions/prompt-stash/README.md) extension uses **Cmd+Shift+S** to set aside a draft and restore it after the next interactive chat submission. Select it in setup; your terminal must forward the Command shortcut. Drafts stay in memory and are discarded on reload, session changes, or exit.

The experimental [`entire-graph`](harness/pi/extensions/entire-graph/README.md) extension exposes local graph search and change-impact tools. It requires an external graph binary and remains opt-in; see its [spike results](harness/pi/extensions/entire-graph/SPIKE.md) for the measured working-tree latency.

This repository's skills remain under `skills/`. They are written for Pi. Install or link them through Pi's documented discovery mechanism; installation paths are separate from this source checkout.

Use this repository as a local Pi package:

```sh
pi install /absolute/path/to/this-repository
```

For a one-run load without changing settings:

```sh
pi -e /absolute/path/to/this-repository
```

## Resource layout

- `harness/pi/APPEND_SYSTEM.md` contains Pi's repository-owned root-agent policy, linked by `./setup.sh` only when selected.
- `harness/pi/commands/` contains Pi-owned slash-command prompt templates.
- `harness/pi/docs/` contains Pi-owned plans and runbooks. It is not a Pi package resource.
- `harness/pi/extensions/` contains Pi extensions, each linked into Pi individually by `./setup.sh`.
- `skills/` contains Pi skills, installable into Pi or the global `~/.agents/skills` directory.
- `prompts/` contains system-prompt resources. `prompts/COMPRESSED_OUTPUT_MODE.md` is the current repository-owned prompt resource.
- `skill-factory/` contains skill authoring, validation, and evaluation resources.
- `tools/ghh/`, `tools/gs/`, and `tools/gw/` are independent tool packages.

Commands are flat. Recursive command directories, project-local command ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution remain outside the Pi extension's V1 scope.
