# AGENTS.md — spec-reverse-gen skill maintenance

## Purpose

Maintain `SKILL.md` as the workflow for reverse-engineering a behavioral feature spec in `.specs/<spec-name>.md` from existing code for a named domain or feature.

## How the skill works

The skill requires a domain or feature description, searches the codebase by keywords, structure, tests, and imports, reads the prioritized files in full, extracts testable RFC 2119 rules, writes the spec template, verifies every rule against the code, and reports the path and counts.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/spec-reverse-gen`, `/skill:spec-reverse-gen`, or `$spec-reverse-gen`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the missing-input stop condition: invoked without a domain, the skill returns the `Requires a domain or feature description` usage message. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:spec-reverse-gen` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/spec-reverse-gen
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep the spec template aligned with `spec-gen` and the audit categories in `spec-audit`.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
