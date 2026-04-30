---
name: validate-skills
description: Validates repo-local agent skills against the agentskills.io spec and skill authoring best practices. Use when the user asks to validate, lint, audit, or review one or more skill directories, especially via /validate-skills or skill_valid.
license: MIT
metadata:
  author: Callstack
  tags: validation, linting, skill-authoring
---

# Validate Skills

Use read-only inspection to review the requested skill target. If the caller names one target, validate only that target.
If the caller asks for all skills, inspect each direct child under `skills/`.

## Workflow

1. Identify each target skill directory and its skill definition file.
2. Read the skill definition frontmatter and body.
3. Apply the checklist below. Treat missing required fields, invalid formats, or unclear trigger behavior as failures.
4. Report concise per-target results.
5. When the caller requests a machine-readable final line or sentinel, follow that schema exactly.
   Make it the final non-empty line.

## Checklist

### agentskills.io spec

- `name` exists, is 1-64 characters, uses lowercase alphanumeric characters plus hyphens, and has no leading, trailing, or consecutive hyphens.
- Directory basename equals the `name` field.
- `description` exists, is non-empty, and is 1-1024 characters.
- Optional `license`, `metadata`, and `compatibility` fields are valid if present.

### Skill authoring best practices

- Description is third person and explains both what the skill does and when to use it.
- Body is under 500 lines.
- Referenced resources are one level deep; avoid chains where one reference points to another required reference.
- Resource references use Markdown links when presented as links.
- Body does not merely repeat the description.
- Instructions are concise and add context the agent would not already know.

## Human-readable report format

```markdown
## Validation Results

### skills/example-skill
- [PASS] name format valid
- [FAIL] directory name does not match frontmatter name
- [PASS] description length OK (156 chars)
```

## References

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skill best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
