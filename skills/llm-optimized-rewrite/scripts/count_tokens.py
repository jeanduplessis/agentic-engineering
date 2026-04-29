#!/usr/bin/env python3
"""Compatibility wrapper for the repo-level LLM Token Count tool.

Usage:
  python scripts/count_tokens.py < file.txt
  python scripts/count_tokens.py <<'TEXT'
  hello world
  TEXT
  python scripts/count_tokens.py --encoding o200k_base --json < file.txt

If tiktoken is missing, the delegated tool bootstraps it into a persistent venv
(default: ~/.agents/.venvs/llm-optimized-rewrite) and re-executes itself.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.llm_token_count import main


if __name__ == "__main__":
    raise SystemExit(main())
