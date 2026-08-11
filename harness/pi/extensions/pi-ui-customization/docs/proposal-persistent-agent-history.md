# Proposal: persistent agent history

## Summary

`pi-ui-customization` can open an inline `Agent` result while the subagents extension still holds its in-memory record. That record is normally cleaned up about 10 minutes after completion. After cleanup, the inline block has no session to open.

The smallest durable solution is to support agents whose configuration sets `persist_session: true`. The extension would record the persisted session path when the agent starts or completes, then reopen that path when a later click no longer finds the live record.

Supporting history for every agent, including agents that use in-memory sessions, is a larger feature. Those agents currently have no Pi session file. Their optional output transcript is JSONL in the system temporary directory and is not a durable session store.

## Current behavior

- The clickable inline result resolves a live record through `globalThis[Symbol.for("pi-subagents:manager")]`.
- The record contains the live `AgentSession`, which the existing pi-subagents conversation viewer can render.
- `AgentManager` removes completed records after roughly 10 minutes and disposes their sessions.
- A session switch can remove completed records sooner when their result has already been consumed.
- `persist_session` is an agent configuration option. When enabled, the subagent uses `SessionManager.create()`; otherwise it uses `SessionManager.inMemory()`.
- The pi-subagents completion event and its parent-session `subagents:record` entry do not currently include the child session file path.
- Output transcripts, when enabled, are written below the OS temporary directory. They are useful for short-term recovery but may disappear after a reboot and are not in Pi session format.

## Goals

1. Let a completed, persisted subagent be opened from its inline result after the live record has been cleaned up.
2. Keep the existing live-session viewer and click behavior unchanged.
3. Fail safely when a recorded file was deleted, moved, or belongs to an older incompatible format.
4. Keep the history index local to the parent Pi session or agent directory.
5. Avoid storing prompts or model output in a second index when a session file already contains them.

## Non-goals for the first version

- Persisting every in-memory subagent automatically.
- Reconstructing a full `AgentSession` with a model, tools, and extension bindings.
- Editing or steering a historical session.
- Changing the installed pi-subagents package.
- Making temporary output transcripts permanent without an explicit retention choice.

## Recommended first version

### 1. Capture session metadata

Listen for `subagents:started` and `subagents:completed`. While the record is still available, resolve it from the pi-subagents manager registry and capture:

- agent ID
- type and description
- parent working directory
- start and completion timestamps
- whether the record is persisted
- `session.sessionManager.getSessionFile()` when available
- output transcript path, if available

Only the session path and display metadata need to go into the lookup index. The conversation remains in the Pi session file.

### 2. Store an index entry

Store a small custom entry in the parent session, for example:

```text
customType: pi-ui-customization:agent-history
```

The entry data should contain the agent ID, description, status, timestamps, and session path. Appending it to the parent session means the index follows the parent session and does not require a separate database.

A separate file under the Pi agent directory is another option, but it needs its own cleanup, locking, and session ownership rules. The parent-session custom entry is simpler for the first version.

### 3. Use two lookup paths on click

1. Look up the live record, as today.
2. If it is gone, read the parent session's history entries, validate the stored path, and open the persisted session with `SessionManager.open()`.

The persisted session is read-only. The current conversation viewer expects an `AgentSession`-like object, so the implementation can either:

- pass it a small read-only adapter backed by `SessionManager.buildSessionContext().messages`; or
- add a history-only viewer that renders `SessionManager` entries directly.

The adapter is the smaller change. It should disable stop and steer actions for historical sessions and keep Esc-to-close and scrolling.

### 4. Handle missing and stale entries

If the session path no longer exists, show a notification such as `The subagent session is no longer available.` Do not fall back to an arbitrary session with the same description. Index entries can be pruned when their files disappear or when they exceed a chosen retention period.

## Supporting all agents later

To make default in-memory agents durable, the extension would need to copy or convert their output before the record is discarded. The current output transcript is a temporary JSONL sidecar, not a `SessionManager` file. Possible choices are:

- copy the transcript to a Pi-owned history directory;
- convert it to a Pi session file;
- keep a separate read-only transcript viewer.

The last option avoids pretending that a transcript is a resumable Pi session, but it would require a second renderer and different behavior for persisted and in-memory agents. It also raises retention and privacy questions because prompts, tool calls, and results would be kept beyond the normal temporary lifetime.

## Risks and decisions

- **Package coupling:** The current integration already relies on pi-subagents' private global manager symbol and viewer module. A durable lookup adds coupling to `SessionManager` file layout and the `persist_session` behavior. A small public history hook in pi-subagents would be cleaner, but would require an upstream or local package change.
- **Retention:** Decide whether history follows the parent session forever, uses a time limit, or is pruned when the child file disappears.
- **Privacy:** Session files contain prompts, tool calls, and results. The index should store paths and metadata only, and the feature should not copy content by default.
- **Path safety:** Validate stored paths before opening them. Prefer paths under the configured Pi session directory or the explicitly configured child `session_dir`.
- **Compaction:** `buildSessionContext()` is compaction-aware. A history viewer must make clear that it shows the active session path, not necessarily every pre-compaction message.
- **Restart behavior:** The index must be reconstructed from the parent session before clicks can resolve old agents. The live manager registry is unavailable for old records.
- **Agent ID reuse:** Use the stored session path as the identity after lookup, not description or type. Descriptions are not unique.

## Verification plan

The first version should cover:

1. A live running agent still opens the current viewer.
2. A completed persisted agent opens after its live record is removed.
3. A missing session file produces a notification and does not throw.
4. A session switch and Pi restart reconstruct the index from the parent session.
5. Two agents with the same description resolve to different session files.
6. In-memory agents remain unchanged and continue to expire normally.
7. Historical viewers cannot steer or stop the agent.

## Effort estimate

- Persisted agents only: about half a day for implementation and focused tests.
- Durable history for all agents: roughly one to two days, mostly for transcript retention, history rendering, cleanup, and restart behavior.

The persisted-agents-only version is the right starting point. It adds useful lookup without silently changing how much agent conversation is retained on disk.
