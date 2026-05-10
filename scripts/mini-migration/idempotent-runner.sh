#!/bin/bash
# scripts/mini-migration/idempotent-runner.sh <label> <inner-cmd...>
#
# Wrapper for cron jobs with non-idempotent side-effects (Brevo, social,
# Telegram broadcast, Canva). Generates an idempotency key per scheduled
# fire window, stores it in Redis with TTL, and skips execution if the key
# already exists (i.e., another instance — same machine or other — already
# took it).
#
# Window granularity:
#   - hourly job   => key = "<label>_<YYYY-mm-dd-HH>"
#   - daily job    => key = "<label>_<YYYY-mm-dd>"
#   - weekly job   => key = "<label>_<YYYY-Www>"
#   - monthly job  => key = "<label>_<YYYY-mm>"
#
# Detection of granularity is heuristic from label suffix (.daily/.hourly/
# .weekly/.monthly) — falls back to daily.
#
# Redis target: $REDIS_URL or default redis://127.0.0.1:6379. For
# cross-machine dedup, set REDIS_URL=redis://Nuzantara.local:6379 in the
# plist EnvironmentVariables (open question §9 of design — pending).
#
# Exit codes:
#   0 — inner command ran (or skipped because dup)
#   inner exit code — propagated from inner command
#   2 — Redis unreachable (FAIL-OPEN: runs the inner command, alerts Telegram)

set -u

LABEL="${1:-}"
shift || true

if [ -z "$LABEL" ] || [ "$#" -eq 0 ]; then
  echo "usage: $0 <label> <inner-cmd> [args...]" >&2
  exit 2
fi

# Determine window granularity from label suffix
case "$LABEL" in
  *.hourly|*.30min|*.10min|*.5min)  WINDOW_FMT='+%Y-%m-%d-%H' ;;
  *.weekly)                          WINDOW_FMT='+%G-W%V' ;;
  *.monthly|*.28d-check)             WINDOW_FMT='+%Y-%m' ;;
  *.daily|*.nightly|*)               WINDOW_FMT='+%Y-%m-%d' ;;
esac

WINDOW=$(date "$WINDOW_FMT")
KEY="idem:${LABEL}:${WINDOW}"

# TTL: 2x the window length (safety margin)
case "$LABEL" in
  *.hourly|*.30min|*.10min|*.5min) TTL=7200 ;;     # 2h
  *.weekly)                         TTL=1209600 ;; # 2 weeks
  *.monthly|*.28d-check)            TTL=5184000 ;; # 60 days
  *)                                TTL=172800 ;;  # 2d (daily)
esac

REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Try SET NX
SET_RESULT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
  SET "$KEY" "claimed_by_$(hostname)_$$_$(date +%s)" NX EX "$TTL" 2>&1)

REDIS_RC=$?

LOG_FILE="$HOME/logs/idempotent-runner.log"
mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$LABEL] $*" >> "$LOG_FILE"; }

if [ "$REDIS_RC" -ne 0 ]; then
  log "WARN: Redis unreachable ($REDIS_HOST:$REDIS_PORT) — FAIL-OPEN, running inner cmd anyway"
  # Telegram alert for ops
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a; source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true; set +a
  fi
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    curl -s --max-time 5 \
      "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_OWNER_CHAT_ID:-1125336968}" \
      -d "text=[idempotent-runner] Redis unreachable on $(hostname) for $LABEL — fail-open, running anyway" >/dev/null 2>&1 || true
  fi
  exec "$@"
fi

if [ "$SET_RESULT" = "OK" ]; then
  log "claimed key=$KEY ttl=${TTL}s — running inner cmd"
  exec "$@"
else
  log "skipped — key=$KEY already claimed (result: $SET_RESULT)"
  exit 0
fi
