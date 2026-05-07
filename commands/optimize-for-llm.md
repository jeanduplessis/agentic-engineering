---
description: "Rewrite file for lower token cost and LLM execution reliability; preserve meaning"
argument-hint: "<file-path>"
---

Strictly follow `llm-optimized-rewrite` skill on $ARGUMENTS. Require one path; absent: ask and stop; ambiguous: list matches and ask concise clarification before editing. Read target; optimize for token cost and LLM execution reliability.

When running optional token/smell tools from downstream projects, use the skill-local wrappers:

```bash
python3 /Users/jdp/.agents/skills/llm-optimized-rewrite/scripts/smell_test.py <path>
python3 /Users/jdp/.agents/skills/llm-optimized-rewrite/scripts/count_tokens.py <<'TEXT'
<exact snippet text>
TEXT
```

Do not run `python3 -m tools.llm_optimal_check` or `python3 -m tools.llm_token_count` outside `/Users/jdp/.agents` unless setting `PYTHONPATH=/Users/jdp/.agents`.
