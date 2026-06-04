from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .regression import promote_failures_to_regression_cases
from .runner import run_suite


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "promote-regressions":
        parser = argparse.ArgumentParser(description="Promote failed real skill eval runs into regression cases.")
        parser.add_argument("command")
        parser.add_argument("manifest", type=Path, help="Path to eval manifest JSON")
        parser.add_argument("--results", type=Path, required=True, help="Result directory containing summary.json")
        parser.add_argument("--output", type=Path, help="Output manifest path; defaults to updating the input manifest")
        parser.add_argument("--source-bead", help="Bead/review ID that discovered the failure")
        args = parser.parse_args()
        summary = promote_failures_to_regression_cases(
            manifest_path=args.manifest,
            result_root=args.results,
            output_manifest_path=args.output,
            source_bead=args.source_bead,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    parser = argparse.ArgumentParser(description="Run a skill eval suite.")
    parser.add_argument("manifest", type=Path, help="Path to eval manifest JSON")
    parser.add_argument("suite", help="Suite name to run")
    parser.add_argument("--results", type=Path, default=Path("skill-eval-results"), help="Result directory")
    parser.add_argument("--require-real", action="store_true", help="Reject static/replay harness configurations")
    parser.add_argument("--allow-live", action="store_true", help="Explicitly allow real harness/model execution")
    parser.add_argument("--allow-live-pi", action="store_true", help="Deprecated alias for --allow-live")
    args = parser.parse_args()

    configurations = None
    if args.allow_live or args.allow_live_pi:
        from .manifest import load_manifest

        configurations = {
            name: {**config, "allow_live": True}
            for name, config in load_manifest(args.manifest).configurations.items()
        }
    summary = run_suite(
        args.manifest,
        args.suite,
        args.results,
        configurations=configurations,
        require_real=args.require_real,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
