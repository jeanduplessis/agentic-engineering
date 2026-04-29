#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  ./skills/llm-optimized-rewrite/scripts/smell_test.sh <file>

Runs the static LLM optimized-state smell test for a Markdown, prompt, command,
skill, or technical prose file by invoking scripts/smell_test.py:
  - excludes leading YAML frontmatter from analyzed body/token metrics
  - counts exact tokens through the bundled count_tokens.py path
  - reports token-cost and reliability heuristic findings
  - exits 0 for completed pass/warn/fail analyses
  - exits nonzero only for usage or runtime errors

Environment overrides:
  SMELL_TEST_VERBOSE=1       Show command, exit code, and raw stderr diagnostics
  SMELL_TEST_RAW_JSON=1      Print the raw smell_test.py JSON after the friendly summary
  NO_COLOR=1                 Disable color output

Example:
  ./skills/llm-optimized-rewrite/scripts/smell_test.sh skills/llm-optimized-rewrite/SKILL.md
USAGE
}

if [[ $# -ne 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit $([[ $# -eq 1 && ("${1:-}" == "-h" || "${1:-}" == "--help") ]] && echo 0 || echo 2)
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../../.." && pwd)"
python_script="$script_dir/smell_test.py"
target_input="$1"

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

if [[ ! -f "$target_input" ]]; then
  error "Target file not found: ${bold}$target_input${reset}"
  echo "Expected a Markdown, prompt, command, skill, or technical prose file." >&2
  exit 2
fi

if [[ ! -f "$python_script" ]]; then
  error "Python smell-test script not found: ${bold}$python_script${reset}"
  exit 2
fi

target="$(cd "$(dirname "$target_input")" && pwd)/$(basename "$target_input")"
stdout_file="$(mktemp)"
stderr_file="$(mktemp)"
cleanup() {
  rm -f "$stdout_file" "$stderr_file"
}
trap cleanup EXIT

cd "$repo_root"

printf '%s%sRunning smell test%s %s%s%s\n' "$bold" "$blue" "$reset" "$bold" "$target_input" "$reset" >&2
info "Static analysis only; no LLM calls are made. Findings are heuristic suggestions, not patches."

set +e
python3 "$python_script" "$target" >"$stdout_file" 2>"$stderr_file"
code=$?
set -e

if [[ "${SMELL_TEST_VERBOSE:-}" == "1" ]]; then
  printf '\n%sRaw smell_test.py diagnostics%s\n' "$bold" "$reset" >&2
  printf '  command: python3 %s %s\n' "$python_script" "$target" >&2
  printf '  exit: %s\n' "$code" >&2
  if [[ -s "$stderr_file" ]]; then
    printf '  stderr:\n' >&2
    sed 's/^/    /' "$stderr_file" >&2
  else
    printf '  stderr: <empty>\n' >&2
  fi
fi

if [[ ! -s "$stdout_file" ]]; then
  error "smell_test.py produced no JSON output."
  if [[ -s "$stderr_file" ]]; then
    printf '\n%sDiagnostics%s\n' "$bold" "$reset" >&2
    sed 's/^/  /' "$stderr_file" >&2
  fi
  exit "$code"
fi

set +e
format_status=$(
  SMELL_TEST_COLOR="$enable_color" python3 - "$stdout_file" <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    result = json.loads(path.read_text())
except Exception as exc:
    print(f"Could not parse smell_test.py JSON: {exc}", file=sys.stderr)
    sys.exit(2)

use_color = os.environ.get("SMELL_TEST_COLOR") == "1"

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
    "pass": (GREEN, "✓", "Smell test passed", "PASS"),
    "warn": (YELLOW, "!", "Smell test warning", "WARN"),
    "fail": (RED, "✗", "Smell test failed", "FAIL"),
}
severity_style = {
    "major": (RED, "✗"),
    "minor": (YELLOW, "!"),
    "info": (BLUE, "i"),
    "experimental": (CYAN, "?"),
}

status = result.get("status", "unknown")
score = result.get("score", "?")
metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
findings = result.get("findings") if isinstance(result.get("findings"), list) else []
status_color, status_icon, title, summary_word = status_style.get(
    status, (YELLOW, "?", "Smell test status unknown", str(status).upper())
)

target = metrics.get("path", "<unknown>")
print()
print(f"{BOLD}{status_color}{title}{RESET}")
print(f"{DIM}Target:{RESET} {target}")
print(f"{DIM}Score:{RESET} {score}/100 ({status_color}{summary_word}{RESET})")
print()
print(f"{BOLD}Metrics{RESET}")
metric_rows = [
    ("document", metrics.get("document_kind")),
    ("tokens", metrics.get("tokens")),
    ("characters", metrics.get("characters")),
    ("lines", metrics.get("lines")),
    ("paragraphs", metrics.get("paragraphs")),
    ("encoding", metrics.get("encoding")),
    ("source", metrics.get("source")),
]
for label, value in metric_rows:
    if value is not None:
        print(f"  {DIM}{label}:{RESET} {value}")
frontmatter = metrics.get("frontmatter_excluded")
if frontmatter is not None:
    line_count = metrics.get("frontmatter_lines", 0)
    print(f"  {DIM}frontmatter excluded:{RESET} {frontmatter} ({line_count} lines)")

print()
print(f"{BOLD}Findings{RESET}")
if not findings:
    print(f"  {GREEN}✓{RESET} No findings")
else:
    for item in findings:
        if not isinstance(item, dict):
            print(f"  {YELLOW}?{RESET} {item}")
            continue
        severity = item.get("severity", "unknown")
        sev_color, sev_icon = severity_style.get(severity, (YELLOW, "?"))
        rule_id = item.get("rule_id", "<rule>")
        category = item.get("category", "unknown")
        message = item.get("message", "")
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        line = location.get("line")
        end_line = location.get("end_line")
        if line and end_line:
            loc = f"line {line}-{end_line}"
        elif line:
            loc = f"line {line}"
        else:
            loc = "unknown location"
        print(f"  {sev_color}{sev_icon}{RESET} {BOLD}{rule_id}{RESET} {DIM}{severity}/{category}, {loc}{RESET}")
        if message:
            print(f"      {message}")
        evidence = item.get("evidence")
        if evidence:
            compact_evidence = " ".join(str(evidence).split())
            print(f"      {DIM}evidence:{RESET} {compact_evidence}")
        suggestion = item.get("suggestion")
        if suggestion:
            print(f"      {DIM}suggestion:{RESET} {suggestion}")

print()
print(f"{BOLD}Result:{RESET} {status_color}{status_icon} {summary_word}{RESET}")
PY
)
formatter_code=$?
set -e

if [[ "$formatter_code" -ne 0 ]]; then
  error "Could not render friendly smell-test summary. Raw JSON follows:"
  cat "$stdout_file"
  exit "$code"
fi

printf '%s\n' "$format_status"

if [[ "${SMELL_TEST_RAW_JSON:-}" == "1" ]]; then
  printf '\n%sRaw JSON%s\n' "$bold" "$reset"
  cat "$stdout_file"
  printf '\n'
fi

exit "$code"
