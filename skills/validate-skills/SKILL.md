---
name: validate-skills
description: Validates repo-local agent skills against qualitative skill-authoring best practices after deterministic checks. Use when the user asks to validate, lint, audit, or review one or more skill directories, especially via /validate-skills or the live skill_valid reviewer.
license: MIT
metadata:
  author: Callstack
  tags: validation, linting, skill-authoring
---

# Validate Skills

Use read-only inspection to review repo-local skill quality. `tools.skill_valid` owns deterministic parsing/spec/resource checks.
This skill adds judgment about trigger clarity, scope, instruction usefulness, and agent usability.

If the caller names one target, validate only that target. If the caller asks for all skills, inspect each direct child under `skills/`.

## Workflow

1. Resolve each target skill directory and read its `SKILL.md`.
2. Apply the qualitative checklist below. Treat obvious spec breakage you directly observe as a failure.
   Do not recreate every parser rule from `tools.skill_valid`.
3. Report concise per-target results with stable check IDs.
4. If the caller requests a machine-readable final line or sentinel, follow that schema exactly and make it the final non-empty line.

## Severity

- **FAIL**: The skill likely will not load, trigger, or guide agents reliably.
- **WARN**: The skill is usable but has reliability, portability, or maintainability risk.
- **INFO**: Optional improvement.

## Qualitative checklist

### Discovery and trigger behavior

- `description.trigger-context`: Description explains both what the skill does and when to use it.
- `description.specificity`: Description includes concrete trigger keywords and avoids vague text like “helps with data”.
- `description.third-person`: Description is third person, not “I can...” or “You can use...”.
- `description.scope`: Trigger is neither so broad that it over-triggers nor so narrow that likely tasks are missed.

### Instruction value

- `body.adds-context`: Body adds procedures, defaults, examples, gotchas, or repo-specific context the agent would not already know.
- `body.procedure`: Multi-step work is expressed as an actionable workflow, not generic declarations.
- `body.defaults`: When multiple approaches exist, the skill gives a clear default instead of an unranked menu.
- `body.output-template`: If output shape matters, the skill provides a concrete template or example.
- `body.validation-loop`: Fragile or quality-critical workflows include a check/fix/recheck loop.

### Scope and progressive disclosure

- `scope.coherent`: The skill covers one coherent capability that composes with other skills.
- `body.concise`: `SKILL.md` is concise enough to load in full; detailed optional material is moved to referenced files.
- `references.signposted`: References are linked from `SKILL.md` with clear instructions for when to read each file.
- `references.no-chains`: Required knowledge is not hidden behind nested reference chains.

### Portability and maintenance

- `paths.portable`: File paths use forward slashes and relative paths from the skill root.
- `content.timeless`: Time-sensitive claims are avoided or explicitly marked as historical.
- `evals.coverage`: If the skill is behavior-critical, evals cover representative success and failure-prone cases.
- `maintenance.clear`: Skill-local maintenance docs and bundled resources are easy for future agents to update.

## Human-readable report format

```markdown
## Validation Results

### skills/example-skill
- [PASS] description.trigger-context — Description includes what the skill does and when to use it.
- [WARN] body.defaults — Lists three tools without choosing a default.
- [FAIL] references.signposted — SKILL.md points to references/ but does not say when to read each file.
```

## Sentinel contract

When asked for `SKILL_VALID_RESULT=<json>`, make the final non-empty line start with `SKILL_VALID_RESULT=`.
Append one compact JSON object with this schema; do not use a Markdown fence and do not print text after it:

```json
{
  "status": "passed|failed",
  "target": "skills/example",
  "checks": [
    {"id": "description.trigger-context", "status": "passed|failed", "message": "human-readable result"}
  ]
}
```

Use top-level `status: "passed"` only when every check in the sentinel passed.

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Agent Skills best practices](https://agentskills.io/skill-creation/best-practices)
- [Claude skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
