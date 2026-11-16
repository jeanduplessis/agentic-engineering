# AGENTS.md — spec-audit skill maintenance

## Purpose

Maintain `SKILL.md` as an audit of behavioral feature specs in `.specs/` for anything that could make a coding agent misread intent, followed by author questions and an approved scope of spec fixes.

## How the skill works

The skill selects a spec from a path, a description, or a list of `.specs`; audits 12 fixed categories; reports each finding in a fixed format with severity; adds summary statistics, suggested definitions, and author questions grounded in related code; then asks which scope of fixes to apply.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/spec-audit`, `/skill:spec-audit`, or `$spec-audit`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` copies `evals/fixtures/project`, which contains a deliberately vague `.specs/order-refunds.md`, and checks for the finding fields (`**Severity:**`, `**How an agent could misread it:**`, `**Suggested fix:**`), summary statistics, and author questions. It has no custom grader.

Eval prompts start with `/skill:spec-audit` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/spec-audit
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep `evals/fixtures/project` small and seeded with defects across several audit categories.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
