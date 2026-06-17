#!/usr/bin/env bash
# intake_review_reader_liveness.sh — port-liveness guardian for the intake-review reader.
#
# INCIDENT 2026-06-17: the reader (uvicorn on 127.0.0.1:18795, Pro-only) crash-looped
# SILENTLY with `ModuleNotFoundError: No module named 'fastapi'` (its venv lost the dep).
# Its LaunchAgent is `KeepAlive=true`, so launchd kept restarting it and `launchctl list`
# stayed "green" (a transient LastExitStatus=15 SIGTERM) while the PORT was dead and
# kita.balizero.com/review went down in prod. Nobody was paged — Zero noticed from the
# browser. This is superscar #2 "Esiste != Armato — the green lies; read the OUTPUT /
# heartbeat, not the exit code."
#
# WHY a dedicated probe and not the W84 launchd_liveness_detector.py:
#   The W84 detector reads launchctl exit-code vs LOG CONTENT (matching launch-failure
#   markers like "operation not permitted"). It is STRUCTURALLY blind to this reader's
#   failure: (1) the crash is a Python `ModuleNotFoundError`, not a launch-failure marker,
#   and chasing exception strings is a substring under-match trap (superscar #3); (2) with
#   KeepAlive=true the exit code oscillates and lies; (3) the REAL liveness signal for a web
#   reader is "does the port answer", which has no log representation at all. So we probe the
#   port directly: the heartbeat IS the HTTP response.
#
# Liveness rule: the reader is JWT-only, so EVERY path returns an HTTP status (401/404) when
# ALIVE. ANY HTTP response (any 3-digit code) = ALIVE. curl connection-refused / timeout /
# HTTP code 000 = DEAD. This correctly separates "process up but auth-gated" from "port dead".
#
# SEGNALATORE ONLY (superscar #2 antidote: it ALERTS, it does NOT auto-attuate). It does NOT
# restart/pip-install/kickstart — a sibling PR (fix/intake-reader-venv-deps-autoheal) owns the
# auto-heal. This guardian's job is to make a dead reader PAGE instead of hiding.
#
# Pro-only (the reader runs only on Pro — avoid active-active, superscar #10): the plist
# installs on Pro only, and this script no-ops gracefully if nothing is listening AND the
# reader plist is not present (so a stray run on Mini/M5 stays silent).
#
# Runs every 300s via launchd (StartInterval, NO KeepAlive — one-shot, superscar #7).
#
# Manual test:
#   bash scripts/intake_review_reader_liveness.sh           # probe :18795, alert if dead
#   PROBE_PORT=18799 FORCE_CHECK=1 bash scripts/intake_review_reader_liveness.sh   # prove alert fires on a dead port
#   bash scripts/intake_review_reader_liveness.sh --test    # send ONE test ping to confirm the alert path is armed
#
# Reference sibling: scripts/supervisor_liveness_watchdog.sh (same shape: StartInterval probe
# + canonical send_telegram). Reference scar: cicatrix superscar #2 (W81/W84), #7, #10.

set -u -o pipefail

# --- Config (env-overridable) ---
PROBE_HOST="${PROBE_HOST:-127.0.0.1}"
PROBE_PORT="${PROBE_PORT:-18795}"
READER_LABEL="${READER_LABEL:-com.nuzantara.intake-review-reader}"
STATE_FILE="${STATE_FILE:-$HOME/.agent/decisions/state/intake_review_reader_liveness.json}"
LOG_FILE="${LOG_FILE:-$HOME/logs/intake-review-reader-liveness.log}"
COOLDOWN_S="${COOLDOWN_S:-1800}"          # 30min between alerts (anti-storm)
CURL_TIMEOUT_S="${CURL_TIMEOUT_S:-5}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

now_ts() { date +%s; }
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >>"$LOG_FILE"; }

# --- Telegram helper (canonical pattern, identical to supervisor_liveness_watchdog.sh) ---
send_telegram() {
  local msg="$1"
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local TOKEN="${TELEGRAM_BOT_TOKEN:-${CELL_TELEGRAM_BOT_TOKEN:-}}"
  local CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ZERO_CHAT_ID:-1125336968}}"
  if [ -z "$TOKEN" ] || [ -z "$CHAT_ID" ]; then
    log "telegram: skipped (no token/chat_id available)"
    return 0
  fi
  curl -fsS --max-time "$CURL_TIMEOUT_S" -X POST \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT_ID}" \
    --data-urlencode "text=${msg}" \
    --data-urlencode "parse_mode=Markdown" \
    >/dev/null 2>&1 || log "telegram: send failed"
}

# --- State ---
read_last_action_ts() {
  if [ -f "$STATE_FILE" ]; then
    /usr/bin/jq -r '.last_action_ts // 0' "$STATE_FILE" 2>/dev/null || echo 0
  else
    echo 0
  fi
}
write_state() {
  local action="$1"; local code="$2"
  cat >"$STATE_FILE" <<EOF
{
  "last_action_ts": $(now_ts),
  "last_action": "$action",
  "last_http_code": "$code",
  "probe": "http://${PROBE_HOST}:${PROBE_PORT}/"
}
EOF
}

# --- Probe: print curl's %{http_code}. On connection-refused/timeout curl ALREADY
# prints 000 (and exits non-zero); we must NOT append our own fallback or we get
# "000000" (a real bug caught in test 2026-06-17). Swallow curl's exit with `|| true`
# so the printed code (000 or 1xx-5xx) is the sole signal; liveness is judged below
# by validating the code is a real HTTP status, not by string-comparing to "000".
probe_http_code() {
  curl -s -o /dev/null -w "%{http_code}" --max-time "$CURL_TIMEOUT_S" \
    "http://${PROBE_HOST}:${PROBE_PORT}/" 2>/dev/null || true
}

# --- --test: prove the alert path is armed (send ONE ping, no probe) ---
if [ "${1:-}" = "--test" ]; then
  log "--test: sending one armed-confirmation ping"
  send_telegram "🧪 intake-review reader liveness guardian ARMED (test ping — ignore). Probing http://${PROBE_HOST}:${PROBE_PORT}/ every 5min; pages on dead port."
  exit 0
fi

NOW=$(now_ts)

# Active-active guard (superscar #10): if the reader plist is NOT installed here AND
# nothing answers, this is not the reader's host — stay silent (no false page on Mini/M5).
PLIST_PRESENT=0
if [ -f "$HOME/Library/LaunchAgents/${READER_LABEL}.plist" ]; then PLIST_PRESENT=1; fi

CODE="$(probe_http_code)"
log "probe: http://${PROBE_HOST}:${PROBE_PORT}/ -> code=${CODE} plist_present=${PLIST_PRESENT}"

# ALIVE iff CODE is a single valid HTTP status (1xx-5xx). 401/404 count — the process
# is up and answering. Anything else (000 = connection refused/timeout, empty, or a
# doubled string) = DEAD. We validate the SHAPE, never string-compare to "000".
if [[ "$CODE" =~ ^[1-5][0-9][0-9]$ ]]; then
  log "OK: reader ALIVE (http ${CODE})"
  write_state "ok" "$CODE"
  exit 0
fi

# DEAD path (code=000 = connection refused / timeout).
# If the reader is not supposed to run here (no plist) and unless FORCE_CHECK=1, no-op.
if [ "$PLIST_PRESENT" != "1" ] && [ "${FORCE_CHECK:-0}" != "1" ]; then
  log "no-op: reader plist absent on this host and port dead — not the reader's host (no alert)"
  exit 0
fi

# Cooldown gate (anti-storm).
LAST_ACTION_TS=$(read_last_action_ts)
SINCE=$((NOW - LAST_ACTION_TS))
if [ "$SINCE" -lt "$COOLDOWN_S" ]; then
  log "WARN: reader DEAD (code=${CODE}) but cooldown active (${SINCE}s < ${COOLDOWN_S}s) — alert suppressed"
  exit 1
fi

log "ALERT: reader DEAD on port ${PROBE_PORT} (curl code=${CODE} = connection refused/timeout)"
ALERT_MSG="🚨 intake-review reader DOWN
Probe: \`http://${PROBE_HOST}:${PROBE_PORT}/\` → \`${CODE}\` (connection refused/timeout)
Effect: \`kita.balizero.com/review\` is DOWN.
Label: \`${READER_LABEL}\`
Check: \`tail ~/logs/intake-review-reader.log\` (likely venv dep / import crash under KeepAlive).
Guardian: segnalatore only (auto-heal handled separately)."

if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN=1 → would send: ${ALERT_MSG}"
  echo "$ALERT_MSG"
else
  send_telegram "$ALERT_MSG"
fi
write_state "alert_dead" "$CODE"
exit 1
