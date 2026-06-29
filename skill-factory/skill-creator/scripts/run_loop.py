#!/usr/bin/env python3
"""DISABLED_LEGACY_NON_PI_SCRIPT.

This legacy loop depended on disabled non-Pi evaluator/optimizer scripts.
Use `tools.skill_eval` and `tools.skill_valid` for Pi skill iteration instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
