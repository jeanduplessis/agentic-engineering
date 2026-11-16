# AGENTS.md — wat skill maintenance

## Purpose

Maintain `SKILL.md` as a one-shot simplifier that rephrases the previous assistant response into a plain-language takeaway with at most three bullets, without continuing the underlying task.

## How the skill works

The skill uses the optional focus only for emphasis, asks the user to paste text when no previous assistant response exists, preserves caveats and decisions, and outputs only the simplification without further tool use.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/wat`, `/skill:wat`, or `$wat`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the no-previous-response path: invoked as the first message, the skill asks the user to paste the text to simplify. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:wat` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/wat
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep the output short: one-sentence takeaway plus at most three bullets.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
