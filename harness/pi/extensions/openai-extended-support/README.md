# OpenAI Extended Support

This extension provides OpenAI priority mode, configurable model targets, subscription usage polling, and shared metrics for other extensions. It does not create a custom footer or a metrics footer line; usage may appear as a normal status value when enabled.

## Features

- `/fast [on|off|toggle]` and `--fast` for `service_tier: "priority"`.
- Exact provider/model target matching with per-target service tiers.
- Global and project config resolution; project values override global values.
- `/openai-usage` plus background OpenAI subscription usage polling.
- Shared token, cache, cost, context, thinking-level, and usage values through Pi's event bus.
- Request cancellation, stale-session handling, bounded diagnostics, credential redaction, and atomic config writes.

Usage polling requires `openai-codex` OAuth credentials from `/login openai-codex`. It only polls automatically for OpenAI subscription models when `showOnlyOnSubscriptionModels` is enabled. The usage endpoint is a private ChatGPT backend endpoint and may change.

## Configuration

The extension loads config from:

- Project: `.pi/openai-extended-support/config.json`
- User: `$PI_CODING_AGENT_DIR/extensions/openai-extended-support/config.json` (normally `~/.pi/agent/extensions/openai-extended-support/config.json`)

Project values override global values. An explicit `targets: []` disables all priority targets for that scope. If `targets` is omitted, the built-in defaults are used.

```json
{
  "enabled": true,
  "persistState": true,
  "targets": [
    {
      "provider": "openai-codex",
      "model": "gpt-5.6",
      "serviceTier": "priority"
    }
  ],
  "usage": {
    "enabled": true,
    "refreshIntervalMs": 60000,
    "showOnlyOnSubscriptionModels": true,
    "showResetTimes": true,
    "showStatus": true
  }
}
```

`persistState: false` makes `/fast` and `--fast` session-only. Target and usage configuration remains file-backed. Set `usage.showStatus` to `false` to keep polling and shared state without a usage status value.

## Shared state

The latest state is available at `globalThis.piOpenAIExtendedSupport` and through the `openai-extended-support:state` event:

```ts
type OpenAIExtendedSupportState = {
  desiredActive: boolean;
  supported: boolean;
  active: boolean;
  model: { provider: string; id: string } | undefined;
  serviceTier: string | undefined;
  usage: {
    enabled: boolean;
    snapshot: {
      fiveHourLeftPercent: number | null;
      sevenDayLeftPercent: number | null;
      fiveHourResetInSeconds: number | null;
      sevenDayResetInSeconds: number | null;
      isLimited: boolean;
    } | undefined;
    updatedAt: number | undefined;
    error: string | undefined;
    loading: boolean;
  };
  metrics: {
    totals: {
      input: number;
      output: number;
      cacheRead: number;
      cacheWrite: number;
      cost: number;
    };
    context: {
      tokens: number | undefined;
      contextWindow: number | undefined;
      percent: number | null | undefined;
    };
    thinkingLevel: string | undefined;
  };
};
```

Use `state.active === true` for effective priority mode. The extension intentionally leaves rendering these values to an opt-in footer/widget consumer.
