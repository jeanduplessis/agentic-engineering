# AGENTS.md — custom-command skill maintenance

## Purpose

Maintain `SKILL.md` as the portability guide for creating, porting, auditing, and editing Markdown slash commands/prompt templates for both OpenCode and Pi. Preserve behavior-identical shared commands; explicitly flag agent-specific features that would change core results.

## How the skill works

`SKILL.md` defines the shared Markdown command shape, portable argument rules, frontmatter guidance, non-portable expansion warnings, naming rules, output template, checklist, and examples. Keep the default path on the shared subset: `description` frontmatter, Markdown body text, `$ARGUMENTS`, flat kebab-case `.md` filenames, and install paths for both agents.

## Eval and validation

`evals/manifest.json` declares workflow, trigger, and capability suites. Workflow cases come from `evals/evals.json`; `evals/grader.py` grades them by checking portable filenames, frontmatter, `$ARGUMENTS`, absence of behavior-changing OpenCode frontmatter, absence of required shell/file expansion, and install-path guidance.

Run the full local validity wrapper from the repo root only with live Pi/model execution approval:

```sh
./tools/skill_valid/skill_validate.sh skills/custom-command
```

## Change guidelines

- Preserve cross-agent portability as core contract; do not require OpenCode-only or Pi-only features for correct behavior in shared commands.
- Update `evals/evals.json` and `evals/grader.py` when changing expected command output, portability rules, or compatibility checklist in `SKILL.md`.
- Keep `evals/manifest.json` aligned with the skill name and eval assets when adding or removing suites.
- Keep examples behavior-identical across OpenCode and Pi unless clearly labeled as non-portable or graceful-degradation conveniences.
- Prefer concise direct instructions to broad compatibility commentary agents cannot execute.
