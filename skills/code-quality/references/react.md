# React Code Quality

Applicable when package/config signals React or changed files contain React, JSX/TSX/MDX, hooks, components, or
React-framework routes; otherwise return `NOT_APPLICABLE`.

When applicable, run exactly once from `source_root`:

```bash
npx -y react-doctor@latest . --verbose --diff
```

This is the only focus-authorized external fetch. Do not install project dependencies or alter project files. Record
the analyzer command, resolved version when reported, status, and notes. Analyzer failure returns `BLOCKED`; do not
claim PASS. Map diagnostics by actual impact using shared severity, not analyzer labels alone, and report only
changed-scope issues.

Manually review hooks/effects, stale closures, cleanup, state ownership, controlled inputs, optimistic rollback,
component boundaries, render churn, accessibility, async UI states/races, hydration/client-server boundaries, forms,
and duplicate submissions. Avoid memoization advice without concrete impact.
