# extended-commands maintenance context

## Purpose

Pi extension for this repository's Pi-owned command source (`harness/pi/commands/*.md`).

## How it works

- Entry point: `index.ts`; default export calls `registerExtendedCommands(pi)`.
- Load command templates from `harness/pi/commands/`. Do not generate, copy, or rewrite adapter-specific command artifacts.
- Activation belongs to user configuration via symlink from Pi extension discovery; keep activation links untracked.
- Discovery is global-only and flat; do not add recursive or project-local ownership in V1.
- Runtime stays permissive during migration: warn on unknown frontmatter or unsupported legacy syntax; do not fail plain execution.
- Templates support `$ARGUMENTS` and simple positions such as `$1`; preserve permissive legacy behavior by still substituting `$@` and passing `${@:...}` literally.
- Model/thinking routing, restore behavior, skill injection, and duplicate-skill handling remain Pi adapter features.

## Eval and validation

```sh
python3 -m unittest harness.pi.extensions.extended-commands.tests.test_extended_commands -v
```

Tests import `index.ts` with Node TypeScript stripping and fake Pi APIs.

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing discovery, argument substitution, frontmatter parsing, runtime warnings, routing, or registration. Preserve permissive legacy runtime behavior.
