#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  tools/skill_eval/skill_eval.sh <skill-dir|manifest.json> [suite] [skill_eval args...]

Defaults:
  suite: workflow
  manifest for a skill dir: <skill-dir>/evals/manifest.json

Examples:
  tools/skill_eval/skill_eval.sh skills/custom-command
  tools/skill_eval/skill_eval.sh skills/custom-command regression --require-real
  SKILL_EVAL_ALLOW_LIVE_PI=1 tools/skill_eval/skill_eval.sh skills/custom-command workflow --results /tmp/custom-command-real --require-real
USAGE
}

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit $([[ $# -lt 1 ]] && echo 2 || echo 0)
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

target="$1"
shift

suite="${SKILL_EVAL_SUITE:-workflow}"
if [[ $# -gt 0 && "${1:-}" != -* ]]; then
  suite="$1"
  shift
fi

if [[ -d "$target" ]]; then
  manifest="$target/evals/manifest.json"
elif [[ -f "$target" ]]; then
  manifest="$target"
else
  echo "skill_eval wrapper: target is not a directory or manifest file: $target" >&2
  exit 2
fi

if [[ ! -f "$manifest" ]]; then
  echo "skill_eval wrapper: eval manifest not found: $manifest" >&2
  echo "Expected a skill directory containing evals/manifest.json, or pass a manifest path directly." >&2
  exit 2
fi

cd "$repo_root"
exec python3 -m tools.skill_eval "$manifest" "$suite" "$@"
