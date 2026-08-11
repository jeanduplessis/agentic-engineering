# Severity and Category

Severity communicates impact, likelihood, and required action. Category communicates finding type.

## Severity

- `Blocker`: known correctness, data-integrity, security, or reliability defect reachable in realistic operation.
  Must be fixed before merge.
- `Major`: meaningful plausible risk, substantial performance issue, or maintainability/testing gap likely to cause
  future defects. Expected before merge; exception requires explicit agreement.
- `Minor`: limited-impact or unlikely edge case, bounded inefficiency, or localized maintainability/testing gap.
  Fix or explicitly acknowledge/defer.
- `Suggestion`: optional improvement with no material correctness, reliability, performance, or maintenance effect.
- `Nit`: purely cosmetic wording, naming, formatting, or style preference. Only Style emits Nits by default.

Assess impact, realistic likelihood, then urgency. Do not infer severity from category alone.

## Category

`Correctness`, `Data integrity`, `Security`, `Reliability`, `Performance`, `Maintainability`, `Testing`, `Style`.

Choose one primary category. Focus and category need not match; for example, Logic may report `Performance` and
Tests may report `Reliability` when evidence supports that classification.
