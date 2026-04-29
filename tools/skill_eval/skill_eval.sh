#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./tools/skill_eval/skill_eval.sh <skill-dir|manifest.json>

Runs full real skill validation for the target skill:
  - resolves <skill-dir>/evals/manifest.json
  - enables live Pi with SKILL_EVAL_ALLOW_LIVE_PI=1 for this process
  - runs the workflow suite with --require-real
  - runs the regression suite too when the manifest declares one
  - fails nonzero if any run is skipped, synthetic, process-failed, not graded, or content-failed

Results:
  Default: skill-eval-results/<skill-name>/real-<timestamp>/<suite>/
  Override root with SKILL_EVAL_RESULTS_ROOT=/path/to/results

Examples:
  ./tools/skill_eval/skill_eval.sh skills/custom-command
  SKILL_EVAL_RESULTS_ROOT=/tmp/custom-command-real ./tools/skill_eval/skill_eval.sh skills/custom-command
USAGE
}

if [[ $# -ne 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit $([[ $# -eq 1 && ("${1:-}" == "-h" || "${1:-}" == "--help") ]] && echo 0 || echo 2)
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

target="$1"
target_path="$(python3 - "$target" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"

if [[ -d "$target_path" ]]; then
  manifest="$target_path/evals/manifest.json"
elif [[ -f "$target_path" ]]; then
  manifest="$target_path"
else
  echo "skill_eval wrapper: target is not a directory or manifest file: $target" >&2
  exit 2
fi

if [[ ! -f "$manifest" ]]; then
  echo "skill_eval wrapper: eval manifest not found: $manifest" >&2
  echo "Expected a skill directory containing evals/manifest.json, or pass a manifest path directly." >&2
  exit 2
fi

skill_name="$(python3 - "$manifest" <<'PY'
import json
import sys
from pathlib import Path
with open(sys.argv[1]) as f:
    data = json.load(f)
print(data.get("skill", {}).get("name") or Path(sys.argv[1]).parents[1].name)
PY
)"

suites=()
while IFS= read -r suite_name; do
  suites+=("$suite_name")
done < <(python3 - "$manifest" <<'PY'
import json
import sys
with open(sys.argv[1]) as f:
    data = json.load(f)
suites = data.get("suites", [])
workflow = any(s.get("name") == "workflow" and s.get("type", "workflow") == "workflow" for s in suites)
regression = any(s.get("name") == "regression" and s.get("type", "regression") == "regression" for s in suites)
if not workflow:
    print("skill_eval wrapper: manifest must declare a workflow suite for full validation", file=sys.stderr)
    sys.exit(2)
print("workflow")
if regression:
    print("regression")
PY
)

safe_skill_name="${skill_name//[^A-Za-z0-9_.-]/-}"
timestamp="$(date +%Y%m%d-%H%M%S)"
results_root="${SKILL_EVAL_RESULTS_ROOT:-$repo_root/skill-eval-results/$safe_skill_name/real-$timestamp}"
mkdir -p "$results_root"

export SKILL_EVAL_ALLOW_LIVE_PI=1
cd "$repo_root"

echo "skill_eval wrapper: running full real validation for $skill_name" >&2
echo "skill_eval wrapper: manifest: $manifest" >&2
echo "skill_eval wrapper: results: $results_root" >&2

for suite in "${suites[@]}"; do
  suite_results="$results_root/$suite"
  mkdir -p "$suite_results"
  echo "skill_eval wrapper: running $suite suite with --require-real" >&2
  python3 -m tools.skill_eval "$manifest" "$suite" --results "$suite_results" --require-real > "$suite_results/stdout.json"
  python3 - "$suite_results/summary.json" "$suite" <<'PY'
import json
import sys
from pathlib import Path
summary_path = Path(sys.argv[1])
suite = sys.argv[2]
summary = json.loads(summary_path.read_text())
errors = []
if summary.get("status") != "completed":
    errors.append(f"suite {suite} did not complete: {summary.get('status')}")
runs = summary.get("runs")
if not isinstance(runs, list):
    errors.append(f"suite {suite} summary is missing runs")
    runs = []
if suite == "workflow" and not runs:
    errors.append("workflow suite produced no runs")
for run in runs:
    case = run.get("case_id", "unknown") if isinstance(run, dict) else "unknown"
    config = run.get("configuration", "unknown") if isinstance(run, dict) else "unknown"
    prefix = f"{suite}/{case}/{config}"
    if not isinstance(run, dict):
        errors.append(f"{prefix}: malformed run")
        continue
    if run.get("harness_mode") != "real" or run.get("synthetic") is True:
        errors.append(f"{prefix}: run was synthetic or not real")
    if run.get("status") != "passed":
        errors.append(f"{prefix}: process status is {run.get('status')}")
    if run.get("passed") is not True:
        errors.append(f"{prefix}: content grade did not pass")
if errors:
    print("skill_eval wrapper: real validation failed", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    print(f"skill_eval wrapper: inspect {summary_path.parent}", file=sys.stderr)
    sys.exit(1)
PY
  echo "skill_eval wrapper: $suite suite passed strict real validation" >&2
done

python3 - "$skill_name" "$manifest" "$results_root" "${suites[@]}" <<'PY'
import json
import sys
skill, manifest, results, *suites = sys.argv[1:]
print(json.dumps({
    "valid": True,
    "skill": skill,
    "manifest": manifest,
    "results": results,
    "suites": suites,
}, sort_keys=True))
PY
