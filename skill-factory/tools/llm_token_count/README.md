# llm_token_count

`llm_token_count` is the repo-level exact token-counting tool for LLM-facing text.

## CLI

```sh
PYTHONPATH=skill-factory python3 -m tools.llm_token_count < file.txt
PYTHONPATH=skill-factory python3 -m tools.llm_token_count --json < file.txt
PYTHONPATH=skill-factory python3 -m tools.llm_token_count --model gpt-5 --json < file.txt
PYTHONPATH=skill-factory python3 -m tools.llm_token_count --encoding o200k_base --json < file.txt
```

Default output preserves the legacy human contract:

```text
tokens=<n> encoding=<encoding> source=<source> characters=<n>
```

`--json` emits:

```json
{"tokens":10,"encoding":"o200k_base","source":"model:gpt-5->encoding:o200k_base","characters":42}
```

## API

```python
from tools.llm_token_count import count_text

metrics = count_text("exact text", model="gpt-5")
```

`count_text` returns the same metric fields as the JSON CLI: `tokens`, `encoding`, `source`, and `characters`. `model` and `encoding` are mutually exclusive. Special-token sentinel strings are treated as normal user text.

## Compatibility wrapper

`skills/llm-optimized-rewrite/scripts/count_tokens.py` remains a compatibility wrapper around this tool. Existing invocations and JSON/default output are preserved.

## Dependency bootstrap

The CLI bootstraps `tiktoken` into `~/.agents/.venvs/llm-optimized-rewrite` when it is missing, preserving the legacy environment variables:

- `LLM_OPTIMIZED_REWRITE_VENV`
- `TOKEN_EFFICIENT_REWRITE_VENV`
- `LLM_OPTIMIZED_REWRITE_NO_BOOTSTRAP=1`
