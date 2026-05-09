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
3. Launch the seven reviewer sub-agents in parallel, passing each the same scope block.
4. Each sub-agent loads this skill, `references/reviewer-core.md`, `references/output.md`, and one focus reference.
5. Sub-agents skip `references/scope.md` because the caller already resolved scope.

### Path B: direct `@review-*` sub-agent

1. Without a supplied `Resolved Review Scope` block, read `references/scope.md` and resolve scope.
2. Then load `references/reviewer-core.md`, `references/output.md`, and the matching focus reference.
3. Review only the assigned focus area.

### Path C: custom caller

Select references by role. Use `references/scope.md` only when scope is not already resolved.
