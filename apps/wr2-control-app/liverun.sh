#!/bin/zsh
# liverun.sh — compile + launch a REAL WR2 carousel run through the production ClaudeRunner.
set -euo pipefail
ROOT="${0:A:h}"
cd "$ROOT"
SDK="$(xcrun --show-sdk-path 2>/dev/null || echo /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)"
TARGET="arm64-apple-macosx26.0"
BIN="$ROOT/build/liverun"
mkdir -p "$ROOT/build" "$ROOT/_proof"
SRC=(
  "$ROOT/Sources/Models.swift"
  "$ROOT/Sources/StreamEvent.swift"
  "$ROOT/Sources/ClaudeRunner.swift"
  "$ROOT/Tests/liverun/main.swift"
)
swiftc -sdk "$SDK" -target "$TARGET" -o "$BIN" "${SRC[@]}"
exec "$BIN" "${1:-}"
