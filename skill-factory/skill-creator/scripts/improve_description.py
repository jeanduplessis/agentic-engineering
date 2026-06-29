#!/usr/bin/env python3
"""DISABLED_LEGACY_NON_PI_SCRIPT.

This legacy optimizer called a non-Pi CLI. The repo is Pi-only now.
Optimize descriptions from repo-local evidence instead:

1. Inspect tools.skill_eval results and failing trigger/workflow cases.
2. Edit the SKILL.md `description` directly.
3. Re-run deterministic validation.
4. Run live Pi evals only with explicit approval.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
