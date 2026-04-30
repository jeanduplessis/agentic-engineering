# AGENTS.md — pr-create skill maintenance

## Purpose

Maintain `SKILL.md` as the runtime contract for creating or updating GitHub pull requests with reviewer-focused titles and descriptions. Preserve the skill's bias toward accurate PR text, explicit confirmation, and safe GitHub mutations.

## How the skill works

`SKILL.md` tells the assistant to inspect branch and PR state, optionally rebase when requested, choose create vs. update flow, generate or revise the PR title/body, ask for confirmation, then push and create or edit the PR. Existing PR descriptions should stay unchanged unless current commits make them stale, incomplete, or misleading.

## Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case force-loads `SKILL.md` and asks for a no-command PR preview from supplied branch context; deterministic checks verify the required Summary, Human Verification, Reviewer Notes, and confirmation behavior.

Run the full validation wrapper from the repository root:

```sh
./tools/skill_valid/skill_validate.sh skills/pr-create
```

This invokes `tools.skill_valid` and may run live Pi/model gates when deterministic prerequisites pass.

## Change guidelines

- Keep `SKILL.md` focused on PR creation/update behavior, not general GitHub or release management.
- Preserve the confirmation step before any GitHub write (`git push`, `gh pr create`, or `gh pr edit`).
- Keep update-flow edits conservative: do not rewrite accurate existing PR descriptions for style only.
- Update `evals/manifest.json` when the public output contract or confirmation behavior changes.
- Prefer deterministic eval checks for stable headings and safety behavior; avoid checks that require exact prose.
