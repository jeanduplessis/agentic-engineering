# Test Quality

Applicable when production behavior, public contracts, migrations, bug fixes, or tests change; otherwise return
`NOT_APPLICABLE`.

Review whether existing tests and available evidence already prove observable behavior and high-risk boundaries
without overfitting implementation details. Inspect relevant existing tests before recommending new coverage.

Prefer the highest practical verification level that proves the changed flow. Test project-owned behavior and
integration boundaries, not framework, library, browser, or language-runtime guarantees. Avoid implementation-detail
assertions, brittle UI selectors or timing assumptions, broad snapshots, and duplicated coverage across test layers
unless each test addresses a distinct material risk.

Check changed behavior for normal, failure, boundary, concurrency, compatibility, and regression coverage as
appropriate. Flag brittle assertions, tests that cannot fail for the intended defect, duplicated low-value cases,
missing negative paths, and fixtures that contradict runtime schemas.

Missing tests are findings only when material behavior remains unverified after considering existing coverage.
Trivial or already-covered changes need no new tests. Anchor omissions to the changed production line that creates
the obligation, or to a changed test line that weakens or invalidates coverage. Severity follows risk: high-risk
missing coverage may be `Major`; optional extra coverage is `Suggestion`.
