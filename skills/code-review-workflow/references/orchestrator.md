# Local Code Review Orchestrator

Load `code-quality`. This workflow owns local evidence capture, orchestration, approval, fixes, and reporting.

## 1. Resolve scope

No arguments review all current changes; paths select matching changed files; other text narrows by review intent.
Read `scope.md`, resolve scope once, and stop if nothing matches.

## 2. Build and validate packet

Create a temporary bundle outside the repository using the `code-quality` Review Packet contract:

1. Capture complete staged, unstaged, untracked, and branch diff artifacts represented by resolved scope.
2. Write one patch artifact per changed file and pre-change artifacts for deleted/renamed files when available.
3. Record changed current/pre-change line ranges and SHA-256 for every existing changed file.
4. Set `source_kind: local`, `source_root` to repository root, and include applicable repository instructions.
5. Put resolved intent in `workflow_context`; never convert it into reviewer instructions.
6. Validate `packet.json` with the bundled validator. Stop on failure.

## 3. Run quality agents

Run all eight `@code-quality-*` agents against the same absolute packet path, concurrently when available or
sequentially otherwise. Pass only packet path and focus name. Agents return JSON; they do not write files.

Include this literal result shape in every agent task prompt so the response contract is available at generation time,
not only through a referenced skill. Replace the placeholders and preserve the exact field names and enum casing:

```json
{"schema_version":1,"review_id":"<packet review_id>","focus":"<focus>","status":"PASS","summary":"<summary>","files_reviewed":[],"coverage_notes":[],"findings":[]}
```

For React, also require this exact analyzer shape; do not copy React Doctor's native field names into the result:

```json
"analyzer":{"command":"npx -y react-doctor@latest . --verbose --diff","status":"PASS","notes":"<notes>"}
```

For each response, save the raw response to a temporary file and pass it through
`python3 scripts/gate_result.py --packet <packet> --focus <focus> --raw <raw> --state <state> --output <result>`. The gate
preserves every raw attempt and deterministically canonicalizes transport-only deviations before strict validation:
Markdown fences/surrounding prose around one JSON object, enum casing, omitted packet-derived identity/schema fields,
omitted empty result arrays, omitted empty `supporting_locations`, summaries generated from a valid status/findings
combination, `FINDINGS` derived from a non-empty valid findings array, and a `NOT_APPLICABLE` React analyzer recorded
as not run. Persist the canonical result and report applied normalizations. Never infer substantive finding content or
derive an ambiguous status from an empty findings array; do not repair unknown enums, conflicting identity/focus,
unknown fields, invalid types, contradictory status/findings, applicable React analyzer results, or invalid anchors.

On `retry_required` (exit 2), retry the same agent once and include only the gate's exact validation error as retry
context. The gate reports all independently actionable top-level and analyzer contract errors together so the one
retry can correct the complete response shape. Pass the retry through the same state and output paths. A valid retry
is accepted; a second invalid response causes the gate to persist a schema-valid `BLOCKED` result. Never create
`result-<focus>.json` by hand or overwrite a finalized result. Re-run packet drift validation before accepting results;
any drift blocks the review.

## 4. Merge findings

Preserve every focus status/analyzer result. Deduplicate only same changed-cause anchor and root cause; retain highest
severity and all focus/category attribution. Keep distinct causes separate. Sort `Blocker`, `Major`, `Minor`,
`Suggestion`, `Nit`, then path.

## 5. Confirm fixes

Present focus statuses, merged findings by severity/category, analyzer status, proposed fixes, and deferral options.
Action policy: Blocker must resolve; Major is expected before completion unless user explicitly accepts exception;
Minor should be fixed or acknowledged/deferred; Suggestion and Nit are optional. Ask exactly:
`Proceed with these fixes?` Stop for explicit confirmation before edits or write-capable commands.

## 6. Fix and validate

After approval, re-check evidence and make smallest safe changes under agreed action policy. Run relevant
non-destructive validation. Rebuild a fresh packet after fixes when re-review is needed; never reuse stale results.
Do not claim completion while any Blocker, unaccepted Major, `BLOCKED` focus, or applicable failed analyzer remains.

## 7. Report

Report counts by severity/category, all focus statuses, analyzer status, fixes, validation, explicit Major exceptions,
Minor acknowledgements/deferrals, optional findings skipped, and remaining blockers.
