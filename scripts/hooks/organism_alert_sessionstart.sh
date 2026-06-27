#!/usr/bin/env bash
# organism_alert_sessionstart.sh — the RECEPTOR (SessionStart hook).
#
# Ends the 28-day blindness (2026-06-28): core organs ran green while their
# heartbeat froze, and NO session ever saw it because no hook read any alert
# channel (CLAUDE.md §14 said "check escalations" but nothing enforced it —
# documentation is not a receptor; a hook is. CLAUDE.md §7).
#
# Wired into ~/.claude/settings.json under hooks.SessionStart. On every session
# start it runs the stale-organ detector and, if any organ has stopped breathing,
# injects an alert into the session's context as hookSpecificOutput.additionalContext
# so the brain-session (me) SEES it — the alert reaches the organism, not a human
# on Telegram who won't look.
#
# Design constraints (so the receptor itself never becomes the blindness):
#   - FAST: hard 4s budget; never blocks session start.
#   - PATH-AWARE: works on M5 (balizero) and Pro/Mini (nuzantara).
#   - FAIL-OPEN: any error => no alert, exit 0 (a broken receptor must not
#     break sessions; it degrades to the pre-existing silence, never worse).
#   - SNAPSHOT: shows only currently-open alerts (cured organs vanish) — no
#     stale-alert graveyard (the failure mode that killed claude_tasks).

set -o pipefail

# Resolve repo root from this script's location (path-aware, no hardcoded user).
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"
DETECTOR="$REPO_ROOT/scripts/organism_stale_detector.py"

# Only meaningful on machines that actually run organs (have the sidecar dir).
SIDECAR_DIR="${ORGANISM_LAST_SEEN_DIR:-$HOME/.organism/last_seen}"
[[ -d "$SIDECAR_DIR" ]] || exit 0
[[ -f "$DETECTOR" ]] || exit 0

# Pick a python that exists (prefer repo venv, fall back to system).
PY=""
for cand in \
    "$REPO_ROOT/apps/backend-rag/.venv/bin/python" \
    "$(command -v python3 2>/dev/null)"; do
    [[ -x "$cand" ]] && { PY="$cand"; break; }
done
[[ -n "$PY" ]] || exit 0

# Portable time budget: GNU `timeout`/`gtimeout` if present (Linux/brew), else
# run directly (macOS ships neither). The detector is <0.1s so this is a belt,
# not a requirement.
_TIMEOUT=()
if command -v timeout >/dev/null 2>&1; then _TIMEOUT=(timeout 4)
elif command -v gtimeout >/dev/null 2>&1; then _TIMEOUT=(gtimeout 4); fi

# Run the detector (human report). Fail-open on anything.
REPORT="$(ORGANISM_LAST_SEEN_DIR="$SIDECAR_DIR" \
    "${_TIMEOUT[@]}" "$PY" "$DETECTOR" --dir "$SIDECAR_DIR" 2>/dev/null)" || exit 0

# No alert if all organs breathing.
case "$REPORT" in
    ""|*"all organs breathing"*) exit 0 ;;
esac

# Emit the snapshot file too (best-effort) so other readers can consume it.
ORGANISM_LAST_SEEN_DIR="$SIDECAR_DIR" \
    "${_TIMEOUT[@]}" "$PY" "$DETECTOR" --dir "$SIDECAR_DIR" --emit >/dev/null 2>&1 || true

# Inject into session context. Build JSON safely with python (no manual escaping).
"$PY" - "$REPORT" <<'PYEOF' 2>/dev/null || exit 0
import json, sys
report = sys.argv[1] if len(sys.argv) > 1 else ""
ctx = (
    "🫀 ORGANISM HEARTBEAT ALERT (injected by SessionStart receptor)\n"
    + report
    + "\n\nThese organs run green in launchd but their heartbeat sidecar is "
      "frozen — green (exit 0) != working (heartbeat written). Restart is NOT "
      "the cure (W2 disarmed): the heartbeat CHANNEL is dead. Investigate the "
      "writer/bridge. See research/operations/2026-06-28-heartbeat-channel-dead-core-organs.md"
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": ctx,
    }
}))
PYEOF

exit 0
