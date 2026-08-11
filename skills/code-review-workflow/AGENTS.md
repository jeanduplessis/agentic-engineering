# AGENTS.md — code-review-workflow maintenance

## Purpose

Maintain local adapter/orchestrator for deterministic code review. Shared criteria and specialized agents belong to
`code-quality`.

## How the skill works

`SKILL.md` routes `/code-review-local` into this local workflow. `references/scope.md` resolves local changes.
`references/orchestrator.md` builds a shared Review Packet, invokes all
eight `@code-quality-*` agents, validates/persists results, merges findings, requests confirmation, fixes, validates,
and reports. `scripts/gate_result.py` is the required response acceptance boundary: it preserves raw attempts,
canonicalizes deterministic transport/format deviations, strictly validates review semantics, enforces one retry,
and creates the only allowed irrecoverable-response `BLOCKED` fallback.

## Eval and validation

`evals/manifest.json` covers local packet construction, eight-agent execution, approval, and action policy.

```sh
PYTHONPATH=skill-factory python3 -m unittest discover -s skills/code-review-workflow/tests -v
./skill-factory/tools/skill_valid/skill_validate.sh skills/code-review-workflow
```

Live validation requires explicit approval.

## Change guidelines

- Keep quality criteria and result schema in `code-quality`, not this workflow.
- Preserve confirmation before fixes.
- Validate local drift before agent launch and result acceptance.
- Normalize only through `scripts/gate_result.py`; never infer substantive review content or overwrite a finalized result.
- Update evals when local scope, packet construction, action policy, or reporting changes.
- Preserve sequential fallback when concurrent subagents are unavailable.
