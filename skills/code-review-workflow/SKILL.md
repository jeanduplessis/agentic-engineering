---
name: code-review-workflow
description: Use this skill when running local code review through /code-review-local. Captures staged, unstaged, untracked, deleted, and branch-diff changes into a code-quality Review Packet, orchestrates shared quality agents, gates fixes on confirmation, validates changes, and reports outcomes.
---

# Local Code Review Workflow

Adapt local repository changes into the shared `code-quality` contract, then own local review behavior.

## References

- Orchestration: `references/orchestrator.md`.
- Local scope capture: `references/scope.md`.
- Shared packet, result, criteria, and agent contracts: load `code-quality`.

Load `code-quality`, then follow `references/orchestrator.md`. There is no direct reviewer path; specialized quality
agents require prepared Review Packets.
