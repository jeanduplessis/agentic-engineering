# Agentic Engineering

> [!NOTE]
> Feel free to fork, modify and use as you like, however, this is not a collaborative OSS project. I'm not accepting PRs and not responding to issues. These tools are personalized for how I work.

## Shared command source

`commands/*.md` is canonical command source shared by Pi and OpenCode. Edit canonical files only. Do not generate, copy, or commit adapter-specific command artifacts.

- Pi package discovery reads canonical source through root `package.json` `pi.prompts`.
- `extensions/extended-commands/` is permissive Pi adapter adding routing and skill behavior over same source.
- OpenCode command discovery should symlink `~/.config/opencode/commands` to canonical `commands/` rather than maintain a second tree.
- Kilo, an OpenCode-compatible harness, should symlink `~/.config/kilo/commands` to canonical `commands/`.
- Pi extension activation should symlink Pi extension discovery to `extensions/extended-commands/`; activation symlinks are local and untracked.
- Skills remain canonical under `skills/`; harness config paths may symlink to them when `~/.agents/skills` is not discovered automatically.

Source contract permits harmless Pi/OpenCode union frontmatter, including `agent` and `subtask`. Source placeholders are `$ARGUMENTS` and simple positional `$1`, `$2`, etc. Do not use `$@`, `${@:...}`, or OpenCode shell/file interpolation. Commands declaring skills must include matching explicit `## Required skills` body list so every harness can load required context.

Validate one canonical command:

```sh
python3 -m tools.command_valid <command-name>
python3 -m tools.command_valid <command-name> --json
```

Validator is strict and shared-source focused. Pi adapter stays migration-friendly: it silently accepts `agent`/`subtask`, warns on unknown or legacy syntax, and passes legacy bodies through literally. Inventory tests require every canonical command to pass the shared contract.

## Harness activation

Use symlinks when a harness does not discover `~/.agents/` directly. Keep symlinks local and untracked; never copy or generate harness-specific variants.

```sh
ln -s /Users/jdp/.agents/commands ~/.config/opencode/commands
ln -s /Users/jdp/.agents/commands ~/.config/kilo/commands
```

Use repository as local Pi package:

```sh
pi install /Users/jdp/.agents
```

For one-run load without changing settings:

```sh
pi -e /Users/jdp/.agents
```

Manifest exposes `skills/` as Pi skills and canonical `commands/*.md` as Pi prompt templates/slash commands.

## Resource layout

- `commands/` contains canonical shared Pi/OpenCode commands.
- `skills/` contains canonical shared-harness skills; harness-specific metadata may add capability but cannot replace shared behavior.
- `extensions/extended-commands/` contains Pi adapter source, never generated command copies.
- `prompts/` is reserved for system-prompt resources only.
- `prompts/APPEND_SYSTEM.md` is repo-owned append-system fragment. Load it by explicitly copying or symlinking it to `.pi/APPEND_SYSTEM.md` or `~/.pi/agent/APPEND_SYSTEM.md`.

Keep commands flat. Recursive command directories, project-local ownership, deterministic shell execution, loops, chains, parallel execution, worktrees, subagents, and agent-callable prompt execution remain outside adapter V1 scope.
