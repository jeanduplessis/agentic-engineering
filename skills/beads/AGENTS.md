# Purpose

The beads skill teaches agents when and how to use `bd` as durable, dependency-aware task memory. Future changes should preserve the boundary between durable beads tracking and simple session-local tracking. The implementation lives in `SKILL.md`.

# How the skill works

`SKILL.md` defines the trigger conditions, runtime protocol, command habits, dependency semantics, and troubleshooting guidance. The referenced files under `references/` provide deeper detail, but `SKILL.md` is the public skill contract that Pi loads.

# Eval and validation

Behavior evals are declared in `evals/manifest.json` and the workflow cases live in `evals/evals.json`. The evals check that the skill tells agents to inspect and claim durable beads work, avoid beads for tiny same-session work, and avoid silent `bd init` setup changes.

Run full real validation from the repository root with:

```bash
./tools/skill_valid/skill_validate.sh skills/beads
```

# Change guidelines

When changing `SKILL.md`, update `evals/evals.json` if the expected public behavior changes. Keep command examples aligned with current `bd --help` guidance. Do not add instructions that silently initialize, repair, push, pull, or otherwise mutate beads storage unless the user explicitly asked for that setup or recovery operation.
