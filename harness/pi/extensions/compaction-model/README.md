# Compaction model

Use a dedicated model for Pi's native compaction without changing the active conversation model. This repository owns the extension; no third-party extension package is required.

The extension calls Pi's exported `compact()` with its existing preparation. Pi still owns prompts, recent-message retention, split-turn summaries, previous-summary updates, file tracking, token budgets, usage accounting, and `/compact` focus instructions. It does not intercept `/tree` branch summaries.

## Enable

Run `./setup.sh` from the repository root. Choose **Harness → Pi → compaction-model** and confirm linking. Setup creates:

```text
~/.pi/agent/extensions/compaction-model → <checkout>/harness/pi/extensions/compaction-model
```

No `npm install` or build step is needed. Restart Pi or use `/reload`. If the upstream `pi-compaction-model` package is already installed, remove or disable it before enabling this extension; don't run both handlers.

## Configure

Add this section to your global Pi `settings.json` (normally `~/.pi/agent/settings.json`):

```json
{
  "compactionModel": {
    "model": "google/gemini-2.5-flash",
    "thinkingLevel": "low"
  }
}
```

Choose a model available in your Pi registry with working authentication. There is no default dedicated model: without configuration, Pi uses its active model as usual. The extension reads settings on each compaction and never writes them.

| Field | Behavior |
| --- | --- |
| `model` | Required `provider/model` reference. Model IDs may contain additional slashes. |
| `thinkingLevel` | Optional: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`. Omit or set to `null` for the provider default. Uses native Pi thinking behavior and model capabilities. |
| `reasons` | Defaults to `["manual", "threshold", "overflow"]`. Use a subset to limit routing; `[]` disables it. |
| `enabled` | Set to `false` to disable routing. The entire `compactionModel` section may also be `false`. |

For automatic compaction only:

```json
{
  "compactionModel": {
    "model": "google/gemini-2.5-flash",
    "reasons": ["threshold", "overflow"]
  }
}
```

A trusted project's `.pi/settings.json` can override individual fields. Project fields shallow-merge over global fields; `"compactionModel": false` disables routing for that project. Untrusted project settings are not read. Pi's agent-directory override and `CONFIG_DIR_NAME` are respected.

## Failure and compatibility

- Invalid configuration, unavailable models, authentication failures, and failed or empty model responses warn and leave compaction to Pi's active model. Invalid reason filters never expand to all reasons.
- User cancellation cancels compaction; it does not trigger a fallback request.
- Warnings appear in Pi's UI, or on stderr in headless modes. Raw provider errors and settings content are not logged.
- Requests use the effective registered provider, including custom streaming behavior, auth-resolved base URLs, headers, and provider environment.
- File lists from this extension's previous summary are restored for later compactions, including native fallback or disabled routing while the extension remains loaded. Unrelated extensions' details are not adopted.
- The selected model must have enough context for the prepared summary input. A smaller context window can cause a failure and fallback; the extension does not change Pi's cut point.
- Pi currently resolves the active conversation model's authentication before this hook, so that model also needs valid authentication.
- Avoid multiple compaction extensions handling the same reason. This extension does not control their ordering.

Verified against `@earendil-works/pi-coding-agent` 0.84.4. The native compaction API is the compatibility boundary; check it when upgrading Pi.

## Verification

From the repository root, with Node.js 22.18+:

```sh
node --test harness/pi/extensions/compaction-model/tests/*.test.mjs
```

Tests are offline and use temporary settings plus fake providers. Native integration and loader checks use a locally or globally installed Pi SDK and report a skip if it is absent. No model session is started.

## Attribution

Recreated from the behavior of [JMHSV/pi-compaction-model](https://github.com/JMHSV/pi-compaction-model) at commit `83bd7bc5a54f1b750497f6d1f66e25f5c3519e46`. The valid settings contract is compatible. This implementation rejects invalid filters, honors cancellation without fallback, and keeps requests on the registered provider path. The upstream MIT notice is retained in `LICENSE`.
