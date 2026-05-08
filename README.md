# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are for me, highly opinionated and personalized for how I prefer to work at this moment in time. I encourage you to build your own that is tailored to how you work best.

## Pi install/discovery

Use this repository as a local Pi package:

```sh
pi install /Users/jdp/.agents
```

For a one-run load without changing settings:

```sh
pi -e /Users/jdp/.agents
```

The package manifest exposes:

- `skills/` as Pi skills.
- `commands/*.md` as Pi prompt templates/slash commands.

## Pi resource layout

- `commands/` contains Pi prompt templates exposed as slash commands. Keep command files there; do not move them into `prompts/`.
- `prompts/` is reserved for system-prompt resources only.
- `prompts/APPEND_SYSTEM.md` is the repo-owned append-system prompt fragment. Keep it in place. To load it in Pi, explicitly copy or symlink it to `.pi/APPEND_SYSTEM.md` or `~/.pi/agent/APPEND_SYSTEM.md`.

## Extended commands workflow

`extensions/extended-commands/` is the local Pi extension that owns `commands/*.md` as the global command library. Runtime stays migration-friendly: it warns on unknown frontmatter or stale legacy syntax and passes command bodies through literally. `tools.command_valid` is the strict gate for certifying one clean Pi command.

Validate one command by name:

```sh
python3 -m tools.command_valid <command-name>
python3 -m tools.command_valid <command-name> --json
```

Clean command files use frontmatter with `description` plus optional `argument-hint`, `model`, `thinking`, `skill`, YAML-list `skills`, and `restore`. Model routing accepts exact `provider/model` or unique bare model IDs. `skill` and `skills` inject visible local skill context messages. `restore` defaults to `true`; set `restore: false` only for intentional sticky model/thinking switches.

Migration guidance: replace legacy OpenCode shell/file expansion such as ``!`cmd` `` or `@path` with explicit instructions for Pi to run commands or read files. Keep commands flat; recursive command directories, project-local ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution are out of V1 scope.
