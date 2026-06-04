# AGENTS.md — premortem skill maintenance

## Purpose

Maintain `SKILL.md` as a compact workflow for running premortems on concrete plans, launches, hires, strategies, and decisions. The skill should make the assistant assume the plan failed 6 months from now, identify grounded failure modes, and turn them into a revised plan.

## How the skill works

`SKILL.md` defines the trigger scope, minimum context threshold, premortem frame, failure-mode analysis, synthesis structure, output defaults, and guardrails. Preserve the core behavior: gather the plan, affected people, and success criteria; state the “this already failed” frame; analyze genuine failure modes independently; and produce the synthesis sections.

Default output should stay chat-first. Optional files are allowed only when the user asks or when a file clearly helps.

## Eval and validation

`evals/manifest.json` defines the workflow evaluation for this skill. It force-loads `SKILL.md` with a concrete workshop-launch premortem prompt and checks that the response is non-empty and includes the required synthesis sections.

Run the deterministic/live validation wrapper before handing off changes when live execution is approved:

```sh
./tools/skill_valid/skill_validate.sh skills/premortem
```

The manifest has no copy fixtures, custom grader, or legacy eval assets.

## Change guidelines

- Keep `SKILL.md` concise and execution-focused; avoid adding background theory that does not change behavior.
- Keep the minimum context threshold: plan, affected people, and success criteria.
- Keep recommendations concrete and mapped to failure modes.
- Update `evals/manifest.json` when required report sections or output defaults change.
- Prefer deterministic manifest checks. Add a skill-local grader only if generic checks cannot express the contract.
- Preserve equivalent Pi/OpenCode behavior; keep harness-specific capability optional with a shared fallback.
