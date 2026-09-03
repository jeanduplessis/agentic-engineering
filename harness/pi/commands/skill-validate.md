---
description: "Validate one repo-local skill with the local skill_valid gate"
argument-hint: "<skill-name>"
---

Validate one repo-local skill using the local `skill_valid` tool.

Skill argument: $ARGUMENTS

Rules:
- Require exactly one skill name or `skills/<skill-name>` path. If missing or ambiguous, ask a concise clarification and stop.
- If the argument starts with `skills/`, use it as the target. Otherwise use `skills/<argument>`.
- Run deterministic validation from the repository root: `PYTHONPATH=skill-factory python3 -m tools.skill_valid <target>`.
- Do not run live/model-backed validation by default.
- Run live validation only when the user explicitly opts in: `PYTHONPATH=skill-factory python3 -m tools.skill_valid <target> --allow-live --harness pi`. Pi is the only supported live harness; report an unavailable executable instead of substituting another harness.
- Report whether the skill is valid, summarize failed or warning gates, state whether live validation ran, and include any failure artifact path.
