#!/usr/bin/env bash
# intel-lake-router-cron.sh — Pro-local Tier 1 router (Opt A2, 2026-05-13)
#
# Why this exists: Fly secret DISABLE_BACKGROUND_WORKERS=1 prevents the
# EventBus listener (and therefore the router subscriber) from running on
# the rag process. The router *code* is deployed (Fly v3192) but never
# fires. This wrapper runs a standalone classifier from Pro every 5 min.
#
# A2 differs from the previous (broken) A1: it calls
# scripts/intel-lake-router-cron-standalone.py — a pure asyncpg+re script
# with ZERO backend imports. This avoids the Pydantic Settings() validation
# that blocked A1 (Settings requires JWT_SECRET_KEY+API_KEYS at correct
# length; placeholder env vars failed validation).
#
# Schedule: LaunchAgent com.balizero.intel-lake-router.5min
# Logs:     ~/logs/intel-lake-router-cron.log + .state.json (Python-managed)
# Alert:    Telegram if 3+ failures in 30 min sliding window (in Python)

set -uo pipefail

LOG_FILE="${HOME}/logs/intel-lake-router-cron.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

# Defense-in-depth: never pay-per-token Anthropic
unset ANTHROPIC_API_KEY

# Load secrets (DATABASE_URL for PG, TELEGRAM_* for alerts)
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a; source "$SECRETS_FILE"; set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    log "ERROR DATABASE_URL not set in ${SECRETS_FILE}"
    exit 2
fi

# The standalone Python script does its own flycast→localhost:15432 rewrite,
# so we don't need to munge DATABASE_URL here. Pass through.

# Pyenv 3.11.11 has asyncpg installed (the same interpreter used by
# regulatory-watcher-run.sh for eventbus/intel_lake_outbox imports).
PY="${HOME}/.pyenv/versions/3.11.11/bin/python3"
SCRIPT="${HOME}/scripts/intel-lake-router-cron-standalone.py"

if [[ ! -x "$PY" ]]; then
    log "ERROR pyenv python missing: $PY"
    exit 2
fi
if [[ ! -f "$SCRIPT" ]]; then
    log "ERROR standalone script missing: $SCRIPT"
    exit 2
fi

# Verify rules file exists before launching Python — fail fast with a clear
# message rather than letting the script SystemExit() inside asyncio.run().
RULES_FILE="${HOME}/scripts/intel-lake-routing-rules.json"
if [[ ! -f "$RULES_FILE" ]]; then
    log "ERROR rules file missing: $RULES_FILE"
    exit 2
fi

START_EPOCH=$(date +%s)
log "tick start (script=$SCRIPT rules=$RULES_FILE)"

# Concurrency guard: a single /tmp lockfile so a slow run never overlaps the
# next launchd fire. SKIP LOCKED in PG already protects correctness, but
# this avoids spawning two `python3` processes that would then contend for
# the same rows.
LOCK="/tmp/intel-lake-router-cron.lock"
exec 9>"$LOCK"
if ! flock -n 9; then
    log "WARN previous tick still running, skipping"
    exit 0
fi

OUT=$("$PY" "$SCRIPT" 2>&1)
EXIT=$?

END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))

log "exit=${EXIT} duration=${DURATION}s output:"
printf '%s\n' "$OUT" >> "$LOG_FILE"

exit "$EXIT"
