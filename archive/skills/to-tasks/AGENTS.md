# Purpose

The to-tasks skill helps agents convert a plan, PRD, spec, or source bead into dependency-aware `br` tasks. Preserve its focus on tracer-bullet vertical slices that future agents can grab independently after context compaction. The implementation lives in `SKILL.md`.

# How the skill works

`SKILL.md` defines the runtime workflow: gather source context, inspect the codebase only as needed, draft HITL/AFK vertical slices, create beads tasks with real dependency edges when `br` and a beads database are available, ask how to proceed instead of silently initializing when unavailable, and report the resulting graph. Keep the workflow centered on `br`; do not switch the default tracker to GitHub issues or another system unless the user explicitly asks.

# Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case data lives in `evals/evals.json`, and `evals/grader.py` checks that the skill proposes multiple vertical slices, includes required task body fields, classifies HITL/AFK work, uses the `br` creation/dependency workflow, respects the unavailable-database guardrail, and does not claim creation when beads could not be created.

Run full real validation from the repository root with:

```bash
./skill-factory/tools/skill_valid/skill_validate.sh skills/to-tasks
```

# Change guidelines

When changing `SKILL.md`, update `evals/evals.json` and `evals/grader.py` if the expected public behavior changes. Keep command examples aligned with the current `br` CLI. Avoid silent `br init` or other setup mutations, and use dependency edges only for real ordering constraints rather than vague relatedness.
