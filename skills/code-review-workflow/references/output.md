# Output Format

Required output format for all review sub-agents. Every code finding must use this structure.

## For Each Issue

```
**[SEVERITY]** `file/path.ts:42` - Brief description

**Evidence:**

\`\`\`diff
<the relevant changed lines from the diff that triggered this finding>
\`\`\`

**Trace:**
1. <What was observed in the diff>
2. <What surrounding context was checked and where (file, lines)>
3. <The logical conclusion — why this constitutes an issue>

**Impact:** <What breaks at runtime and under what conditions>
```

Every field (Evidence, Trace, Impact) is required. If any field cannot be populated with concrete evidence from inspected code or required analyzer output, drop the finding.

## Severities

- **CRITICAL** — Blocks merge. Security vulnerability, data loss, crash.
- **WARNING** — Should fix. Logic bug, missing error handling, edge case.
- **SUGGESTION** — Nice to have. Minor improvement, concrete future risk.

## Review Summary

When issues are found:

```
## Review Summary (<Focus Area Name>)

| Severity   | Count |
|------------|-------|
| CRITICAL   | X     |
| WARNING    | X     |
| SUGGESTION | X     |

### Files Reviewed
- `src/file.ts`
- `src/other.ts`
```

When no issues are found:

```
## Review Summary (<Focus Area Name>)

No issues found.

### Files Reviewed
- `src/file.ts`
- `src/other.ts`
```

Replace `<Focus Area Name>` with the specific agent's focus (e.g., "Security", "Logic & Error Handling", "Type Safety & API Contract", "Data & Schema Safety", "Resource Management & Typos", "Style & Clarity", "React Code Quality").

## Analyzer Status

Analyzer-backed focus areas may add a short status section before findings:

```md
### Analyzer Status

- `<command>`: PASS|FAIL|NOT APPLICABLE
- Notes: <score, regression status, failure reason, or applicability reason>
```

For React Code Quality, `react-doctor` failure in a React-applicable repo is blocking: report `FAIL`, do not say "No issues found," and include the failed command and stderr/stdout evidence.
