#!/bin/bash
# nlm_watchdog_cron.sh — LaunchAgent wrapper for scripts/nlm_watchdog.py.
#
# Installed copy lives in ~/.nuzantara-cron/ (W84 TCC), like auth_sentinel_cron.sh.
# One-shot per tick: the plist uses StartInterval, no KeepAlive (scar #7).
# nlm_watchdog.py writes its own heartbeat; this wrapper writes one only when
# python did not. Exit: 0 when the kill switch is on; otherwise python's exit code
# (1 if the script is missing), forced to 1 when no heartbeat could be written.
set -uo pipefail

REPO="$HOME/nuzantara"
LOG_DIR="$HOME/.local/state/nlm-watchdog"
LOG="$LOG_DIR/run.log"
HEARTBEAT_DIR="$HOME/.organism/last_seen"
HEARTBEAT_FILE="$HEARTBEAT_DIR/nlm-watchdog.json"
KILL_FLAG="$HOME/.organism/kill/nlm_watchdog"
mkdir -p "$LOG_DIR" "$HEARTBEAT_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Set to 1 when write_heartbeat_atomic's `mv` fails: no fresh heartbeat is on
# disk, so every exit below returns non-zero.
HB_WRITE_FAILED=0

# Atomic heartbeat write (tmp + mv in the same directory).
write_heartbeat_atomic() {
  local status="$1" detail="${2:-}"
  local tmp="$HEARTBEAT_FILE.tmp.$$"
  # JSON-escape backslash and double quote.
  detail="$(printf '%s' "$detail" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  if [ -n "$detail" ]; then
    printf '{"organ":"nlm-watchdog","host":"%s","ts":"%s","status":"%s","note":"%s","last_error":"%s"}\n' \
      "$(hostname -s)" "$(ts)" "$status" "$detail" "$detail" > "$tmp" 2>/dev/null
  else
    printf '{"organ":"nlm-watchdog","host":"%s","ts":"%s","status":"%s"}\n' \
      "$(hostname -s)" "$(ts)" "$status" > "$tmp" 2>/dev/null
  fi
  if ! mv -f "$tmp" "$HEARTBEAT_FILE" 2>/dev/null; then
    echo "[$(ts)] FATAL: write_heartbeat_atomic could not install $tmp -> $HEARTBEAT_FILE — no fresh heartbeat on disk" >> "$LOG"
    rm -f "$tmp" 2>/dev/null
    HB_WRITE_FAILED=1
    return 1
  fi
  return 0
}

# G5 gene — kill switch: NLM_WATCHDOG_ENABLED=false or the flag file. The plist
# sets no environment, so under launchd only the flag file applies. Either
# writes a status=disabled heartbeat.
if [ "${NLM_WATCHDOG_ENABLED:-true}" = "false" ] || [ -e "$KILL_FLAG" ]; then
  write_heartbeat_atomic "disabled"
  echo "[$(ts)] kill switch active (env or $KILL_FLAG) → skip tick (heartbeat=disabled)" >> "$LOG"
  [ "$HB_WRITE_FAILED" -eq 1 ] && exit 1
  exit 0
fi

# launchd does not provide the interactive PATH.
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "[$(ts)] nlm-watchdog tick start" >> "$LOG"

if [ ! -f "$REPO/scripts/nlm_watchdog.py" ]; then
  echo "[$(ts)] FATAL: nlm_watchdog.py not found in $REPO/scripts/" >> "$LOG"
  write_heartbeat_atomic "degraded" "cron wrapper: nlm_watchdog.py not found at $REPO/scripts/"
  exit 1
fi

# An unchanged heartbeat mtime means python wrote no heartbeat (not started,
# killed, or its own write failed): the wrapper writes a degraded one.
BEFORE_MTIME=""
if [ -f "$HEARTBEAT_FILE" ]; then
  BEFORE_MTIME="$(stat -f "%m" "$HEARTBEAT_FILE" 2>/dev/null || stat -c "%Y" "$HEARTBEAT_FILE" 2>/dev/null || echo "")"
fi

RC=0
python3 "$REPO/scripts/nlm_watchdog.py" >> "$LOG" 2>&1 || RC=$?

AFTER_MTIME=""
if [ -f "$HEARTBEAT_FILE" ]; then
  AFTER_MTIME="$(stat -f "%m" "$HEARTBEAT_FILE" 2>/dev/null || stat -c "%Y" "$HEARTBEAT_FILE" 2>/dev/null || echo "")"
fi

if [ "$BEFORE_MTIME" = "$AFTER_MTIME" ]; then
  # scar #2: a finished job that left no heartbeat.
  write_heartbeat_atomic "degraded" "cron wrapper: nlm_watchdog.py wrote no heartbeat (exit $RC)"
  echo "[$(ts)] nlm-watchdog tick end — NO HEARTBEAT WRITTEN by python (rc=$RC), wrapper filled it" >> "$LOG"
else
  echo "[$(ts)] nlm-watchdog tick end (rc=$RC)" >> "$LOG"
fi

# HB_WRITE_FAILED takes priority over python's RC.
if [ "$HB_WRITE_FAILED" -eq 1 ]; then
  exit 1
fi
exit "$RC"
