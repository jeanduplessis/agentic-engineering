# Custom footer specification

## Purpose

Replace Pi's footer with a generated session title, compact session summary, and, when a session uses more than one model, a per-model usage table.

## Example

```text
_Refactor authentication middleware_                  ~/project • main
𐘱100k 78%                                          openai/gpt-5.6-sol • high
↑12k ↓8k ⚛︎5k ▦196k/87% ⇢42t/s $15.78                            $573.60
────────────────────────────────────────────────────────────────────────────
  Model                                                Steps      Cost
➤ openai/gpt-5.6-sol                                     10    $12.50
➤ anthropic/claude-sonnet-4-5                              3     $3.24
➤ google/gemini-2.5-pro                                    3     $0.04
```

## Session title and location

Render the session name, or the italic `New session` placeholder when no name is
available yet, as a left-aligned title with the current location right-aligned on
the same row:

```text
<session title>                                      ~/project • main
```

Read the session name during rendering from the latest `session_info_changed`
value, `pi.getSessionName()`, or `ctx.sessionManager.getSessionName()`.
Show `New session` while the generated title is not available yet. Middle-truncate
the title when necessary so the line fits the available width. Always
show the current working directory, even when no session name exists. Replace the
user's home directory with `~`, and show at most the final 30 characters of the
resulting path. When the working directory is inside a Git repository, append the
current branch as `cwd • branch`; otherwise show only `cwd`.

## Summary rows

The summary occupies the first two rows after the session/location row.

### Row 1: context and current model

```text
𐘱<context tokens> <context percent>                    <model> • <thinking level>
```

- Left-align context information.
- Right-align the current model and thinking level.
- `𐘱` means current context-window usage.
- Show only the number of tokens currently in context. Do not show the model's total context-window size.
- Format context tokens with a lowercase `k`, `m`, `b`, or `t` multiplier and round up. Show at most three digits before the multiplier; values below 10m/10b/10t may use one decimal (for example, `11,001` becomes `12k` and `3,153,000` becomes `3.2m`).
- Round context percentage up to the next whole number.
- Color the context percentage:
  - 70% or less: normal text
  - More than 70% and up to 85%: amber
  - More than 85%: red
- Display the model identifier in provider-qualified form when needed, for example `openai/gpt-5.6-sol`.
- When the OpenAI Extended Support state has `active === true`, prefix the current model with `⚡︎ ` and render that marker in the thinking-level accent color.
- Separate the model and thinking level with ` • `.

### Thinking-level colors

Color the thinking-level value using the selected level's color. Use the fixed low-thinking blue for summary-row symbols.

| Level | Color |
| --- | --- |
| `off` | Dim gray |
| `minimal` | Muted cyan |
| `low` | Ice blue |
| `medium` | Yellow |
| `high` | Amber |
| `xhigh` | Red |
| `max` | Purple |

### Row 2: session usage and Kilo balance

```text
↑<input> ↓<output> ⚛︎<reasoning> ⍈<cache reads>/<cache hit> ⇢<rate>t/s $<cost>    <Kilo balance>
```

- Left-align session usage.
- Right-align the Kilo balance.
- Read the formatted balance published by the custom Kilo provider through the live `kilo-credits` extension status, preserving its text and styling.
- Show the Kilo balance only when the current model's provider is `kilo` (the Kilo gateway).
- Omit the Kilo balance when that status is unavailable or the current model is served by another provider.

Render each metric's leading symbol (`𐘱`, `↑`, `↓`, `⚛︎`, `▦`, `⇢`, and `$`) in the fixed low-thinking blue accent color. Render each value normally.

The metrics are:

| Display | Meaning |
| --- | --- |
| `↑12k` | Cumulative input tokens |
| `↓8k` | Cumulative output tokens |
| `⚛︎5k` | Cumulative reasoning/thinking tokens |
| `▦196k/87%` | Cumulative cache-read tokens and prompt-cache hit percentage |
| `⇢42t/s` | Output rate for the latest completed model response |
| `$15.78` | Cumulative session cost |

Rules:

- Format token counts with a lowercase `k`, `m`, `b`, or `t` multiplier and round up. Show at most three digits before the multiplier; values below 10m/10b/10t may use one decimal.
- Reasoning tokens are a subset of output tokens, not an additional output total.
- Treat reasoning as unavailable when a provider does not report a reasoning breakdown.
- Show cumulative cache-read tokens before the cache hit percentage, separated by `/`.
- Apply the same compact token formatting to cumulative cache reads (for example, `3,153,000` becomes `3.2m`).
- Calculate cumulative cache hit percentage as:

  ```text
  cacheRead / (input + cacheRead + cacheWrite) × 100
  ```

- Round cache hit percentage up to the next whole number.
- Measure output rate from assistant response start through completion of the latest completed assistant response. This includes time to first output and avoids inflated rates when tool-call events arrive with buffered arguments.
- Calculate output rate as output tokens divided by elapsed response time.
- Round output rate down to a whole number.
- Do not put a space between the rate value and `t/s`.
- Always render cost in dollars with two decimal places, including `$0.00`.
- Session totals cover the entire session file, including abandoned tree branches, tool-reported nested model usage, compaction summaries, and branch summaries. This matches Pi's built-in cost-accounting scope.

## Unavailable values

Use `﹍` for unavailable values. Do not use an em dash.

Examples:

```text
𐘱﹍ ﹍%
↑12k ↓8k ⚛︎﹍ ⍈0k/﹍% ⇢﹍t/s $0.00
```

A confirmed zero is `0` or `0k`, not `﹍`.

### Row 3: subscription quota

When OpenAI Extended Support reports a supported model and quota snapshot, render:

```text
⧖ 7d 94%/↺ Tue 3:00 PM
```

Use the seven-day remaining percentage and reset clock. Omit the row when the model is unsupported or no quota snapshot is available.

## Per-model table

Show the model table only after more than one model has produced an assistant response in the session.

### Divider

- Put a divider between the two summary rows and the model table.
- Fill the available terminal width with `─`.
- Render the divider in the theme's dim color.

### Header

```text
  Model                                                Steps      Cost
```

- Render the header in the theme's dim color.
- Left-align `Model` with model identifiers after accounting for the row marker.
- Right-align `Steps` and `Cost` over their columns.

### Rows

```text
➤ openai/gpt-5.6-sol                                     10    $12.50
```

- Prefix every model row with `➤ `.
- Do not use a distinct current-model indicator.
- Left-align model identifiers.
- Right-align step counts and costs.
- Do not append a symbol such as `×` to the step count.
- A step is one completed assistant message produced by that model, including intermediate tool-calling responses.
- Group assistant messages by their provider and model identity. For display, use the message's model identifier when it is already provider-qualified; otherwise display `<provider>/<model>`.
- Order models by first use in the session.
- Sum each model's assistant-message costs for its row.
- Model-table costs always use two decimal places.
- Usage that has a cost but no attributable provider/model may be represented by an `other` row so the table reconciles with the session total.

## Responsive behavior

Preserve data rather than silently dropping metrics.

1. At wide widths, keep the optional title, summary rows, subscription quota, and aligned model table shown in the example.
2. Use one space between metrics; at medium widths, add rows when they no longer fit.
3. At narrow widths, move the current model, Kilo balance, or usage groups onto additional rows.
4. Middle-truncate long model identifiers only after reflow is no longer practical.
5. Keep model-table numeric columns right-aligned whenever their headers and values fit.
6. Every rendered line must fit the width supplied by Pi's TUI.

## Pi integration

- Install the footer with `ctx.ui.setFooter(...)`.
- Read the Kilo balance during rendering from:

  ```ts
  footerData.getExtensionStatuses().get("kilo-credits")
  ```

- Do not cache the Kilo status at footer construction time because Kilo fetches and refreshes it asynchronously.
- Subscribe to branch changes and request a render so Git/session state remains current.
- Re-render after message completion and again at turn end, because Pi emits `message_end` before persisting the finalized message. Also re-render after session-info changes, model selection, thinking-level selection, Kilo status updates, and `openai-extended-support:state` events.
- Subscribe to `session_info_changed` so an asynchronously generated title appears immediately. Cache `event.name` and also re-read `pi.getSessionName()` during render.
- Read the OpenAI Extended Support state from the `openai-extended-support:state` event and show the priority marker only when `active === true`.
- Only one custom footer can be active. This extension must install its footer after Kilo's own footer installation or provide a command that reinstalls it.

## Glyph compatibility

`𐘱` requires a terminal font with Linear A Unicode coverage. If the terminal renders it as a missing-glyph box or assigns an unexpected cell width, the user must select a compatible font; the extension must still enforce terminal-width limits using ANSI-aware visible-width utilities.
