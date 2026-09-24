#!/bin/bash
# nlm_watchdog_cron.sh — wrapper LaunchAgent per scripts/nlm_watchdog.py.
#
# Stessa forma di scripts/auth_sentinel_cron.sh (sibling M5, canon nel repo,
# live copy fuori da ~/Desktop — W84 TCC): vive in ~/.nuzantara-cron/, non nel
# checkout principale (sola lettura lì, nessun write).
#
# Blocking-loop NON necessario: cron puro → StartInterval, niente KeepAlive
# (scar #7 daemon-vs-cron). Un tick = i tre probe di nlm_watchdog.py (login Pro
# + cap notebook + freschezza inventario), che scrive da sé il proprio
# heartbeat ok/degraded — questo wrapper logga e, SOLO se python non è
# arrivato a scrivere nulla, riempie il vuoto (Gear-3 council finding: un
# wrapper che ingoia sempre l'exit code e non verifica MAI che un heartbeat
# sia stato davvero scritto lascia esattamente la classe di guasto silenzioso
# che questo organo esiste per eliminare).
set -uo pipefail

REPO="$HOME/nuzantara"
LOG_DIR="$HOME/.local/state/nlm-watchdog"
LOG="$LOG_DIR/run.log"
HEARTBEAT_DIR="$HOME/.organism/last_seen"
HEARTBEAT_FILE="$HEARTBEAT_DIR/nlm-watchdog.json"
KILL_FLAG="$HOME/.organism/kill/nlm_watchdog"
mkdir -p "$LOG_DIR" "$HEARTBEAT_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Atomic heartbeat write (tmp + mv, same filesystem) — a concurrent
# organism_digest.py read must never observe a partial write (same class of
# bug nlm_watchdog.py's OWN atomic write already guards against).
write_heartbeat_atomic() {
  local status="$1" detail="${2:-}"
  local tmp="$HEARTBEAT_FILE.tmp.$$"
  if [ -n "$detail" ]; then
    printf '{"organ":"nlm-watchdog","host":"%s","ts":"%s","status":"%s","note":"%s","last_error":"%s"}\n' \
      "$(hostname -s)" "$(ts)" "$status" "$detail" "$detail" > "$tmp" 2>/dev/null
  else
    printf '{"organ":"nlm-watchdog","host":"%s","ts":"%s","status":"%s"}\n' \
      "$(hostname -s)" "$(ts)" "$status" > "$tmp" 2>/dev/null
  fi
  mv -f "$tmp" "$HEARTBEAT_FILE" 2>/dev/null || true
}

# G5 gene — kill switch: honors BOTH NLM_WATCHDOG_ENABLED=false (kept for
# manual/interactive invocation and gene-conformance parity with the sibling
# organs) AND a flag file (Gear-3 council finding, kimi #4: launchd NEVER
# sources shell rc files and this plist carries no <EnvironmentVariables>, so
# the env var is ALWAYS unset under the one caller that matters — the exact
# same latent defect exists, uncured, in auth_sentinel_cron.sh's own
# AUTH_SENTINEL_ENABLED gate; found, not fixed there, out of scope for this
# PR). The flag file is the mechanism that actually works from launchd; the
# env var stays as a documented, testable fallback. Either path leaves a
# status=disabled heartbeat, never silence.
if [ "${NLM_WATCHDOG_ENABLED:-true}" = "false" ] || [ -e "$KILL_FLAG" ]; then
  write_heartbeat_atomic "disabled"
  echo "[$(ts)] kill switch active (env or $KILL_FLAG) → skip tick (heartbeat=disabled)" >> "$LOG"
  exit 0
fi

# PATH esteso: launchd non ha il PATH interattivo (verificato in prod su
# auth-sentinel 2026-07-12: senza questo, i CLI in ~/.local/bin sparivano).
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "[$(ts)] nlm-watchdog tick start" >> "$LOG"

if [ ! -f "$REPO/scripts/nlm_watchdog.py" ]; then
  echo "[$(ts)] FATAL: watchdog non trovato in $REPO/scripts/ (checkout spostato?)" >> "$LOG"
  write_heartbeat_atomic "degraded" "cron wrapper: nlm_watchdog.py not found at $REPO/scripts/"
  exit 1
fi

# Record the heartbeat's mtime BEFORE running python. nlm_watchdog.py writes
# its own (far more specific) heartbeat on every reachable path, including a
# crash it catches — the only way NO heartbeat lands is if python could not
# even get that far (missing interpreter, syntax error, OOM-killed before its
# first write). Comparing mtimes tells the two cases apart: if python DID
# write something, trust its content and never clobber it with a generic
# message; if it did not, fill the silence here.
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
  # python never reached its own write_heartbeat() call at all — the exact
  # "green cron, dead worker" shape (scar #2). Fill the gap.
  write_heartbeat_atomic "degraded" "cron wrapper: nlm_watchdog.py wrote no heartbeat (exit $RC)"
  echo "[$(ts)] nlm-watchdog tick end — NO HEARTBEAT WRITTEN by python (rc=$RC), wrapper filled it" >> "$LOG"
else
  echo "[$(ts)] nlm-watchdog tick end (rc=$RC)" >> "$LOG"
fi

# The wrapper's own exit code now reflects reality too (previously always 0)
# — launchd's own per-run exit-status accounting is a second, independent
# signal on top of the heartbeat, not a replacement for it.
exit "$RC"
