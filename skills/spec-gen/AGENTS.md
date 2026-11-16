# AGENTS.md — spec-gen skill maintenance

## Purpose

Maintain `SKILL.md` as the workflow for generating a retroactive behavioral feature spec in `.specs/<spec-name>.md` from the current feature branch's changes against `main`.

## How the skill works

The skill identifies the branch, stops on `main`/`master` or missing git context, reads the full diff, commit log, and changed files, extracts testable RFC 2119 rules from the system's perspective, writes the spec template, verifies every rule against the code, and reports the path and counts.

`SKILL.md` sets `disable-model-invocation: true`, so the skill runs only when the user invokes it explicitly (`/spec-gen`, `/skill:spec-gen`, or `$spec-gen`, depending on the harness). It treats the text the user gave after the skill name as its input; keep that wording harness-neutral and do not reintroduce template placeholders such as `$ARGUMENTS`.

## Eval and validation

`evals/manifest.json` checks the missing-git-context stop condition: in an empty, non-git sandbox the skill reports the missing repository or branch instead of writing a spec. The manifest uses an empty fixture and has no custom grader.

Eval prompts start with `/skill:spec-gen` because Pi hides model-invocation-disabled skills from discovery and expands that command into the skill body.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/spec-gen
```

Run live evals only with explicit approval.

## Change guidelines

- Keep `SKILL.md` concise, explicit, and executable for LLMs.
- Keep the skill harness-neutral: name no harness-specific tools; describe optional capabilities with a complete fallback.
- Keep `disable-model-invocation: true` and a description that states the explicit-invocation contract.
- Keep the spec template aligned with `spec-reverse-gen` and the audit categories in `spec-audit`.
- Update `evals/manifest.json` when the input handling, stop conditions, or output contract changes.
- Prefer deterministic manifest checks; add a skill-local grader only if built-in checks cannot express the contract.
