#!/usr/bin/env bash
# injected_surface_sessionstart.sh — RECEPTOR for the turn-1 injected context surface.
#
# Sibling of proprioception_sessionstart.sh, and it inherits that file's
# ANTI-CALM-LIAR CONTRACT: this receptor is NEVER silent while it is armed.
#   - measurable + under budget -> one-line heartbeat (proves the receptor ran)
#   - measurable + over budget  -> the same line, marked, naming the biggest files
#   - script missing / errored  -> one visible line saying so (fail-open)
# Silence therefore means exactly one thing: the hook is not registered.
#
# WHY it prints even when everything is fine: the number it reports is the only
# per-machine record of what a session was handed at turn 1. On 2026-08-21 an
# audit measured ~150 KB; ten days later it was 783,444 B and nobody saw the
# growth, because nothing ever printed it (superscar #2 — the signal was never
# emitted, so it could never be missed). A heartbeat that costs one line is the
# cheapest defence against that specific silence.
#
# Budget: hard <=4s (the attestation is a handful of stat() calls). Always exit 0
# — a receptor that can block session boot gets disarmed, and a disarmed
# receptor reports nothing forever.
# Kill switch: INJECTED_SURFACE_RECEPTOR_ENABLED=false

set -o pipefail
[[ "${INJECTED_SURFACE_RECEPTOR_ENABLED:-true}" == "false" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." 2>/dev/null && pwd)"
ATTEST="$REPO_ROOT/scripts/injected_surface_attest.py"

if [[ ! -f "$ATTEST" ]]; then
  echo "📏 injected-surface: receptor armed but $ATTEST is missing — nothing is measuring the context budget"
  exit 0
fi

# NOTE: no `timeout` wrapper — GNU timeout is not on stock macOS and is absent
# from a non-interactive shell's PATH even when Homebrew has it (cicatrix W107).
# Never `--strict` here: this receptor reports, it does not judge boot.
if ! OUT="$(/usr/bin/env python3 "$ATTEST" --repo-root "$REPO_ROOT" 2>&1)"; then
  echo "📏 injected-surface: receptor error — ${OUT:-no output}"
  exit 0
fi
echo "$OUT"
exit 0
