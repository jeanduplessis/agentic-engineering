# Switch Pi subagents to nicobailon

Replace `@tintinweb/pi-subagents@0.14.3` with `pi-subagents@0.47.1` (`nicobailon/pi-subagents`). Adopt that extension’s roles, tools, and defaults. Customize only through its settings, agent overrides, and custom agent files.

This is not a 1:1 port of the current Explore / General / Frontend runtime.

## Locked decisions

- Roles: `scout`, `worker`, `reviewer`, `oracle` (`advisor` alias), `delegate`, plus a thin custom `frontend`.
- Delete `explore` and `general`. Do not set `disableBuiltins`.
- Web access stays Firecrawl. Do not install `pi-web-access`. Eject `researcher` and point it at the Firecrawl skill.
- Parent orchestration uses `subagent` + `workflowScript`, FleetView, status/steer, and the packaged parent skill.
- Leave builtin prompts, tool allowlists, and `inheritSkills: false` alone except where a setting must change.
- Leave nested-depth and async defaults. Builtin children cannot spawn children unless `tools` includes `subagent`.
- Teach Code to wait/status instead of forcing foreground.
- Keep `frontend` because it is a real split: `kilo/moonshotai/kimi-k3` plus the native-file path guard.
- Do not rebuild tintinweb’s in-process conversation viewer before cutover.
- Do not check agent files into this repository in v1.

## Current vs target

Tintinweb is in-process and Claude Code-shaped (`Agent`, `get_subagent_result`, `steer_subagent`). Nicobailon starts child `pi` processes and exposes one parent tool, `subagent`.

```text
User
  └── Code (root Pi session)
        APPEND_SYSTEM.md           role, routing, Firecrawl, integration
        packaged pi-subagents skill  how to call subagent

        scout        recon; may write context.md
        researcher   ejected: Firecrawl only
        oracle       second opinion, no edits
        worker       default implementation
        frontend     React/web-only worker + path guard
        reviewer     evidence-only review
        delegate     parent-twin; rarely used
```

Default loop: `clarify → scout → worker → fresh reviewers → worker`.

- Web facts: `researcher` (Firecrawl).
- Risky calls: `oracle`.
- Confirmed React/web UI: `frontend`, not `worker`.

## What not to do

- No Explore / General compatibility layer or `subagent_type` guard.
- No `agent-orchestration-guard` after cutover.
- No `pi-web-access`.
- Do not strip `scout`’s `bash`/`write` or worker’s strict tool allowlist.
- Do not install both subagent packages in one session.

## Ownership

| Owner | Files |
|---|---|
| User Pi home | `~/.pi/agent/settings.json`, `APPEND_SYSTEM.md`, `AGENT_ORCHESTRATION.md`, `agents/researcher.md`, `agents/frontend.md`; delete `agents/explore.md`, `agents/general.md`, `subagents.json`, `extensions/agent-orchestration-guard.ts` |
| This repo | `harness/pi/extensions/pi-ui-customization/**`, `skills/improve-codebase-architecture/**`, `CHANGELOG.md` |

`setup.sh` does not install the subagent package. Do not add that in v1.

## Phase 0 — prepare while tintinweb is still running

Write the new files first so the first nicobailon session is already consistent.

### 0a. Root prompt

Rewrite `~/.pi/agent/APPEND_SYSTEM.md`:

- Drop `Agent`, `get_subagent_result`, `steer_subagent`, Explore, and General.
- Route with nicobailon names and `subagent({ workflowScript })`.
- Background work: `status`, `subagent_wait`, `steer`.
- Web: Firecrawl via `researcher` or the Firecrawl skill. Never `web_search`.
- Keep Code as owner of integration, verification, and the user-facing answer.
- Keep the thin `frontend` eligibility gate.
- Do not restate the packaged tool schema.

Rewrite `~/.pi/agent/AGENT_ORCHESTRATION.md` to this target. It is the install/runbook, not a Kilo migration doc.

### 0b. Ejected `researcher`

Create `~/.pi/agent/agents/researcher.md` so it shadows the builtin:

```yaml
---
name: researcher
description: Web researcher that uses Firecrawl and returns a sourced brief
tools: read, write, bash, ls
skills: firecrawl
inheritSkills: false
inheritProjectContext: true
thinking: medium
systemPromptMode: replace
output: research.md
defaultProgress: true
---
```

Prompt: keep the builtin brief shape. Load the Firecrawl skill and use the `firecrawl` CLI. Do not mention `web_search`, `fetch_content`, or `get_search_content`.

### 0c. Thin `frontend`

Replace `~/.pi/agent/agents/frontend.md`:

- `model: kilo/moonshotai/kimi-k3`
- Worker-like tools: `read, grep, find, ls, bash, edit, write, contact_supervisor`
- `inheritProjectContext: true`
- `skills: agent-browser, react-doctor`
- `acceptanceRole: writer`
- Keep `<!-- pi-subagent-role: frontend-path-guard -->`
- Short prompt: web-only gate, no native files, report to Code
- Load `frontend-path-guard` with a real path in `extensions` or `subagentOnlyExtensions`

Delete `explore.md` and `general.md` in the same sitting as the package swap so they never appear beside `scout`/`worker`.

### 0d. Settings overlay

Draft this in `~/.pi/agent/settings.json`, but apply it at swap time:

```json
{
  "subagents": {
    "agentOverrides": {
      "scout": { "model": "kilo/kilo-internal/galaxy" },
      "worker": { "model": "kilo/kilo-internal/galaxy" },
      "reviewer": { "model": "kilo/kilo-internal/galaxy" },
      "oracle": { "model": "kilo/kilo-internal/galaxy" },
      "delegate": { "model": "kilo/kilo-internal/galaxy" }
    },
    "modelScope": {
      "enforce": true,
      "allow": [
        "kilo/kilo-internal/galaxy",
        "kilo/moonshotai/kimi-k3",
        "kilo/openai/*",
        "kilo/anthropic/*",
        "openai-codex/*"
      ]
    }
  }
}
```

Do not set `disableBuiltins`. Do not add `inheritSkills: true` on builtins unless a real task fails without it.

After install, optional `~/.pi/agent/extensions/subagent/config.json`:

- `artifactDir: "session"`
- `toolDescriptionMode: "full"`
- leave FleetView and async defaults

`~/.pi/agent/subagents.json` is tintinweb-only. Do not migrate it key-for-key.

| Old key | Action |
|---|---|
| `disableDefaultAgents` | Drop. Builtins stay on. |
| `fallbackSubagent` | Drop. Unknown names already fail. |
| `maxSubagentDepth` | Drop. Builtin children cannot nest. |
| `maxConcurrent` | Drop unless queueing becomes a problem. |
| `scopeModels` | Replace with `subagents.modelScope` above. |
| `toolDescriptionMode` | Optional nicobailon `config.json`. |
| `widgetMode` / `defaultJoinMode` / `graceTurns` | Drop. Use package defaults. |

## Phase 1 — cut the package

Review `pi-subagents@0.47.1` before install. Pi packages run with full permissions.

```bash
pi remove npm:@tintinweb/pi-subagents
pi install npm:pi-subagents@0.47.1
```

Then:

1. Confirm `settings.json` `packages` is only `npm:pi-subagents@0.47.1`.
2. Confirm `~/.pi/agent/npm` no longer has `@tintinweb/pi-subagents`.
3. Merge the `subagents` settings from 0d.
4. Delete `~/.pi/agent/subagents.json`.
5. Delete `~/.pi/agent/agents/explore.md` and `general.md`.
6. Delete `~/.pi/agent/extensions/agent-orchestration-guard.ts` and its tests.
7. Keep `frontend-path-guard.ts`.
8. Restart Pi.

Do not leave both packages installed.

## Phase 2 — prove the new runtime

In a disposable repo:

1. `/subagents-doctor`
2. `subagent({ action: "list" })` shows scout, researcher, worker, reviewer, oracle, delegate, frontend. No explore/general. No `Agent` tool.
3. `/subagents-models` shows the Kilo pins, not inherit-fallback.
4. Scout a small tree. It may write `context.md`.
5. Researcher on a public URL uses `firecrawl`, not missing `web_search`.
6. Worker does a bounded edit. Code inspects the real diff.
7. Frontend edits `.tsx` and is blocked on `.swift` / `.kt`.
8. Reviewer is read-only.
9. An unknown agent name fails.
10. Two background children: status/steer work.
11. Root still answers a trivial question without delegating.

## Phase 3 — this repository

Start only after Phase 2 passes.

1. `pi-ui-customization`: drop `@tintinweb/pi-subagents` viewer, `Symbol.for("pi-subagents:manager")`, and `subagent_type`. Keep collapse/click-to-expand. Missing viewer stays a no-op.
2. `skills/improve-codebase-architecture`: call `scout` through `subagent`, not `Agent` / `Explore`.
3. Update the UI README and `docs/proposal-persistent-agent-history.md`.
4. Record the repo changes under `CHANGELOG.md` Unreleased.

No `setup.sh` change.

## Phase 4 — cleanup

- Confirm `pi list` has no tintinweb package.
- Confirm a new session’s tools are `subagent`, `subagent_wait`, and `subagent_supervisor`.
- Keep `APPEND_SYSTEM.md` short. Let the packaged skill teach invocation.

## Success

- Code speaks scout / worker / reviewer / oracle / frontend.
- Web research goes through Firecrawl.
- Builtin agents run as shipped, except ejected researcher and model pins.
- Frontend is the only extra specialist.
- No tintinweb tools, viewer, or package.
- Code still owns integration and the user-facing answer.

## First implementation slice

Phase 0 files (prompt, researcher, frontend, settings draft), then Phase 1 in the same sitting so a mixed tintinweb/nicobailon session never boots.
