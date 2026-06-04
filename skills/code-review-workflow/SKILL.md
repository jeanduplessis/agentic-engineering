---
name: code-review-workflow
description: Use when reviewing local repository changes or running /review or @review-* workflows. Provides a deterministic review process for staged, unstaged, untracked, deleted, and branch-diff changes across security, logic, types, data, resources, style, and React code quality.
---

# Code Review Workflow

Review local changes. Focus reviews inspect evidence and do not edit code or run application logic.
React Code Quality may run the required `react-doctor` static analyzer.

## Reference loading

- Scope resolution: `references/scope.md` for `/review`, or for direct sub-agents without a resolved scope.
- Reviewer contract: `references/reviewer-core.md` and `references/output.md` for every reviewer sub-agent.
- Focus references:
  - `references/security.md` for `@review-security`.
  - `references/logic.md` for `@review-logic`.
  - `references/types.md` for `@review-types`.
  - `references/data.md` for `@review-data`.
  - `references/resources.md` for `@review-resources`.
  - `references/style.md` for `@review-style`.
  - `references/react.md` for `@review-react`.

## Usage paths

### Path A: `/review` command

1. Load this skill and `references/scope.md`.
2. Resolve scope and emit a `Resolved Review Scope` block.
3. When native sub-agents are available, launch seven reviewer sub-agents concurrently and pass each the same scope block. Otherwise run the seven focus reviews sequentially in the current session as distinct read-only reviewer roles.
4. Each focus execution loads this skill, `references/reviewer-core.md`, `references/output.md`, and one focus reference.
5. Focus executions skip `references/scope.md` because the caller already resolved scope.
6. Harness-specific parallel self-invocation is optional acceleration only; failure or absence must fall back to native sub-agents or sequential current-session review without weakening any focus.

### Path B: direct `@review-*` sub-agent

1. Without a supplied `Resolved Review Scope` block, read `references/scope.md` and resolve scope.
2. Then load `references/reviewer-core.md`, `references/output.md`, and the matching focus reference.
3. Review only the assigned focus area.

### Path C: custom caller

Select references by role. Use `references/scope.md` only when scope is not already resolved.
