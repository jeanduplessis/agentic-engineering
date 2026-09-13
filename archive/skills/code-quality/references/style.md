# Style and Maintainability

Applicable to every packet. Review changed code for complexity, duplication, expression density, misleading naming,
unclear ownership, inconsistent established patterns, and project-standard violations.

Prefer the smallest clear change that preserves correctness, security, accessibility, and error handling. Do not
recommend new abstractions, configuration, dependencies, scaffolding, or broad refactors unless the changed code
creates a concrete material risk that the recommendation addresses.

Use impact-based severity: maintainability likely to cause defects may be `Major` or `Minor`; optional readability is
`Suggestion`; cosmetic wording/naming/formatting may be `Nit`. Style is the only focus that emits Nits by default.

Do not flag generated churn, TODOs, console logging, or preferences unsupported by surrounding code/project rules.
Do not report correctness/security defects better owned by another focus.
