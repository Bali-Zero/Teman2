#!/bin/zsh
# test.sh — compile and run the unit-test harness.
# Tests cover the pure-Foundation core (Models, WarRoom, StreamEvent, PromptBuilder).
# These do NOT depend on SwiftUI, so they compile with plain swiftc / CLT — no macro plugin.
set -euo pipefail

ROOT="${0:A:h}"
cd "$ROOT"

SDK="$(xcrun --show-sdk-path 2>/dev/null || echo /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk)"
TARGET="arm64-apple-macosx26.0"
BIN="$ROOT/build/testrunner"
mkdir -p "$ROOT/build"

# pure-Foundation sources under test + the test runner
SRC=(
  "$ROOT/Sources/Models.swift"
  "$ROOT/Sources/WarRoom.swift"
  "$ROOT/Sources/StreamEvent.swift"
  "$ROOT/Sources/PromptBuilder.swift"
  "$ROOT/Sources/InstagramCaption.swift"
  "$ROOT/Sources/ExternalImport.swift"
  "$ROOT/Sources/ExternalPostRegistration.swift"
  "$ROOT/Tests/main.swift"
)

echo "▸ compiling tests (Foundation-only, no SwiftUI/macros)…"
swiftc -sdk "$SDK" -target "$TARGET" \
  -o "$BIN" "${SRC[@]}"

echo "▸ running…"
"$BIN"

# QueueWriter has its own harness (separate @main entry point — can't share the
# binary above). Wired in here 2026-07-14: it existed on disk but no script ever
# invoked it (scar-family #2, esiste≠armato) — and turned out to be UNCOMPILABLE as
# written (a file literally named main.swift can't also carry @main without
# -parse-as-library — swiftc's own suggested fix). This is the D2 innocence-test home.
QW_BIN="$ROOT/build/queuewritertest"
echo "▸ compiling QueueWriter tests…"
# Models.swift joined in 2026-07-16: QueueWriter.markPublished now calls
# isQueuePublishEligible/CarouselPhase (the fail-closed publish-state gate, cross-
# finding with the Python A3 daily-reconciler) — a genuine new compile dependency, not
# a workaround.
# WarRoom.swift joined in 2026-07-17 (Codex red-team finding D mirror):
# QueueWriter.addExternalPost's duplicate guard now calls WarRoom.igShortcode for
# shortcode-first URL-equality — WarRoom.swift is Foundation-only (no SwiftUI/AppKit),
# same constraint class as Models.swift/QueueWriter.swift, so it's a safe compile add.
swiftc -parse-as-library -sdk "$SDK" -target "$TARGET" \
  -o "$QW_BIN" "$ROOT/Sources/Models.swift" "$ROOT/Sources/WarRoom.swift" "$ROOT/Sources/QueueWriter.swift" "$ROOT/Tests/queuewritertest/main.swift"
echo "▸ running QueueWriter tests…"
"$QW_BIN"

echo "▸ validating launch-agent configurations…"
"$ROOT/deploy/test-launchagent-config.sh"
