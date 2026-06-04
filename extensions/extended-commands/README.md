# extended-commands

Pi adapter over shared canonical command source at `~/.agents/commands`.

## Source and activation

- `commands/*.md` is canonical source shared by Pi and OpenCode. Edit source files only; do not generate or copy adapter-specific command artifacts.
- Activate Pi extension with a symlink from Pi extension discovery to `~/.agents/extensions/extended-commands`; keep symlink untracked and pointing at source.
- Activate OpenCode commands with a symlink from OpenCode command discovery to canonical `~/.agents/commands`; do not maintain a second command tree.
- Root package manifest exposes same source to Pi prompt discovery. Extension adds routing and skill behavior when activated.

## Pi adapter behavior

- Loads direct Markdown files only and registers each filename stem as Pi slash command.
- Sends rendered body to Pi as user message; shared source supports `$ARGUMENTS` and simple positional `$1`, `$2`, etc.
- Silently accepts shared union frontmatter `agent` and `subtask`; Pi adapter does not implement their OpenCode semantics.
- Supports exact `provider/model` routing, unique bare model IDs, valid Pi thinking levels, and default post-turn restore; `restore: false` stays sticky.
- Supports legacy scalar `skill` and YAML-list `skills`, injecting visible skill context before prompt and skipping already-loaded duplicates.
- Remains permissive for legacy files: unknown frontmatter and unsupported OpenCode shell/file interpolation produce warnings, then body passes through literally.
- Preserves permissive adapter legacy behavior: `$@` still substitutes, `${@:...}` passes through literally, and strict validator rejects both from shared source.

No custom renderer is added. Strict source certification belongs to `python3 -m tools.command_valid <command-name>`.

## Manual smoke test

After symlink activation, reload Pi extensions with `/reload` or restart Pi. Run a canonical command containing `$ARGUMENTS` or `$1`; confirm rendered prompt arrives. For routed commands, confirm declared model/thinking apply and restore. For skill commands, confirm visible skill context appears before prompt.
