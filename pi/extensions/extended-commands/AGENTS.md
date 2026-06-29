# extended-commands maintenance context

## Purpose

Pi adapter over shared canonical Pi/OpenCode command source (`~/.agents/commands/*.md`).

## How it works

- Entry point: `index.ts`; default export calls `registerExtendedCommands(pi)`.
- Canonical source is shared. Never generate, copy, or rewrite adapter-specific command artifacts.
- Activation belongs to user configuration via symlink from Pi extension discovery; keep activation links untracked.
- Discovery is global-only and flat; do not add recursive or project-local ownership in V1.
- Runtime stays permissive during migration: warn on unknown frontmatter or unsupported legacy syntax; do not fail plain execution.
- Silently accept shared union fields `agent` and `subtask`; Pi adapter intentionally ignores their semantics.
- Shared source permits `$ARGUMENTS` and simple positions such as `$1`; preserve permissive adapter legacy behavior by still substituting `$@` and passing `${@:...}` literally.
- Model/thinking routing, restore behavior, skill injection, and duplicate-skill handling remain Pi adapter features.

## Eval and validation

```sh
python3 -m unittest extensions.extended-commands.tests.test_extended_commands -v
```

Tests import `index.ts` with Node TypeScript stripping and fake Pi APIs.

## Change guidelines

Update `README.md`, this `AGENTS.md`, and tests when changing discovery, argument substitution, frontmatter parsing, runtime warnings, routing, registration, or shared-source adapter behavior. Preserve permissive legacy runtime behavior.
