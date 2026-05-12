#!/usr/bin/env bash
# intel-lake-nb-pusher-cron.sh — Pro-local NB push (Tier 1.5, 2026-05-13)
#
# Closes the Intel Lake pipeline gap: Tier 1 router classifies items as
# nb-intel + sets routing_targets.nb_uuids but nothing reads it. This
# pusher takes those classifications and actually adds the items to the
# right NB-INTEL notebook(s) via `nlm source add`.
#
# Pattern follows A2 cron (intel-lake-router-cron.sh): zero backend
# imports, pure asyncpg + subprocess to nlm CLI, flock concurrency guard.
#
# Schedule: LaunchAgent com.balizero.intel-lake-nb-pusher.15min (900s)
# Logs:     ~/logs/intel-lake-nb-pusher.log + .metrics.json
# Migration: 171_intel_item_nb_pushes.sql (apps/backend-rag/.../migrations_v2/)

set -uo pipefail

LOG_FILE="${HOME}/logs/intel-lake-nb-pusher.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

# Defense-in-depth: never pay-per-token Anthropic
unset ANTHROPIC_API_KEY

SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a; source "$SECRETS_FILE"; set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR DATABASE_URL not set in ${SECRETS_FILE}"
    exit 2
fi

PY="${HOME}/.pyenv/versions/3.11.11/bin/python3"
SCRIPT="${HOME}/scripts/intel-lake-nb-pusher-standalone.py"

if [[ ! -x "$PY" ]]; then
    log "ERROR pyenv python missing: $PY"
    exit 2
fi
if [[ ! -f "$SCRIPT" ]]; then
    log "ERROR standalone script missing: $SCRIPT"
    exit 2
fi

# Concurrency guard via flock — NLM push can take 30-60s/item × 10 items
# = up to 10min wall time. LaunchAgent interval 900s leaves no overlap
# margin if a run is slow. flock -n exits immediately if held.
LOCK="/tmp/intel-lake-nb-pusher.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    log "WARN previous tick still running, skipping"
    exit 0
fi

START_EPOCH=$(date +%s)
log "tick start (script=$SCRIPT)"

OUT=$("$PY" "$SCRIPT" 2>&1)
EXIT=$?

END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))

log "exit=${EXIT} duration=${DURATION}s output:"
printf '%s\n' "$OUT" >> "$LOG_FILE"

exit "$EXIT"
