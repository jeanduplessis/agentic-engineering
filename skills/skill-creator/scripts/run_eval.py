#!/usr/bin/env python3
"""DISABLED_LEGACY_NON_PI_SCRIPT.

This legacy trigger evaluator used non-Pi project command files and a non-Pi CLI.
The repo is Pi-only now. Use repo-local Pi tooling instead:

    python3 -m tools.skill_eval skills/<skill-name>/evals/manifest.json workflow --results /tmp/<skill-name>-eval --require-real

For live runs, get explicit approval and set:

    SKILL_EVAL_ALLOW_LIVE_PI=1
"""

from __future__ import annotations

import sys


def main() -> int:
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
