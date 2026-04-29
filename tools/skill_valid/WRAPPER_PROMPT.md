You are validating exactly one repo-local skill for the `skill_valid` tool.

Target skill: `{{TARGET_SKILL}}`

Use the loaded validate-skills skill as the authoritative reviewer. Validate only the target skill above against the agentskills.io skill specification and this repository's skill best practices. Use only read-only inspection.

Return any concise human-readable findings you need, then make the final non-empty stdout line exactly:

`SKILL_VALID_RESULT=<json>`

The JSON after `SKILL_VALID_RESULT=` must be one object with this schema:

```json
{
  "status": "passed|failed",
  "target": "{{TARGET_SKILL}}",
  "checks": [
    {"id": "short-stable-id", "status": "passed|failed", "message": "human-readable result"}
  ]
}
```

Rules:
- `target` must equal `{{TARGET_SKILL}}`.
- `checks` must be non-empty.
- Every check object must include `id`, `status`, and `message`.
- Use top-level `status: "passed"` only when every check passed.
- Do not print anything after the `SKILL_VALID_RESULT=` line.
