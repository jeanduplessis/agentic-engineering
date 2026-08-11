# Pi extensions maintenance context

## Ownership

This directory holds the canonical source of every Pi extension in this repository. Nothing under `~/.pi/agent/extensions/` is a source; those entries are symlinks created by `./setup.sh`. Edit files here.

## Installation contract

- `./setup.sh` discovers a subdirectory as an extension when it contains `index.ts`, `index.js`, or `package.json`. Keep one of those at the extension root.
- Selection is explicit and per-extension. Do not make an extension install by default.
- Installation is a symlink from `~/.pi/agent/extensions/<name>` to this directory. Do not add copy or build steps to activation.
- Enabling an extension in Pi `settings.json` is user configuration, not a repository concern.

## Runtime state

Extensions that resolve paths through `getAgentDir()` write into the installed symlink and therefore into this checkout. Keep such generated state untracked in the root `.gitignore`; `openai-extended-support/config.json` and `*/node_modules/` are already ignored.

## Dependencies

An extension with npm dependencies declares them in its own `package.json` and needs `npm install` run in its directory here. Do not vendor `node_modules/` into git.

## Change guidelines

When changing an extension's entry point, discovery shape, config paths, or dependencies, update that extension's `README.md` and `AGENTS.md`, the root `README.md` if the install contract changes, `setup.sh` discovery if the entry shape changes, and the root `CHANGELOG.md`.
