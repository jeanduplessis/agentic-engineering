# Logic & Error Handling Review Criteria

You are responsible for **error handling** and **logic correctness** only.

## What to Evaluate

- **Missing try/catch** — Where required by the calling convention or when the callee can throw

- **Unhandled promise rejections** — Async calls without `.catch()` or `try/catch` in an `async` context

- **Unchecked null/undefined** — Accessing properties on values that may be null or undefined without a guard

- **Wrong conditions** — Boolean logic errors, inverted checks, missing cases in switches or if-else chains

- **Off-by-one** — Array bounds, loop limits, range calculations, string slicing

- **Incorrect comparisons** — `==` vs `===`, type coercion surprises, wrong operand order

- **Unreachable code** — Dead branches after early returns, throws, or unconditional jumps

- **Unsafe fallback/default values** — Fallbacks that are incorrect for some input states (see Fallback Path Enumeration below)

## Cross-File Analysis

Limit cross-file analysis to logic and error-handling interactions:

- A caller not handling an error that a changed function can now throw

- Inconsistent null checks across call sites

- Changed return types not reflected in caller logic

## Invariant Expansion Triggers

### Fallback Path Enumeration

For every `??`, `||`, `COALESCE`, default value, or conditional fallback on a changed line:

1. List every distinct real-world state that can produce the triggering condition (null, undefined, empty, zero, false).

2. For each state, verify the fallback value is **semantically correct for that state** — not just that the operator handles the value mechanically.

3. If a code comment or variable name claims a single reason for the fallback, treat that as a hypothesis.

   Example: "clean repos have no findings".

   Actively search for counterexamples: other real-world states that produce the same triggering value but for
   which the fallback is incorrect.

If any enumerated state makes the fallback unsafe, report it. Do not stop at confirming the operator works correctly.

### Stateful Code Trigger

If the diff touches any of the following, run an explicit state-machine review:

- status fields

- queue rows

- leases or claims

- callbacks or webhooks

- retry logic

- cleanup or finalization logic

- timestamps representing freshness, progress, or completion

For each touched state field, verify:

- how the state is entered

- how the state is exited

- behavior on partial failure

- behavior on skip or no-op paths

- behavior on duplicate or supersede paths

- behavior on in-flight completion races

- behavior when zero matching records exist

- behavior when a callback or retry arrives after state changed elsewhere

Do not apply the Schema And Rollout Trigger or Mirrored Implementation Trigger unless directly relevant to a
logic or error-handling finding you already verified.
