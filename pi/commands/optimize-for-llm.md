---
description: "Rewrite file for lower token cost and LLM execution reliability; preserve meaning"
argument-hint: "<file-path>"
skills:
  - llm-optimized-rewrite
---

## Required skills

- `llm-optimized-rewrite`

Current harness must load and follow every skill listed above before continuing. Reuse already loaded skill context. If any required skill is unavailable, stop and report it.

Target path: $ARGUMENTS

Require one path; absent: ask and stop; ambiguous: list matches and ask concise clarification before editing. Read target; optimize for token cost and LLM execution reliability.

Treat the loaded `llm-optimized-rewrite` skill directory as the skill root. When running optional token/smell tools from downstream projects, resolve and invoke bundled wrappers relative to that root:

```bash
python3 <loaded-skill-root>/scripts/smell_test.py <path>
python3 <loaded-skill-root>/scripts/count_tokens.py <<'TEXT'
<exact snippet text>
TEXT
```

Prefer these bundled wrappers. Do not assume the skill package or its repository lives at a fixed absolute path.
