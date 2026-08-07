---
name: testing-principles
user-invocable: false
description: >
  Agent guidance for writing, modifying, or reviewing automated tests. Use when an agent chooses a test level,
  designs test cases, decides what to assert, or evaluates test quality.
license: Apache-2.0
metadata:
  author: Jean du Plessis
  version: "1.0"
  credit: https://github.com/kentcdodds/kody/blob/main/docs/contributing/testing-principles.md
---

# Testing principles

Use these principles whenever test work is part of a change. Optimize for tests that catch meaningful regressions,
read like executable specifications, and remain cheap to maintain.

## Choose the lightest honest test

Choose the least expensive test that can genuinely falsify the behavior:

- **Unit tests** for pure logic and code that can run without a framework or external runtime.
- **Integration/runtime tests** when the behavior depends on real local bindings, persistence, queries, or runtime APIs.
  Prefer project test-support factories and schema helpers over copied setup.
- **Transport/protocol smoke tests** for a small number of behaviors that specifically require the real HTTP, OAuth,
  or protocol wiring.
- **End-to-end tests** for a very small number of user-critical happy-path journeys.

Do not use a slower or broader test to cover edge cases that a faster test can cover. Keep tests offline and deterministic:
use local fakes, fixtures, and test services instead of the public internet or third-party services.

## Write workflow tests

Treat each test like a manual tester's script:

1. Set up the required state explicitly in the test.
2. Perform the meaningful actions in order.
3. Assert the resulting behavior and important intermediate states.

Prefer fewer, longer tests when assertions belong to the same workflow. Multiple related assertions are valuable; do not
split one journey into many tiny tests merely to enforce one assertion per test. If later assertions depend on the same
rendered object, request, or response, keep them in that workflow.

## Keep intent and isolation obvious

- Name tests after observable behavior, for example: `auth handler returns 400 for invalid JSON`.
- Prefer flat test files and top-level tests over deep `describe` nesting.
- Inline setup instead of hiding it in `beforeEach`/`afterEach` hooks.
- Do not share mutable state across cases.
- Build factories that return ready-to-run objects, not global fixtures.
- Use disposable resources only when they need real cleanup; make cleanup reliable and unable to obscure the assertion.

## Assert behavior, not implementation

Test through public interfaces and stable contracts. Tests should survive internal refactors.

- Assert user-visible outcomes, structured results, persisted effects, or other stable contracts.
- Avoid private methods, internal call sequences, incidental object shape, and implementation-only collaborators.
- Do not test guarantees already provided by the type system.
- Avoid pinning descriptive prose, configuration strings, warnings, or instructional copy unless that exact text is itself
  the public contract. Prefer testing the behavior or structured contract it describes.
- Add a regression test when the bug is likely to recur or the affected flow is important enough to justify its maintenance cost.

Use mocks, spies, and stubs only where they honestly exercise the intended behavior. A mock is appropriate for an external
boundary or an unavoidable expensive dependency, but replacing the code path under test with mocks is not coverage. When
logging is part of the contract, assert stable tags, event data, or error types rather than long prose; when it is incidental,
silence only explicitly expected messages so unexpected failures remain visible.

## Test-quality checklist

Before finalizing a test, ask:

- Can this test fail when the intended behavior breaks?
- Does it use the lightest test flavor that can honestly exercise that behavior?
- Does it describe behavior through a public interface?
- Is setup explicit, isolated, and local to the test?
- Are related actions, intermediate states, and outcomes kept in one workflow?
- Is the assertion tied to a stable contract rather than incidental implementation or copy?
- Is the test deterministic, offline-capable, and worth its maintenance cost?
