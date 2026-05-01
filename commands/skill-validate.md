---
description: "Validate one repo-local skill with the local skill_valid gate"
argument-hint: "<skill-name>"
---

Validate one repo-local skill using the local `skill_valid` tool.

Skill argument: $ARGUMENTS

Rules:
- Require exactly one skill name or `skills/<skill-name>` path. If missing or ambiguous, ask a concise clarification and stop.
- If the argument starts with `skills/`, use it as the target. Otherwise use `skills/<argument>`.
- Run from the repository root: `./tools/skill_valid/skill_validate.sh <target>`.
- This wrapper invokes `python3 -m tools.skill_valid <target> --allow-live-pi` and may run live Pi/model validation gates.
- Report whether the skill is valid, summarize failed or warning gates, and include any failure artifact path.
