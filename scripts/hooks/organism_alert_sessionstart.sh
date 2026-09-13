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
# DIET (2026-09-09): a Fable session measured ~49K tokens injected at
# SessionStart, and this hook was the single biggest offender — it used to
# print EVERY open finding, unbounded, including 27 WR2 organs stale BY
# DECISION (Zero ruled 2026-09-01: "WR2 runs only on command", memory
# decision_wr2_runs_only_on_command_2026_09_01) and every finding the session
# already saw last time. scripts/organism_heartbeat_brief.py now sits between
# the detector and this hook: it drops on-command organs
# (infra/organism/on_command_organs.json), shows only what is NEW or CHANGED
# since the last session on this machine, and hard-caps the block.
#
# Design constraints (so the receptor itself never becomes the blindness):
#   - FAST: hard 4s budget; never blocks session start.
#   - PATH-AWARE: works on M5 (balizero) and Pro/Mini (nuzantara).
#   - FAIL-OPEN: any error => no alert, exit 0 (a broken receptor must not
#     break sessions; it degrades to the pre-existing silence, never worse).
#   - SNAPSHOT: shows only currently-open alerts (cured organs vanish) — no
#     stale-alert graveyard (the failure mode that killed claude_tasks).
#   - CAPPED: the emitted block is bounded (SESSIONSTART_HOOK_MAX_BYTES,
#     default 1500) — same convention as the escalations/digest siblings.

set -o pipefail

# Resolve repo root from this script's location (path-aware, no hardcoded user).
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO_ROOT="$(cd "$HOOK_DIR/../.." && pwd)"
DETECTOR="$REPO_ROOT/scripts/organism_stale_detector.py"
BRIEF="$REPO_ROOT/scripts/organism_heartbeat_brief.py"

# Only meaningful on machines that actually run organs (have the sidecar dir).
SIDECAR_DIR="${ORGANISM_LAST_SEEN_DIR:-$HOME/.organism/last_seen}"
[[ -d "$SIDECAR_DIR" ]] || exit 0
[[ -f "$DETECTOR" ]] || exit 0
[[ -f "$BRIEF" ]] || exit 0

ON_COMMAND_FILE="${ORGANISM_ON_COMMAND_FILE:-$REPO_ROOT/infra/organism/on_command_organs.json}"
STATE_FILE="${ORGANISM_HEARTBEAT_STATE_FILE:-$HOME/.organism/session_brief/heartbeat_last_session.json}"
MAX_BYTES="${SESSIONSTART_HOOK_MAX_BYTES:-1500}"

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

# Run the detector (machine-readable). Fail-open on anything.
FINDINGS_JSON="$(ORGANISM_LAST_SEEN_DIR="$SIDECAR_DIR" \
    "${_TIMEOUT[@]}" "$PY" "$DETECTOR" --dir "$SIDECAR_DIR" --json 2>/dev/null)" || exit 0

# No alert if all organs breathing (empty list).
case "$FINDINGS_JSON" in
    ""|"[]") exit 0 ;;
esac

# Emit the snapshot file too (best-effort) so other readers can consume it.
ORGANISM_LAST_SEEN_DIR="$SIDECAR_DIR" \
    "${_TIMEOUT[@]}" "$PY" "$DETECTOR" --dir "$SIDECAR_DIR" --emit >/dev/null 2>&1 || true

# Filter to on-command-excluded + session-delta + capped brief. Fail-open.
OUT="$(printf '%s' "$FINDINGS_JSON" | "${_TIMEOUT[@]}" "$PY" "$BRIEF" \
    --on-command-file "$ON_COMMAND_FILE" \
    --state-file "$STATE_FILE" \
    --max-bytes "$MAX_BYTES" 2>/dev/null)" || exit 0

[[ -n "$OUT" ]] && echo "$OUT"

exit 0
