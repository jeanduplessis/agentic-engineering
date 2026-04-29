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
  SKILL_EVAL_VERBOSE=1       Show raw skill_valid progress logs
  SKILL_EVAL_RAW_JSON=1      Print the raw skill_valid JSON after the friendly summary
  NO_COLOR=1                 Disable color output

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

enable_color=0
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  enable_color=1
fi

if [[ "$enable_color" == "1" ]]; then
  bold=$'\033[1m'
  dim=$'\033[2m'
  red=$'\033[31m'
  green=$'\033[32m'
  yellow=$'\033[33m'
  blue=$'\033[34m'
  cyan=$'\033[36m'
  reset=$'\033[0m'
else
  bold=""
  dim=""
  red=""
  green=""
  yellow=""
  blue=""
  cyan=""
  reset=""
fi

info() { printf '%sℹ%s %s\n' "$cyan" "$reset" "$*" >&2; }
error() { printf '%s✗%s %s\n' "$red" "$reset" "$*" >&2; }

if [[ ! -d "$target" ]]; then
  error "Target skill directory not found: ${bold}$target${reset}"
  echo "Expected a repo-local skill directory such as: skills/beads" >&2
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

stdout_file="$(mktemp)"
stderr_file="$(mktemp)"
cleanup() {
  rm -f "$stdout_file" "$stderr_file"
}
trap cleanup EXIT

cd "$repo_root"

printf '%s%sValidating skill%s %s%s%s\n' "$bold" "$blue" "$reset" "$bold" "$target" "$reset" >&2
info "Live Pi/model execution is allowed if required by later gates."
if [[ -n "${SKILL_VALID_PROVIDER:-}${SKILL_VALID_MODEL:-}${SKILL_VALID_THINKING:-}" ]]; then
  info "Execution profile: provider=${SKILL_VALID_PROVIDER:-default} model=${SKILL_VALID_MODEL:-default} thinking=${SKILL_VALID_THINKING:-default}"
fi

set +e
python3 -m tools.skill_valid "${args[@]}" >"$stdout_file" 2>"$stderr_file"
code=$?
set -e

if [[ "${SKILL_EVAL_VERBOSE:-}" == "1" && -s "$stderr_file" ]]; then
  printf '\n%sRaw skill_valid logs%s\n' "$bold" "$reset" >&2
  sed 's/^/  /' "$stderr_file" >&2
fi

if [[ ! -s "$stdout_file" ]]; then
  error "skill_valid produced no JSON output."
  if [[ -s "$stderr_file" ]]; then
    printf '\n%sDiagnostics%s\n' "$bold" "$reset" >&2
    sed 's/^/  /' "$stderr_file" >&2
  fi
  exit "$code"
fi

set +e
format_status=$(
  SKILL_EVAL_COLOR="$enable_color" python3 - "$stdout_file" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    result = json.loads(path.read_text())
except Exception as exc:
    print(f"Could not parse skill_valid JSON: {exc}", file=sys.stderr)
    sys.exit(2)

use_color = os.environ.get("SKILL_EVAL_COLOR") == "1"

def c(code: str) -> str:
    return f"\033[{code}m" if use_color else ""

BOLD = c("1")
DIM = c("2")
RED = c("31")
GREEN = c("32")
YELLOW = c("33")
BLUE = c("34")
CYAN = c("36")
RESET = c("0")

status_style = {
    "passed": (GREEN, "✓"),
    "failed": (RED, "✗"),
    "not_run": (YELLOW, "-"),
}

gate_labels = {
    "target": "Target shape",
    "eval_manifest": "Eval manifest",
    "agents_md": "Maintenance docs",
    "live_opt_in": "Live opt-in",
    "validate_skills": "validate-skills review",
    "live_eval": "Live behavior evals",
}

gate_order = ["target", "eval_manifest", "agents_md", "live_opt_in", "validate_skills", "live_eval"]

target = result.get("target", "<unknown>")
valid = result.get("valid") is True
summary_color = GREEN if valid else RED
summary_word = "VALID" if valid else "INVALID"

print()
print(f"{BOLD}{summary_color}{'Skill validation passed' if valid else 'Skill validation failed'}{RESET}")
print(f"{DIM}Target:{RESET} {target}")
print()
print(f"{BOLD}Gate results{RESET}")

gates = result.get("gates", {})
for gate_name in gate_order:
    gate = gates.get(gate_name, {"status": "not_run", "message": "not run"})
    status = gate.get("status", "not_run")
    color, icon = status_style.get(status, (YELLOW, "?"))
    label = gate_labels.get(gate_name, gate_name)
    message = gate.get("message", "")
    print(f"  {color}{icon}{RESET} {BOLD}{label}{RESET} {DIM}({gate_name}){RESET}")
    if message:
        print(f"      {message}")

    details = gate.get("details") if isinstance(gate.get("details"), dict) else {}
    if gate_name == "eval_manifest" and details:
        manifest = details.get("manifest")
        asset_refs = details.get("asset_refs") or []
        if manifest:
            print(f"      {DIM}manifest:{RESET} {manifest}")
        if asset_refs:
            print(f"      {DIM}assets:{RESET} {', '.join(asset_refs)}")

    sentinel = details.get("sentinel") if isinstance(details, dict) else None
    checks = sentinel.get("checks") if isinstance(sentinel, dict) else None
    if checks:
        print(f"      {DIM}validate-skills checks:{RESET}")
        for check in checks:
            check_status = check.get("status", "not_run") if isinstance(check, dict) else "not_run"
            check_color, check_icon = status_style.get(check_status, (YELLOW, "?"))
            check_id = check.get("id", "<unknown>") if isinstance(check, dict) else "<unknown>"
            check_msg = check.get("message", "") if isinstance(check, dict) else str(check)
            print(f"        {check_color}{check_icon}{RESET} {check_id}: {check_msg}")

failure_artifacts = result.get("failure_artifacts")
if failure_artifacts:
    print()
    print(f"{BOLD}Debug artifacts{RESET}")
    print(f"  {failure_artifacts}")

print()
print(f"{BOLD}Result:{RESET} {summary_color}{summary_word}{RESET}")
PY
)
formatter_code=$?
set -e

if [[ "$formatter_code" -ne 0 ]]; then
  error "Could not render friendly validation summary. Raw JSON follows:"
  cat "$stdout_file"
  exit "$code"
fi

printf '%s\n' "$format_status"

if [[ "${SKILL_EVAL_RAW_JSON:-}" == "1" ]]; then
  printf '\n%sRaw JSON%s\n' "$bold" "$reset"
  cat "$stdout_file"
  printf '\n'
fi

exit "$code"
