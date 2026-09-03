# Prompt stash maintenance

- `index.ts` is the dependency-free Pi extension entry point. Activation is opt-in through `./setup.sh`; no build, package install, or generated configuration is required.
- Keep exactly one private in-memory draft slot per extension instance. Never persist, log, emit, or send draft text to the model. Status and notifications may reveal only that a stash exists.
- Publish presence with `ctx.ui.setStatus("prompt-stash", ...)`. The key exists while a stash is pending and is removed after restoration/reset. Footer consumers use `footerData.getExtensionStatuses().has("prompt-stash")`, not display-text parsing. Keep this contract stable; do not modify `custom-footer` as part of this extension.
- Use `pi.registerShortcut("super+shift+s")`. Do not add fallback shortcuts or modify user terminal/keybinding settings.
- Preserve the exact editor API text, including whitespace and expanded pastes. An occupied editor must never be overwritten. Clear the slot only after verified restoration or session lifecycle reset.
- Restore synchronously from interactive TUI `input` without altering the input payload. Noninteractive and extension-injected messages must not consume the stash. Do not replace or patch the editor, add timers, or intercept commands to broaden coverage.
- Reset on session start and shutdown. Reload, session replacement, and exit intentionally discard the stash; keep the README warning explicit.
- SDK integration tests use native loader/editor/shortcut/input code with fake delivery endpoints. They must stay offline, skip explicitly if Pi is absent, and never start a model or read user credentials/configuration.
- Run `node --test harness/pi/extensions/prompt-stash/tests/*.test.mjs` and `git diff --check`. Update `README.md` and these tests when the public behavior changes; coordinate root documentation and changelog updates with the parent task.
