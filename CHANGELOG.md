# Changelog

## Unreleased

- Fixed `pi-ui-customization` text jumping during streamed tool calls by retaining one trailing padding row in collapsed text blocks, while preserving image-height rows and expanded spacing. Added offline renderer regression tests.
- Added a compaction-aware `◈` loaded-skills row to `custom-footer`, including symlinked paths, extension-contributed skills on resume/reload, and valid `SKILL.md` reads outside the advertised catalog. The marker uses the footer's shared symbol color, with full-width dividers above the skills and model sections while the model table stays compact. Added offline detection and footer lifecycle tests.
- Added the repository-owned `compaction-model` Pi extension: route native compaction through a dedicated model with trusted project overrides, reason filters, active-model fallback, cancellation handling, and offline tests. Installation remains opt-in through `setup.sh`.
- Shortened the `human-writing` description, retaining artifact examples and compact exclusions for ordinary chat, progress updates, and agent-facing instructions.
- Added Pi-only natural trigger evals with a frozen target-only read profile, catalog observation, trace-based activation/avoidance grades, and separate invalid/loading-error counts. Added explicit trigger validation opt-in, complete `human-writing` trigger fixtures, and offline protocol tests. Pi workflow metadata now distinguishes advertised skills from observed reads; trigger-to-workflow regression promotion is rejected.
- Fixed trigger catalog capture after the first live test: Pi redirects extension stdout to stderr, so the observer now writes a separate evidence file. Added offline transport coverage; original live traces and invalid grades were retained.
- Reworked `human-writing` as automatic guidance only for durable, human-facing prose. Added fact-preservation and voice safeguards, replaced blanket style rules and unsupported examples, and added maintenance guidance plus workflow and trigger eval cases.
- Tightened `human-writing` after live evaluation: distinguish selecting relevant source notes from preserving claims, omit incidental documentation history, and preserve tentative and exhaustive scope. Added the confirmed README regression and grader tests that accept equivalent dates, technical-term hyphenation, and evidence-gap phrasing.
- Clarified `human-writing` copy-ready delivery: editorial notes require a request and stay outside the artifact; no-change examples now return the original text. Preserved two observed Opus commentary failures as regressions and added separate cases for bounded repeated testing.
- Made native Pi compaction summary blocks clickable in `pi-ui-customization`, so clicking toggles the summary's expanded content.
- Collapsed every `pi-ui-customization` tool row by default. Clicking a block still expands that tool's output; the previous expand-hint, completed-`read`, and `edit`-only exceptions are gone.
- Rendered `cache-miss-gate` warnings as a dark amber chat block and dropped the compaction-cost footnote from that message.
- Pinned the custom Pi `frontend` agent to `kilo/moonshotai/kimi-k3` instead of the unavailable `kilo/kilo-internal/kimi-k3-fast`.
- Switched Pi subagent orchestration to nicobailon `pi-subagents@0.47.1`. `pi-ui-customization` dropped the `@tintinweb/pi-subagents` conversation viewer, manager symbol, and `subagent_type` handling; click-to-expand remains, and a missing viewer is a no-op. `improve-codebase-architecture` now launches `scout` through `subagent` instead of `Agent` / `Explore`.
- Added `harness/pi/docs/switch-to-nicobailon-pi-subagents.md`, the execution plan to replace `@tintinweb/pi-subagents` with nicobailon's `pi-subagents` while keeping Firecrawl for web access.
- Collapsed `edit` tool rows by default in `pi-ui-customization`. Pi always renders the full diff, so the extension now treats those rows as clickable and shows only the command plus last visible line until expanded.
- Fixed `session-title` failing on reasoning models that reject `reasoning_effort: none`, which left `custom-footer` stuck on `New session`. Title generation now sends the cheapest supported non-off effort, and Kilo marks missing off/none variants as unsupported so Pi does not send `none` for models such as `kilo-internal/galaxy`.
- Fixed `session-title` never persisting a name for `custom-footer`, which left new sessions stuck on `New session`. Title generation now uses the session model registry, treats empty or failed model replies as errors, retries once after the next settled turn, and times out hung requests.
- Recolored successful `SKILL.md` read blocks in `pi-ui-customization` from the green tool-success background to the theme's purple custom-message background.
- Fixed `pi-ui-customization` breaking inline images from the `read` tool by leaving Kitty and iTerm2 graphics sequences unmodified.
- Moved the `cache-miss-gate`, `pi-ui-customization`, `custom-footer`, `kilo-pi-provider`, `openai-extended-support`, `openai-images`, and `session-title` Pi extensions from `~/.pi/agent/extensions` into `harness/pi/extensions`, making this checkout their source of truth.
- Changed `setup.sh` to install Pi extensions through an explicit per-extension selection that symlinks each choice into the Pi agent extensions directory, replacing the previous link-everything behavior.
- Added `harness/pi/extensions/AGENTS.md` and documented the extension source and install contract in `README.md` and the root `AGENTS.md`.
- Ignored Pi extension runtime state written through the install symlink (`harness/pi/extensions/*/node_modules/` and `openai-extended-support/config.json`).
- Updated `pi-ui-customization` to hide inline expansion hints and show darker collapsed and lighter expanded left gutters.
- Renamed the clickable tool expansion extension to `pi-ui-customization`.
- Added the shared `code-quality` skill and moved local review onto a packet-based `code-review-workflow` that orchestrates those quality agents.
- Updated the `flesh-out` workflow to present one recommendation with at most two variations and prompt for acceptance or custom feedback.
- Added a repository-level changelog.
- Require repository changes to be documented here before they are pushed to `origin`.
