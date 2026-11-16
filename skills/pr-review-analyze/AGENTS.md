# AGENTS.md — pr-review-analyze skill maintenance

## Purpose

Maintain `SKILL.md` as the workflow for addressing unresolved review comments from user-selected automated reviewers on a GitHub pull request: fix, reply, resolve, self-review, commit, and push.

## How the skill works

The skill requires the `gh-pr-review` skill and stops if it is unavailable. It resolves the PR (or the current branch's PR), reads recent git history, confirms the automated reviewer logins, reads full selected-reviewer history, then acts only on unresolved, non-outdated comments from those logins.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/pr-review-analyze`, `/skill:pr-review-analyze`, or `$pr-review-analyze`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the required-skill guard: in the isolated eval run `gh-pr-review` is not loaded, so the skill must name it as unavailable and stop. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:pr-review-analyze` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/pr-review-analyze
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Never widen the action scope to human comments or unconfirmed reviewers.
- Keep the `gh-pr-review` dependency explicit; update this file and the manifest if the dependency changes.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
