# AGENTS.md — code-quality maintenance

## Purpose

Maintain source-neutral code-quality contracts and criteria shared by local and pull-request review workflows.

## How the skill works

- `SKILL.md` routes prepared packets to shared contracts and one focus reference.
- This skill owns Review Packet and Quality Result schemas, validation, severity/categories, and eight focus criteria.
- Caller workflows own evidence retrieval, packet construction, orchestration, result persistence, merge policy,
  presentation, publication, approval, and fixes.
- `@code-quality-*` agents consume prepared packets only. They never run Git/GitHub discovery or edit source.

## Eval and validation

`evals/manifest.json` covers packet-only ownership and severity/anchor behavior.

```sh
./skill-factory/tools/skill_valid/skill_validate.sh skills/code-quality
PYTHONPATH=skill-factory python3 skills/code-quality/scripts/validate_contract.py self-test
```

Live evals require explicit approval.

## Change guidelines

- Keep packet/result schemas backward-compatible or increment `schema_version`.
- Keep severity action-oriented and category orthogonal.
- Require changed-cause anchors; use supporting locations for omission evidence.
- Only Style emits `Nit` by default.
- Update evals and validator whenever schemas, routes, or severity behavior change.
