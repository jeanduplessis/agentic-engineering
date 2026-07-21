# AGENTS.md — flesh-out skill maintenance

## Purpose

Maintain `SKILL.md` as a compact interview workflow for turning vague ideas, plans, and designs into explicit agreed decisions. The skill should keep the assistant from asking broad brainstorming questions or making downstream choices before dependencies are settled.

## How the skill works

`SKILL.md` provides a single question template. It tells the assistant to recap accepted decisions, present mutually exclusive options, recommend one default, explain rejected alternatives briefly, and ask for yes/no confirmation before continuing.

When editing the skill, preserve the core behavior: one focused decision question per turn, recommendation before confirmation, and decision-log continuity between turns.

## Eval and validation

`evals/manifest.json` defines the workflow evaluation for this skill. It force-loads `SKILL.md` and checks that the response includes the decision recap, one question heading, options, a recommendation, and an agreement prompt.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/flesh-out
```

The manifest has no copy fixtures, custom grader, or legacy eval assets.

## Change guidelines

- Keep `SKILL.md` concise and LLM-facing; avoid adding background theory that does not affect execution.
- Update `evals/manifest.json` when the required response contract changes.
- Prefer deterministic checks in `evals/manifest.json`; add skill-local grading only if the template contract cannot be checked with built-ins.
- Preserve equivalent Pi/OpenCode behavior; keep harness-specific capability optional with a shared fallback.
