# AGENTS.md — flesh-out skill maintenance

## Purpose

Maintain `SKILL.md` as a compact interview workflow for turning vague ideas, plans, and designs into explicit agreed decisions. The skill should prevent broad brainstorming questions and downstream choices before dependencies are settled.

## How the skill works

`SKILL.md` asks one focused decision question at a time, grounded in the repository and prior dependencies. Each turn gives one best recommendation, followed by zero to two possible variations when useful. Variations adapt the recommendation; they are not competing alternatives and need no rejection rationale.

Do not routinely print a recap of agreed decisions. Keep accepted decisions in a running log, surface only the context needed for the current dependency, and include accepted decisions in the final summary or requested documentation.

After the recommendation, use an available `question` or `ask-user` tool with both an accept action and free-form feedback/custom input. If no such tool exists, use the text fallback in `SKILL.md`. Do not advance until the user accepts or provides feedback. Preserve the same Pi interview behavior through that fallback.

## Eval and validation

`evals/manifest.json` checks for a focused numbered question, one recommendation, an accept-or-feedback prompt with custom input, and the absence of the retired recap, options, and rejected-alternatives format.

Run the deterministic validation wrapper before handing off changes:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/flesh-out
```

The manifest has no copy fixtures, custom grader, or legacy eval assets.

## Change guidelines

- Keep `SKILL.md` concise, direct, and executable for LLMs.
- Update `evals/manifest.json` when the public response contract changes.
- Prefer deterministic checks; add skill-local grading only if built-in checks cannot express the contract.
- Preserve one-question-at-a-time behavior, dependency ordering, repository grounding, accepted-decision tracking, and the final summary.
- Keep question-tool use optional with a shared text fallback.
