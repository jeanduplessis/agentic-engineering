# Setup, initialization, and integration

This skill is runtime-focused. Only initialize beads or change integration files when the user asks, when a project clearly already uses beads and needs recovery, or when setup is necessary to complete the requested task.

## Check before changing anything

```bash
bd --version
bd info
bd init --help
```

If `bd` is missing, tell the user and ask before installing. Do not run installer scripts without approval.

## Initialize a project when requested

Use the installed help to choose supported flags. Common current patterns:

```bash
bd init --quiet
bd init --quiet --skip-agents
bd init --quiet --skip-hooks
bd init --quiet --stealth
```

Explain side effects before setup:

- normal setup may create `.beads/` and project integration files;
- hook setup may change git hook files;
- stealth setup keeps beads usage local/private where supported;
- reinitialization or force flags may risk existing data.

For non-interactive agent runs, prefer quiet/non-interactive setup only after the user confirms the desired mode.

## Integration recipes

`bd setup` writes agent/editor instructions. Use it only when the user asks to configure an integration.

```bash
bd setup --list
bd setup <recipe> --check
bd setup <recipe>
bd setup <recipe> --remove
```

Use `bd setup --help` first because recipes and flags vary by version.

## What not to do by default

- Do not initialize silently just because a task could use durable tracking.
- Do not run reinitialization, migration, cleanup, or repair commands without explicit approval.
- Do not install hooks or editor integrations unless requested.
- Do not add project instruction files unless setup requires them and the user agrees.
