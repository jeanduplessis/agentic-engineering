#!/usr/bin/env python3
"""Compatibility wrapper for the repo-level LLM Optimal Check tool.

This legacy entry point preserves the historical smell_test.py CLI and JSON
contract while delegating implementation to tools.llm_optimal_check.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.llm_optimal_check import main


if __name__ == "__main__":
    raise SystemExit(main(program_name="smell_test"))
