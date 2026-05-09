# React Code Quality Review Criteria

You review changed React code quality. This is a default `/review` focus and direct `@review-react` focus.

This focus is tool-first: run `react-doctor`, then manually inspect React-specific gaps the tool may miss.

## Applicability

React Code Quality always runs as a focus, but may report `NOT APPLICABLE` only when both the repo and resolved scope lack React signals.

Treat the repo/scope as React-applicable if any signal exists:

- `package.json` dependencies, devDependencies, peerDependencies, or optionalDependencies include `react`, `react-dom`, `next`, `gatsby`, `@remix-run/*`, or related React framework packages.
- The resolved scope contains `.jsx`, `.tsx`, or `.mdx` files.
- Changed `.js` or `.ts` files import React, use JSX, define React components/hooks, or touch React framework routes/config.
- Config files imply React, including `next.config.*`, Gatsby config, Remix config, or Vite config using `@vitejs/plugin-react`.

If no signal exists, output:

```md
## Review Summary (React Code Quality)

### Analyzer Status

- `npx -y react-doctor@latest . --verbose --diff`: NOT APPLICABLE
- Notes: No React project or changed React files detected.

No issues found.
```

## Required analyzer

When React is applicable, run this command from the repo root exactly once:

```bash
npx -y react-doctor@latest . --verbose --diff
```

Do not run package scripts, builds, tests, servers, or application code. Do not edit files during the focus review.

### Analyzer failure

If the command cannot run, exits unexpectedly, or produces unusable output in a React-applicable repo:

- Mark Analyzer Status as `FAIL`.
- Include command, exit status, and relevant stdout/stderr in Evidence.
- Do not say "No issues found."
- Treat React Code Quality as blocking even if manual inspection finds no issues.
- If the failure is caused by a changed project/config line, report a `CRITICAL` finding on that changed line.

### Analyzer findings

Use `react-doctor` output as mandatory evidence.

Severity mapping:

- `react-doctor` errors on changed files: `CRITICAL`.
- `react-doctor` warnings on changed files: `WARNING`.
- Informational/suggestion diagnostics on changed files: `SUGGESTION`.
- Score regression: `WARNING`; use `CRITICAL` only if `react-doctor` marks the regression as blocking/failing. If the regression is not tied to a specific changed line, record it in Analyzer Status and mark the React gate as failed instead of inventing a code finding.

Report diagnostics only when they affect files in the resolved review scope. If `react-doctor` reports unrelated legacy files outside scope, mention them in Analyzer Status notes but do not create findings.

For each analyzer-backed finding, include:

1. The relevant changed diff lines.
2. The exact `react-doctor` rule/message, file, line, and severity when available.
3. The practical React quality impact.

## Manual React gap review

After running `react-doctor`, inspect changed React-applicable files for issues the analyzer may miss. Report only concrete issues on changed lines.

Evaluate:

1. **Hooks and effects** — missing/incorrect dependencies, stale closures, effect cleanup, conditional hook calls, hook misuse.
2. **State ownership** — duplicated state, derived state drift, controlled/uncontrolled input flips, optimistic state without rollback.
3. **Component boundaries** — oversized components introduced by the diff, leaky props, unclear ownership, unstable public component APIs.
4. **Render behavior** — avoidable render churn, unstable object/function props in hot paths, expensive work during render, missing memoization only when the impact is visible.
5. **Accessibility in React markup** — missing labels, keyboard traps, incorrect ARIA, non-semantic interactive elements.
6. **Async UI paths** — missing loading, empty, error, cancellation, or race handling in React data flows.
7. **Client/server boundaries** — hydration hazards, browser APIs in server components, missing client directives, environment-dependent rendering.
8. **Forms/events** — default-submit mistakes, unhandled validation state, event propagation bugs, unsafe disabled/loading transitions.

## What not to flag

- Generic style preferences already covered by Style & Clarity.
- Security issues already better reported by Security, unless the React-specific manifestation is necessary to explain the issue.
- Existing React debt outside the resolved scope unless a changed line worsens or depends on it.
- Memoization suggestions without concrete render/performance impact.
- Tool diagnostics for unchanged/out-of-scope files as findings.

## Output requirements

Use `references/output.md`.

The summary heading must be:

```md
## Review Summary (React Code Quality)
```

Include `### Analyzer Status` in every React Code Quality report.

List all React-applicable files reviewed. If not applicable, list the inspected project/scope signals in Notes instead.
