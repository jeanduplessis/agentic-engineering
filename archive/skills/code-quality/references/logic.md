# Logic and Error Handling

Applicable to every packet. Review correctness, state, concurrency, and failure paths:

- wrong conditions, comparisons, bounds, null handling, unreachable paths, and unsafe defaults;
- exceptions, rejected promises, retries, idempotency, partial failures, duplicate delivery, and stale data;
- status transitions, queues, claims, leases, callbacks, cleanup, finalization, and timestamp semantics;
- fallback operators (`??`, `||`, defaults, `COALESCE`): enumerate null, undefined, empty, zero, and false states and
  verify semantic—not mechanical—correctness;
- stateful changes: verify entry, exit, skip/no-op, partial failure, retry, cancellation/supersede, races, and zero-row
  behavior.

Do not report type/style-only issues. Continue through adjacent invariants after finding one defect.
