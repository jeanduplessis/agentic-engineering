# Resource Management and Runtime Typos

Applicable when changed code acquires/releases resources, registers lifecycle callbacks/listeners, or changes runtime
identifiers/configuration strings; otherwise return `NOT_APPLICABLE`.

Review memory, descriptors, streams, sockets, cursors, database connections, locks, timers, listeners, subscriptions,
and leases across success, error, cancellation, early return, retry, and teardown paths. Verify ownership across
module boundaries and mirrored acquire/release paths.

Report misspelled variables, properties, enum/status/event names, routes, or config keys only when they can break
execution. Cosmetic spelling belongs to Style as `Nit`.
