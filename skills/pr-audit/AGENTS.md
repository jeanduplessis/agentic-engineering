# AGENTS.md — pr-audit skill maintenance

## Purpose

Maintain `SKILL.md` as a high-level GitHub pull request audit of process quality, change hygiene, scope, blast radius, and architectural fit. It deliberately does not validate code correctness.

## How the skill works

The skill fetches lightweight PR metadata with `gh`, discovers the diff incrementally by file class, scores 12 fixed criteria as PASS, CONCERN, or BLOCK, and emits an exact report structure whose overall verdict is the highest criterion severity.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/pr-audit`, `/skill:pr-audit`, or `$pr-audit`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the missing-URL stop condition: invoked without a PR URL, the skill asks for one and does not emit the `## Verdict:` report. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:pr-audit` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/pr-audit
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep the 12 criteria, the PASS/CONCERN/BLOCK scale, and the report structure in sync with the manifest checks.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
