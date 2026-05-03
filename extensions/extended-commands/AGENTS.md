# extended-commands maintenance context

## Purpose

This extension registers the local global command library (`~/.agents/commands/*.md`) as Pi extension-owned slash commands.

## How it works

- Entry point: `index.ts`.
- Pure helpers (`parseArgs`, `substituteArguments`, `parseCommandFile`, `discoverCommands`, `registerExtendedCommands`) are exported for deterministic tests.
- Pi runtime entrypoint is the default export, which calls `registerExtendedCommands(pi)`.
- Discovery is global-only and flat; do not add recursive or project-local command ownership in V1.
- Runtime is permissive during migration: warn on unknown frontmatter or unsupported legacy syntax; do not fail plain command execution for those warnings.
- Model routing supports exact `provider/model` and unique bare model IDs. Ambiguous/missing/unavailable models fail before prompt send.
- Thinking routing uses Pi thinking levels and restores model/thinking after `agent_end` unless `restore: false`.
- Skill injection supports one declared `skill`, resolves local `SKILL.md`, sends a visible `extended-command-skill` custom message before the command prompt, and does not add a custom renderer.

## Eval and validation

Run focused extension tests:

```sh
python3 -m unittest extensions.extended-commands.tests.test_extended_commands -v
```

These tests import `index.ts` with Node's TypeScript stripping and use fake Pi APIs.

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing command discovery, argument substitution, frontmatter parsing, runtime warnings, routing, or registration behavior.
Keep activation/symlink changes out of this extension source slice; they are tracked separately.
