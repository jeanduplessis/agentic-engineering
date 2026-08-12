# Proposal: persistent agent history

## Status

Superseded for the tintinweb runtime. `pi-ui-customization` no longer opens an in-process conversation viewer, does not read `Symbol.for("pi-subagents:manager")`, and does not interpret `subagent_type`. Nicobailon `pi-subagents` runs children as separate `pi` processes and already exposes FleetView, session artifacts, and status/steer.

Do not rebuild tintinweb's in-process viewer. If persistent history is still needed after cutover, design it against nicobailon artifacts and FleetView rather than a live in-memory `AgentSession`.

## Original problem

`pi-ui-customization` could open an inline tintinweb `Agent` result while that extension still held an in-memory record. That record was normally cleaned up about 10 minutes after completion. After cleanup, the inline block had no session to open.

The smallest durable solution on that runtime was to support agents whose configuration set `persist_session: true`, record the persisted session path, then reopen that path when a later click no longer found the live record.

## Why this is no longer the first version

- Inline `subagent` rows now use the same collapse/click-to-expand path as other tools. A missing viewer is a no-op.
- Child conversations live in nicobailon session/artifact storage, not a parent-process manager registry.
- FleetView and `/subagents-fleet` are the packaged inspection surface.

## If history is revisited

Prefer nicobailon-owned data:

- session-scoped artifacts when `artifactDir: "session"`
- child session files under the configured session directory
- Fleet history already restored by the package

Keep these constraints if a later `pi-ui-customization` lookup is added:

1. Fail safely when a recorded file was deleted, moved, or belongs to an older incompatible format.
2. Keep any index local to the parent Pi session or agent directory.
3. Avoid storing prompts or model output in a second index when a session file already contains them.
4. Do not steer or stop historical sessions from a click-to-expand row.

## Non-goals

- Rebuilding the tintinweb conversation viewer.
- Persisting every in-memory child automatically.
- Reconstructing a full parent-process `AgentSession` with tools and extension bindings.
