#!/usr/bin/env bash
set -u -o pipefail

# Æ (Agentic Engineering) bootstrap. Builds the `ae` installer from this
# checkout with cargo, then runs it against this checkout. All arguments are
# passed through, so `./setup.sh status` is `ae status`.
#
# AE_BIN runs a prebuilt ae instead of building one (used by the offline tests).

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
AE_DIR="$REPO_ROOT/tools/ae"

if [ -n "${AE_BIN:-}" ]; then
  exec "$AE_BIN" --repo "$REPO_ROOT" "$@"
fi

if ! command -v cargo >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Æ needs Rust's cargo to build its installer, ae.
Install Rust from https://rustup.rs (or run `brew install rust`), then run ./setup.sh again.
EOF
  exit 1
fi

if [ ! -f "$AE_DIR/Cargo.toml" ]; then
  printf 'Æ: missing %s; this checkout looks incomplete.\n' "$AE_DIR/Cargo.toml" >&2
  exit 1
fi

if [ -t 2 ]; then
  printf '\033[2mBuilding ae…\033[0m\r' >&2
fi
if ! cargo build --release --locked --quiet --manifest-path "$AE_DIR/Cargo.toml"; then
  printf 'Æ: building ae failed; see the cargo output above.\n' >&2
  exit 1
fi
if [ -t 2 ]; then
  printf '\033[2K' >&2
fi

exec "$AE_DIR/target/release/ae" --repo "$REPO_ROOT" "$@"
