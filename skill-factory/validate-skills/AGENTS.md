# AGENTS.md — validate-skills skill maintenance

## Purpose

Maintain `SKILL.md` as the read-only qualitative validation checklist for repo-local agent skills. The skill should help agents inspect one requested skill or all direct children under `skills/` for trigger clarity, instruction value, scope, progressive disclosure, and maintainability. Deterministic SKILL.md spec/resource checks live in `skill-factory/tools/skill_valid/spec_checks.py`.

## How the skill works

`SKILL.md` defines target selection, the qualitative validation checklist, the concise human-readable report shape, and the rule for honoring caller-provided machine-readable sentinels. Keep the checklist small enough for agents to apply directly without loading extra references. Do not duplicate every deterministic parser/spec rule already enforced by `skill-factory/tools/skill_valid`.

## Eval and validation

`evals/manifest.json` defines the workflow evaluation. It force-loads `SKILL.md`, copies `evals/fixtures/valid-skill-repo` into an isolated sandbox, asks the agent to validate the fixture skill, and uses `evals/grader.py` to verify the final sentinel JSON.

Run the full local validity gate from the repository root with:

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/validate-skills
```

## Change guidelines

- Keep `SKILL.md` read-only: the validation workflow should inspect and report, not edit target skills.
- Keep deterministic spec/resource validation in `skill-factory/tools/skill_valid/spec_checks.py`; this skill should stay judgment-oriented.
- Update `evals/manifest.json`, `evals/grader.py`, or `evals/fixtures/valid-skill-repo` when the output contract or core checklist changes.
- Preserve the instruction that caller-requested machine-readable sentinel lines must be final, because `skill-factory/tools/skill_valid` depends on that behavior.
- Keep the checklist compatible with the shared repo conventions in `skills/AGENTS.md` unless the repository-wide contract changes.
