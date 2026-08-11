# Data and Schema Safety

Applicable when migrations, persistence schemas, defaults, backfills, queues, sync metadata, or persisted meaning
changes; otherwise return `NOT_APPLICABLE`.

Review destructive/narrowing changes, defaults, nullability, backfills, rollback/recovery, historical meaning, and
mixed-version rollout compatibility. Verify existing rows before new writes and old/new readers and writers during
deployment.

For freshness/sync data, distinguish full success, partial failure, skipped/deleted items, owner/repository scope,
zero findings, never scanned, and results deleted. For queue/concurrency data, verify terminalization, in-flight
callbacks, supersede/cancel, lease capacity, and app/worker parity.
