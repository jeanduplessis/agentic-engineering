# Changelog

## Unreleased

- Pinned the custom Pi `frontend` agent to `kilo/moonshotai/kimi-k3` instead of the unavailable `kilo/kilo-internal/kimi-k3-fast`.
- Added `harness/pi/docs/switch-to-nicobailon-pi-subagents.md`, the execution plan to replace `@tintinweb/pi-subagents` with nicobailon's `pi-subagents` while keeping Firecrawl for web access.
- Fixed `session-title` never persisting a name for `custom-footer`, which left new sessions stuck on `New session`. Title generation now uses the session model registry, treats empty or failed model replies as errors, retries once after the next settled turn, and times out hung requests.
- Recolored successful `SKILL.md` read blocks in `pi-ui-customization` from the green tool-success background to the theme's purple custom-message background.
- Fixed `pi-ui-customization` breaking inline images from the `read` tool by leaving Kitty and iTerm2 graphics sequences unmodified.
- Made inline `Agent` results clickable in `pi-ui-customization`, opening the optional `@tintinweb/pi-subagents` conversation viewer when a live session is available.
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
