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

## Pi UI customization

- `pi-ui-customization` patches private Pi renderer methods. Keep patches idempotent across reloads and preserve native input and URL forwarding.
- User-message bubbles fit rendered text up to a responsive wrapping limit, align right, and retain native top/bottom padding and left-aligned Markdown. Keep OSC 133 prefixes at byte zero for fullscreen prompt navigation and stripping. Keep other message layouts unchanged and do not prefix terminal-image protocol lines.
- Link hover uses the visible fullscreen frame and OSC 22 only on known compatible terminals outside multiplexers. Reset pointer state on focus loss, shutdown, and terminal stop.
- Keep successful collapsed built-in text `read` cards, including `SKILL.md` reads, title-only without a synthetic preview. Preserve native expanded content, errors, and images.
- Keep successful collapsed built-in `edit` cards title-only, even when the renderer owns its shell; identify its renderer functions rather than exempting all tools named `edit` from self-shell protection. Preserve errors, partial results, native expanded diffs, and custom self-shell framing and safety/detail rows.
- Run its offline Node SDK tests when changing these patches or upgrading Pi; terminal appearance still needs manual verification.

## Change guidelines

When changing an extension's entry point, discovery shape, config paths, or dependencies, update that extension's `README.md` and `AGENTS.md`, the root `README.md` if the install contract changes, `setup.sh` discovery if the entry shape changes, and the root `CHANGELOG.md`.
