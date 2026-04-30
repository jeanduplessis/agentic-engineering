# Type Safety & API Contract Review Criteria

You are responsible for **type safety** and **API contract** issues only.

## What to Evaluate

### Type Safety

- **Implicit any** — Variables, parameters, or return types that default to `any` without explicit annotation
- **Unsafe casts** — `as` casts, `!` non-null assertions, or type assertions that suppress real type errors
- **Missing input validation** — External input (API payloads, query params, form data) used without runtime validation
- **Wrong parameter types** — Function calls passing values of incorrect type that the type system does not catch (e.g., string where number expected via `any` intermediary)

### API Contract

- **Breaking signature changes** — Function, method, or API endpoint signatures changed in ways that break existing callers
- **Missing required fields** — New required fields added to request/response types without updating all producers/consumers
- **Wrong return types** — Return type changed or narrowed without updating all consumers

## Cross-File Analysis

Limit cross-file analysis to type and API interactions:

- A function signature changed but callers not updated
- An export type changed but importers still using the old shape
- A required field added but not all call sites provide it

## Invariant Expansion Triggers

### Mirrored Implementation Trigger

When a changed file has a known counterpart, duplicate implementation, or mirrored runtime path, search for the counterpart and verify equivalent type signatures and API contracts were updated.

If the counterpart was not updated and this creates behavioral drift, report the issue anchored to the changed file that introduced the divergence.

Do not apply the Fallback Path Enumeration, Stateful Code, or Schema And Rollout triggers unless directly relevant to a type safety or API contract finding you already verified.
