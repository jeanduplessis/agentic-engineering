# Quality Result

Each agent should return one JSON object conforming to `quality-result.schema.json`; no Markdown or code fence.

Use this exact top-level shape and copy enum values exactly; do not invent synonymous labels:

```json
{"schema_version":1,"review_id":"<packet review_id>","focus":"<assigned focus>","status":"PASS","summary":"<summary>","files_reviewed":[],"coverage_notes":[],"findings":[]}
```

- Status: `FINDINGS`, `PASS`, `NOT_APPLICABLE`, or `BLOCKED`.
- Severity: `Blocker`, `Major`, `Minor`, `Suggestion`, or `Nit` (Style only by default).
- Category: `Correctness`, `Data integrity`, `Security`, `Reliability`, `Performance`, `Maintainability`, `Testing`,
  or `Style`.
- React always includes `analyzer` with `command`, `status`, and `notes`; analyzer status is `PASS`, `FAIL`, or
  `NOT_APPLICABLE`.
- Include no keys not declared by the schema. All canonical result strings are non-empty except analyzer `notes` and
  optional location `note`. An ingestion gate may generate `summary` when status/findings already determine a neutral
  summary; persisted results always include it.

Statuses:

- `FINDINGS`: one or more verified findings.
- `PASS`: applicable, fully reviewed, no findings.
- `NOT_APPLICABLE`: focus applicability condition failed; include reason.
- `BLOCKED`: required packet evidence, source context, analyzer output, or contract validation was unavailable.

Every finding has one changed-cause `anchor`. Use `supporting_locations` for unchanged callers, absent tests,
missing migrations, or other evidence. `evidence`, `trace`, `impact`, and `fix_direction` must be concrete.

Use `coverage_notes` to record relevant existing tests inspected, behavior not covered, analyzer command/status and
limitations, and why any missing coverage is or is not material.

Agents remain read-only and return JSON in their task response. Orchestrators preserve the raw response, canonicalize
safe transport-only deviations (wrappers, enum casing, packet-derived or empty defaults, `FINDINGS` implied by a
non-empty findings array, neutral generated summaries, and a not-run analyzer for non-applicable React), then strictly validate the result. They persist it as
`result-<focus>.json`, retry responses that remain invalid once, then record `BLOCKED` only if useful review content
still cannot be validated.
