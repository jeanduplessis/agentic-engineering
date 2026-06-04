# Purpose

The to-issues skill helps agents convert a plan, PRD, spec, or source `ait` epic into dependency-aware `ait` issues. Preserve its focus on tracer-bullet vertical slices that future agents can grab independently after context compaction. The implementation lives in `SKILL.md`.

# How the skill works

`SKILL.md` defines the runtime workflow: gather source context, inspect the codebase only as needed, draft HITL/AFK vertical slices, create `ait` task issues with real dependency edges when `ait` and an `.ait/` project are available, ask how to proceed instead of silently initializing when unavailable, and report the resulting graph. Keep the workflow centered on `ait`; do not switch the default tracker to GitHub issues, Jira, or another system unless the user explicitly asks.

# Eval and validation

Behavior evals are declared in `evals/manifest.json`. The workflow case data lives in `evals/evals.json`, and `evals/grader.py` checks that the skill proposes multiple vertical slices, includes required issue body fields, classifies HITL/AFK work, uses the `ait` creation/dependency workflow, respects the unavailable-project guardrail, and does not claim creation when `ait` issues could not be created.

Run deterministic validation from the repository root when changing this skill:

```bash
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m tools.skill_eval skills/to-issues/evals/manifest.json workflow --results /tmp/to-issues-eval --require-real
```

Run live harness validation only with explicit approval.

# Change guidelines

When changing `SKILL.md`, update `evals/evals.json` and `evals/grader.py` if the expected public behavior changes. Keep command examples aligned with the current `ait` CLI. Avoid silent `ait init` or other setup mutations, and use dependency edges only for real ordering constraints rather than vague relatedness.
