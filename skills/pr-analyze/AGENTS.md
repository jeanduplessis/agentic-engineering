# AGENTS.md — pr-analyze skill maintenance

## Purpose

Maintain `SKILL.md` as a read-only GitHub pull request analysis workflow. It finds verified logic bugs, missed edge cases, unresolved review-thread disagreements, PR-body discrepancies, tracking gaps, and weak tests on changed lines, then posts a GitHub review only after explicit user approval.

## How the skill works

The skill parses a PR URL or number plus optional focus, gathers PR metadata, unresolved threads, the final combined diff, and surrounding code with `gh`, reports findings in a fixed severity format, then asks before submitting a review and asks again for the review type.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/pr-analyze`, `/skill:pr-analyze`, or `$pr-analyze`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the missing-target stop condition: invoked without a PR, the skill asks for the PR URL or number and does not produce a findings report. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:pr-analyze` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/pr-analyze
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Preserve the read-only contract: no edits, checkouts, tests, or git mutations; posting the approved review is the only mutation.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
