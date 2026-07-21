# extended-commands

Pi extension for command templates in `harness/pi/commands`.

## Source and activation

- `harness/pi/commands/*.md` is this repository's Pi-owned source. Edit source files only; do not generate or copy adapter-specific command artifacts.
- Root `package.json` exposes the templates through `pi.prompts`. This extension adds routing and skill behavior when activated.
- Activate the extension from Pi's extension discovery configuration. Keep activation links local, untracked, and pointed at `harness/pi/extensions/extended-commands`.
- This repository does not provide or activate OpenCode/Kilo commands. Use each downstream harness's native command locations for harness-local commands.

## Pi adapter behavior

- Loads direct Markdown files only and registers each filename stem as Pi slash command.
- Sends rendered body to Pi as user message; templates support `$ARGUMENTS` and simple positional `$1`, `$2`, etc.
- Supports exact `provider/model` routing, unique bare model IDs, valid Pi thinking levels, and default post-turn restore; `restore: false` stays sticky.
- Supports legacy scalar `skill` and YAML-list `skills`, injecting visible skill context before prompt and skipping already-loaded duplicates.
- Remains permissive for legacy files: unknown frontmatter and unsupported interpolation produce warnings, then body passes through literally.
- Preserves permissive adapter legacy behavior: `$@` still substitutes and `${@:...}` passes through literally.

No custom renderer is added. Deterministic command validation belongs to `PYTHONPATH=skill-factory python3 -m tools.command_valid <command-name>`.

## Manual smoke test

After activation, reload Pi extensions with `/reload` or restart Pi. Run a template containing `$ARGUMENTS` or `$1`; confirm rendered prompt arrives. For routed commands, confirm declared model/thinking apply and restore. For skill commands, confirm visible skill context appears before prompt.
