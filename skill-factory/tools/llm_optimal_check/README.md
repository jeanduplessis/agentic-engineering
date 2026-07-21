# llm_optimal_check

`llm_optimal_check` is the repo-level deterministic LLM optimization-readiness checker for Markdown, prompt, command, skill, and technical prose files. It is heuristic and never calls an LLM.

## CLI

```sh
PYTHONPATH=skill-factory python3 -m tools.llm_optimal_check <path>
```

The CLI emits JSON only on success and exits `0` for completed `pass`, `warn`, or `fail` analyses. Runtime/tool errors exit nonzero and write diagnostics to stderr.

JSON contract:

```json
{
  "status": "pass|warn|fail",
  "score": 100,
  "metrics": {
    "tokens": 10,
    "encoding": "o200k_base",
    "source": "model:gpt-5->encoding:o200k_base",
    "characters": 42,
    "path": "skills/example/SKILL.md",
    "document_kind": "skill",
    "lines": 12,
    "paragraphs": 3,
    "frontmatter_excluded": true,
    "frontmatter_lines": 3,
    "analyzed_preview": "..."
  },
  "findings": [
    {
      "rule_id": "REL002",
      "severity": "major",
      "category": "reliability",
      "location": {"line": 12},
      "evidence": "...",
      "message": "...",
      "suggestion": "..."
    }
  ]
}
```

Status semantics:

- `pass`: score `>= 90`; no blocking optimization concerns.
- `warn`: score `>= 70` and `< 90`; advisory findings are visible but non-blocking in `skill_valid`.
- `fail`: score `< 70`; blocks `skill_valid` before live gates.

## API

```python
from tools.llm_optimal_check import check_path

report = check_path("skills/example/SKILL.md")
```

`check_path` returns the same report dictionary as the CLI without spawning a subprocess. The checker uses `tools.llm_token_count.count_text` for exact token metrics.

## Compatibility wrapper

`skills/llm-optimized-rewrite/scripts/smell_test.py <path>` remains a compatibility wrapper around this tool. The old script keeps the historical JSON schema and error prefix. The phrase “smell test” is legacy wording; use **LLM Optimal Check** for new code and docs.

## Skill validation integration

`tools.skill_valid` runs this checker on only the target skill's primary `SKILL.md` in v1. The `llm_optimal_check` gate embeds a compact report with status, score, useful metrics, and all findings while excluding bulky preview/body fields. Tool errors fail closed.
