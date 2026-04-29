#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./tools/skill_eval/skill_eval.sh <skill-dir>

Runs full real skill validation for the target skill by invoking tools.skill_valid:
  - validates target shape, eval manifest, and skill-local AGENTS.md
  - runs the live validate-skills gate
  - runs live skill_eval workflow/regression suites with the target skill force-loaded
  - requires strict real-run success

Environment overrides:
  SKILL_VALID_PROVIDER=<provider>
  SKILL_VALID_MODEL=<model>
  SKILL_VALID_THINKING=<off|minimal|low|medium|high|xhigh>
  SKILL_VALID_ARTIFACT_BASE=<dir>

Example:
  ./tools/skill_eval/skill_eval.sh skills/beads
USAGE
}

if [[ $# -ne 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit $([[ $# -eq 1 && ("${1:-}" == "-h" || "${1:-}" == "--help") ]] && echo 0 || echo 2)
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
target="$1"

if [[ ! -d "$target" ]]; then
  echo "skill_eval wrapper: target skill directory not found: $target" >&2
  exit 2
fi

args=("$target" "--allow-live-pi")
if [[ -n "${SKILL_VALID_PROVIDER:-}" ]]; then
  args+=("--provider" "$SKILL_VALID_PROVIDER")
fi
if [[ -n "${SKILL_VALID_MODEL:-}" ]]; then
  args+=("--model" "$SKILL_VALID_MODEL")
fi
if [[ -n "${SKILL_VALID_THINKING:-}" ]]; then
  args+=("--thinking" "$SKILL_VALID_THINKING")
fi
if [[ -n "${SKILL_VALID_ARTIFACT_BASE:-}" ]]; then
  args+=("--artifact-base" "$SKILL_VALID_ARTIFACT_BASE")
fi

cd "$repo_root"
exec python3 -m tools.skill_valid "${args[@]}"
