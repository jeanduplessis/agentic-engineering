---
description: "Review current code changes and fix actionable findings"
argument-hint: "[scope or instructions]"
---

Review current changes or requested subset; fix actionable issues.

Arguments: $ARGUMENTS

## Argument handling

- No arguments: review the full current repository change set.
- File/directory paths: review only matching changed files.
- Other text: treat as review intent; resolve the most relevant changed files.
- No changed-file match: say so and stop.

## 1. Resolve scope

Load `code-review-workflow` and `references/scope.md`.

Follow scope discovery:
1. Inspect repository state with read-only git commands.
2. Resolve the base branch dynamically.
3. Build the candidate review scope.
4. Apply the argument scope override, if any.
5. Emit the exact `Resolved Review Scope` block.

If there are no changes to review, say so and stop.

## 2. Review focus areas

Run six independent, read-only focus reviews against the same `Resolved Review Scope`:

1. Security: injection, XSS, auth bypass, secrets, unsafe deserialization.
2. Logic & Error Handling: conditions, fallbacks, error paths, broken edge cases.
3. Type Safety & API Contracts: casts, signatures, validation, caller/callee compatibility.
4. Data & Schema Safety: migrations, defaults, backfills, data loss.
5. Resource Management & Typos: leaks, cleanup, lifecycle, runtime-breaking typos.
6. Style & Clarity: complexity, naming, consistency, project standards.

For each focus review, load `code-review-workflow` and read:
- `references/reviewer-core.md`
- `references/output.md`
- matching focus reference: `security.md`, `logic.md`, `types.md`, `data.md`, `resources.md`, or `style.md`

Use the supplied `Resolved Review Scope`; do not re-run scope discovery.
Reviewer-core read-only/no-edit constraints:
- apply only to focus reviews;
- do not prevent Step 4 fixes.

### Execution compatibility

No native sub-agent support required.

If visible sub-agents exist:
- You may delegate one focus review per sub-agent.

Pi default:
- Use tmux-backed parallel self-invocation.
- Create a temporary directory outside the repo.
- Write one prompt and output file per focus.
- Start one tmux window/pane per focus.
- Run all six Pi review passes concurrently.
- For each pass, run print mode with read-only review tools:
  `pi --tools read,bash,grep,find,ls -p "Run this code-review focus pass from stdin" < "$prompt_file" > "$output_file"`
- Do not provide `edit` or `write`.
- Use only read-only git/bash inspection commands.

Fallback:
- If tmux or Pi self-invocation is unavailable, run six focus reviews sequentially in the current session.

For delegated or self-invoked reviews, pass only:
1. `Resolved Review Scope` block.
2. Focus name and matching focus reference to load.
3. Brief original-argument intent, if needed.

Do not pass full diffs, full skill text, or unresolved natural-language overrides. The resolved scope block is the contract.

## 3. Merge findings

Collect all focus-review findings into one list.

Deduplicate findings with the same file, changed line range, and root cause; keep the highest severity and all reporting focus areas.
Keep different root causes on the same line separate.

Sort by severity (`CRITICAL`, `WARNING`, `SUGGESTION`), then file path.

## 4. Fix

After the read-only review phase, fix actionable findings:

- Fix every `CRITICAL` and `WARNING` finding.
- For Style & Clarity `SUGGESTION` findings, fix only changes that clearly improve readability, maintainability, or comprehension.
- Skip other `SUGGESTION` findings unless trivial and safe.

For each fix:
1. Re-check Evidence, Trace, and Impact.
2. Implement the smallest safe change.
3. Note what changed and why.

## 5. Summarize

Report:
- issue counts by severity and focus area;
- fixes applied;
- skipped findings with brief reasons.
