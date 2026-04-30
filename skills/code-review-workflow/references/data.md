# Data & Schema Safety Review Criteria

You are responsible for **data and schema safety** issues only.

## What to Evaluate

- **Destructive migrations** — Column drops, type narrowing, or table deletes that lose data irreversibly
- **Incompatible defaults** — New columns or fields with defaults that conflict with existing data semantics
- **Risky backfills** — Backfill operations that can corrupt, overwrite, or misinterpret existing rows
- **Irreversible data loss** — Any operation that permanently removes or alters data without a recovery path

## Cross-File Analysis

Limit cross-file analysis to data and schema interactions:

- A migration that changes a column type but read paths not updated
- A new required field with no backfill for existing rows
- A default value that is incompatible with existing data

## Invariant Expansion Triggers

### Schema And Rollout Trigger

If a migration is added or the meaning of persisted data changes, verify:

- migration backfill behavior
- compatibility for existing rows
- null and default behavior immediately after deploy
- read paths before any new write has occurred
- whether historical data disappears, changes meaning, or becomes overstated

### Domain Checklists

For freshness or sync metadata changes, verify:

- full success versus partial failure behavior
- skipped-item behavior
- stale or deleted-item behavior
- owner-scoped versus repo-scoped semantics; verify that an owner-level value is never used as a proxy for a repo-level value without confirming all repos have been covered
- zero-row or zero-finding behavior; enumerate distinct causes (never scanned, scanned with no results, results deleted) and verify each is handled correctly
- fallback behavior before the first successful sync; verify that "no data yet" is not conflated with "data checked, nothing found"
- migration or backfill behavior for pre-existing data

For queue, callback, or concurrency changes, verify:

- queued versus pending versus running transitions
- claim or start races
- supersede or cancel while in flight
- callback behavior after supersede or cancel
- queue-row terminalization
- release of concurrency or lease capacity
- parity between app-side and worker-side code paths

Do not apply the Fallback Path Enumeration, Stateful Code, or Mirrored Implementation triggers unless directly relevant to a data safety finding you already verified.
