#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$ROOT_DIR/dist"

echo "Building for darwin-arm64..."
bun build --compile --target=bun-darwin-arm64 "$ROOT_DIR/src/index.ts" --outfile "$ROOT_DIR/dist/darwin-arm64"

echo "Building for darwin-amd64..."
bun build --compile --target=bun-darwin-x64 "$ROOT_DIR/src/index.ts" --outfile "$ROOT_DIR/dist/darwin-amd64"

echo "Building for linux-amd64..."
bun build --compile --target=bun-linux-x64 "$ROOT_DIR/src/index.ts" --outfile "$ROOT_DIR/dist/linux-amd64"

echo "Building for linux-arm64..."
bun build --compile --target=bun-linux-arm64 "$ROOT_DIR/src/index.ts" --outfile "$ROOT_DIR/dist/linux-arm64"

echo "Building for windows-amd64..."
bun build --compile --target=bun-windows-x64 "$ROOT_DIR/src/index.ts" --outfile "$ROOT_DIR/dist/windows-amd64.exe"

echo ""
echo "Build complete. Binaries:"
ls -lh "$ROOT_DIR/dist/"
