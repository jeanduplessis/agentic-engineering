# AGENTS.md — gh-pr-review skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for using the `gh pr-review` GitHub CLI extension to inspect PR review feedback, reply to review threads, and resolve or unresolve threads safely.

## How the skill works

`SKILL.md` tells the assistant when to use `gh pr-review` commands instead of generic GitHub review handling. It documents installation, read commands (`view`, `threads`), mutation commands (`reply`, `resolve`, `unresolve`), JSON output expectations, and the default workflow for focusing on actionable unresolved PR feedback.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case force-loads `SKILL.md` and asks for a no-command plan using `gh pr-review` to inspect unresolved feedback, filter by reviewer, reply after a fix, and resolve an addressed thread. Deterministic checks verify the key commands, flags, and `PRRT_` thread-id placeholder.

Run the full validation wrapper from the repository root:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/gh-pr-review
```

This invokes deterministic `tools.skill_valid`; pass `--allow-live` and select a supported harness only with explicit approval.

## Change guidelines

- Keep `SKILL.md` focused on PR review comment workflows, not general GitHub PR creation or repository maintenance.
- Preserve the safe default: inspect unresolved, non-outdated feedback before replying or resolving.
- Resolve threads only after the referenced feedback has been addressed or intentionally declined with an explanatory reply.
- Update `evals/manifest.json` when command names, flags, JSON contracts, or the safe review workflow change.
- Prefer deterministic eval checks for stable command/flag contracts; avoid exact prose checks.
