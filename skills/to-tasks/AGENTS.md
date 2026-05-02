# Purpose

The to-tasks skill helps agents convert a plan, PRD, spec, or source bead into dependency-aware `br` tasks. Preserve its focus on tracer-bullet vertical slices that future agents can grab independently after context compaction. The implementation lives in `SKILL.md`.

# How the skill works

`SKILL.md` defines the runtime workflow: gather source context, inspect the codebase only as needed, draft HITL/AFK vertical slices, quiz the user for approval, create beads tasks with real dependency edges, and report the resulting graph. Keep the workflow centered on `br`; do not switch the default tracker to GitHub issues or another system unless the user explicitly asks.

# Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case data lives in `evals/evals.json`, and `evals/grader.py` checks that the skill proposes multiple vertical slices, includes the required slice fields, asks the approval quiz, classifies HITL/AFK work, and does not claim to create beads before approval.

Run full real validation from the repository root with:

```bash
./tools/skill_valid/skill_validate.sh skills/to-tasks
```

# Change guidelines

When changing `SKILL.md`, update `evals/evals.json` and `evals/grader.py` if the expected public behavior changes. Keep command examples aligned with the current `br` CLI. Preserve the approval gate before task creation, avoid silent `br init` or other setup mutations, and use dependency edges only for real ordering constraints rather than vague relatedness.
