#!/bin/zsh
# test-integration.sh — drive the REAL ClaudeRunner against the live `claude` CLI.
# Costs a tiny amount of OAuth quota (~1 cheap prompt). Foundation-only, no SwiftUI.
set -euo pipefail
ROOT="${0:A:h}"
cd "$ROOT"
SDK="$(xcrun --show-sdk-path 2>/dev/null || echo /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)"
TARGET="arm64-apple-macosx26.0"
BIN="$ROOT/build/integration"
mkdir -p "$ROOT/build"

SRC=(
  "$ROOT/Sources/Models.swift"
  "$ROOT/Sources/StreamEvent.swift"
  "$ROOT/Sources/ClaudeRunner.swift"
  "$ROOT/Tests/integration/main.swift"
)
echo "▸ compiling integration test…"
swiftc -sdk "$SDK" -target "$TARGET" -o "$BIN" "${SRC[@]}"
echo "▸ running (drives the real claude CLI)…"
"$BIN"
