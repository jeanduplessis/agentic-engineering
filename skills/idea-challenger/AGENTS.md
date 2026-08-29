# AGENTS.md — idea-challenger skill

## Purpose

`idea-challenger` is a shared Pi/OpenCode skill for skeptical pre-commitment evaluation of product/software engineering ideas. `SKILL.md` is the installable behavior contract. It helps users decide whether an idea should be pursued, conditionally pursued, revised, deferred, or rejected before planning or implementation starts.

## How the skill works

- Starts with quick skeptical triage for low-context ideas.
- Uses a Socratic interview, asking one weakest decision-changing question at a time.
- Tracks a compact product/software gate set internally without turning the interaction into a rubric checklist.
- Separates idea desirability from user/team/repo fit.
- Requires falsifiable evidence for important claims.
- Stops when the decision is stable or a fatal assumption is clear.
- Ends with a decision record, not implementation tasks or planning artifacts.

## Eval and validation

Deterministic eval plumbing lives in `evals/`:

- `evals/manifest.json` defines workflow cases, Pi-only natural trigger cases, and represented capability cases.
  Before live trigger evaluation, supply the ideas, launch plan, and approved spec referenced by the prompts.
- `evals/grader.py` checks for key response contracts such as skeptical posture, one-question challenge turns, decision-record fields, and no premature build planning.

Run repo-level deterministic checks from the repo root when changing this skill:

```sh
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
python3 -m unittest tools.skill_valid.tests.test_skill_validate_wrapper -v
```

Run live harness evals or live skill validation only with explicit user approval.

## Change guidelines

- Keep the skill tightly scoped to product/software engineering ideas.
- Preserve the anti-cheerleader, do-not-build-yet default unless the product decision model intentionally changes.
- Do not add implementation planning, PRD generation, task creation, or code-writing behavior.
- Keep trigger language distinct from `premortem`, code review, architecture review, and planning skills.
- Prefer concise executable instructions over examples unless examples catch a recurring failure.
