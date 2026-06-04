---
description: "Review current code changes and fix actionable findings after confirmation"
argument-hint: "[scope or instructions]"
skills:
  - code-review-workflow
---

## Required skills

- `code-review-workflow`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Treat the loaded `code-review-workflow` skill directory as the skill root. Resolve every review reference below from its `references/` directory, never relative to the repository or command file; for example, `security.md` means `<loaded-skill-root>/references/security.md`.

Review current changes or requested subset; fix actionable issues.

Arguments: $ARGUMENTS

## Argument handling

- No arguments: review the full current repository change set.
- File/directory paths: review only matching changed files.
- Other text: treat as review intent; resolve the most relevant changed files.
- No changed-file match: say so and stop.

## 1. Resolve scope

Read `references/scope.md`.

Follow scope discovery:
1. Inspect repository state with read-only git commands.
2. Resolve the base branch dynamically.
3. Build the candidate review scope.
4. Apply the argument scope override, if any.
5. Emit the exact `Resolved Review Scope` block.

If there are no changes to review, say so and stop.

## 2. Review focus areas

Run seven independent focus reviews against the same `Resolved Review Scope`:

1. Security: injection, XSS, auth bypass, secrets, unsafe deserialization.
2. Logic & Error Handling: conditions, fallbacks, error paths, broken edge cases.
3. Type Safety & API Contracts: casts, signatures, validation, caller/callee compatibility.
4. Data & Schema Safety: migrations, defaults, backfills, data loss.
5. Resource Management & Typos: leaks, cleanup, lifecycle, runtime-breaking typos.
6. Style & Clarity: complexity, naming, consistency, project standards.
7. React Code Quality: `react-doctor` diagnostics plus React-specific manual review.

For each focus review, read:
- `references/reviewer-core.md`
- `references/output.md`
- matching focus reference: `security.md`, `logic.md`, `types.md`, `data.md`, `resources.md`, `style.md`, or `react.md`

Use the supplied `Resolved Review Scope`; do not re-run scope discovery.
Reviewer-core constraints:
- apply only to focus reviews;
- do not prevent Step 4 fixes;
- allow the React Code Quality focus to run the required `react-doctor` static analyzer.

### Execution compatibility

Use the best available harness-neutral execution path:

1. If the current harness provides native sub-agents, delegate one focus review per sub-agent and run them concurrently when supported.
2. Otherwise, run all seven focus reviews sequentially in the current session.

Optional Pi/tmux acceleration:
- When running under Pi and both Pi self-invocation and tmux are available, you may use tmux-backed parallel self-invocation instead of the harness-neutral paths.
- Create a temporary directory outside the repo; write one prompt and output file per focus; start one tmux window/pane per focus.
- Run each pass in print mode without edit/write tools:
  `pi --tools read,bash,grep,find,ls -p "Run this code-review focus pass from stdin" < "$prompt_file" > "$output_file"`
- Use only read-only git/bash inspection commands, except React Code Quality must run the latest `react-doctor` package with `npx -y`, passing `. --verbose --diff`, when React is applicable.
- If this acceleration path fails or is unavailable, use native sub-agents or sequential execution; do not block the review.

For delegated or self-invoked reviews, pass only:
1. `Resolved Review Scope` block.
2. Focus name and matching focus reference to load.
3. Brief original-argument intent, if needed.

React Code Quality is a default focus. It may report not applicable only when the repo and resolved scope have no React signals.

Do not pass full diffs, full reference text, or unresolved natural-language overrides. The resolved scope block is the contract.

## 3. Merge findings

Collect all focus-review findings into one list. Preserve analyzer status sections, especially React Code Quality PASS/FAIL/NOT APPLICABLE.

Deduplicate findings with the same file, changed line range, and root cause; keep the highest severity and all reporting focus areas.
Keep different root causes on the same line separate.

Sort by severity (`CRITICAL`, `WARNING`, `SUGGESTION`), then file path.

## 4. Confirm before fixes

Pause before any fix edits or write-capable commands.

Present:
- merged findings by severity and focus area;
- React Code Quality analyzer status;
- proposed fixes;
- skipped findings with brief reasons.

Ask the user: `Proceed with these fixes?`

Stop and wait for explicit user confirmation. If the user declines or changes scope, do not fix; follow the user's updated direction. Proceed to Step 5 only after confirmation.

## 5. Fix

After the no-edit focus-review phase and explicit user confirmation, fix actionable findings:

- Fix every `CRITICAL` and `WARNING` finding.
- If React Code Quality reports Analyzer Status `FAIL`, treat the review as blocked until the analyzer passes or React is proven not applicable.
- For Style & Clarity `SUGGESTION` findings, fix only changes that clearly improve readability, maintainability, or comprehension.
- Skip other `SUGGESTION` findings unless trivial and safe.

For each fix:
1. Re-check Evidence, Trace, and Impact.
2. Implement the smallest safe change.
3. Note what changed and why.

## 6. Summarize

Report:
- issue counts by severity and focus area;
- React Code Quality analyzer status;
- fixes applied;
- skipped findings with brief reasons.
