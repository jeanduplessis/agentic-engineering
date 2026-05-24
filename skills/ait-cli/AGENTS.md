# Purpose

The `ait-cli` skill teaches agents to use `ait` as durable, structured, repository-local task memory. Preserve the distinction between `.ait/` issue state and beads; agents should prefer `ait` only when the repo or user intent calls for it.

# How the skill works

`SKILL.md` defines trigger conditions, safe command habits, actor requirements, JSON-envelope handling, dependency semantics, lifecycle commands, and handoff expectations. It is the public contract Pi loads.

# Eval and validation

Behavior evals are declared in `evals/manifest.json`. They check that agents use `ait` for durable work, run startup checks, avoid direct `.ait/` file edits, require actors for mutations, and ask before unsafe setup/recovery actions.

Run deterministic validation from the repository root:

```bash
python3 -m unittest tools.skill_eval.tests.test_skill_eval -v
python3 -m unittest tools.skill_valid.tests.test_skill_valid -v
```

Run live Pi eval/validation only with explicit approval.

# Change guidelines

When changing CLI behavior in `SKILL.md`, update eval checks to match the public contract. Keep examples JSON-first and aligned with current `ait` behavior. Do not add instructions that silently initialize, import, repair, delete, force-close, or directly edit `.ait/` storage unless the user explicitly requests or approves that operation.
