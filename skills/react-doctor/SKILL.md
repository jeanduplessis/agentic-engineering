---
name: react-doctor
description: Use when finishing React feature or bug work, before committing React code, or when improving React code quality or cleaning a React codebase. Checks score regression; covers lint, dead code, accessibility, bundle size, architecture diagnostics.
---

# React Doctor

Scans React codebases for security, performance, correctness, and architecture issues. Outputs a 0–100 health score.

## After React code changes

Run `npx -y react-doctor@latest . --verbose --diff`; confirm the score did not regress. If it dropped, fix regressions before committing.

## General cleanup or code improvement

Run `npx -y react-doctor@latest . --verbose` to scan the full codebase. Fix by severity: errors, then warnings.

## Command

```bash
npx -y react-doctor@latest . --verbose --diff
```

| Flag | Purpose |
| --- | --- |
| `.` | Scan current directory |
| `--verbose` | Show affected files and line numbers per rule |
| `--diff` | Scan changed files vs base branch only |
| `--score` | Output only the numeric score |
