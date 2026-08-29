# Compaction model maintenance

- Canonical source: this directory. `index.ts` is the Pi entry point and setup discovery marker; activation is an opt-in symlink, with no dependencies or build step.
- `config.ts` reads global and trusted project `settings.json` only. Keep the `compactionModel` contract documented in `README.md`; never write user settings or read untrusted project configuration.
- Delegate summary generation to Pi's exported `compact()`. Preserve preparation, custom instructions, signal, native result fields, provider auth/base URL/header deletions/environment, and effective provider streaming behavior. Never switch the conversation model.
- Failed requests return control to Pi; aborted requests return `{ cancel: true }`. Never log raw provider errors, credentials, settings, or conversation content.
- Native preparation skips `fromHook` file lists. Restore only the latest compaction's lists marked `details.compactionModel === true`, including when routing is disabled or falls back. Keep native file-list fields intact.
- Deterministic verification: `node --test harness/pi/extensions/compaction-model/tests/*.test.mjs` from the repository root (Node 22.18+). Native integration/loader tests require an installed Pi SDK; check for skips. No live model calls without explicit approval.
- On Pi upgrades, verify the exported `compact()` signature and the registered provider's `streamSimple()` contract. Retain the upstream MIT notice and update README compatibility notes and root changelog when behavior changes.
