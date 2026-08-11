# Type Safety and API Contracts

Applicable when code, schemas, serialized formats, public APIs, or configuration contracts change; otherwise return
`NOT_APPLICABLE`.

Review:

- unsafe `any`, casts, non-null assertions, incomplete unions, narrowing, and static/runtime mismatches;
- missing runtime validation for external or persisted values;
- caller/callee signatures, required fields, exports/importers, enums/statuses, dates/numbers, and wire/storage forms;
- backward compatibility and producer/consumer parity;
- mirrored implementations or runtime paths that must preserve equivalent contracts.

Anchor omissions to the changed declaration or producer that created the update obligation.
