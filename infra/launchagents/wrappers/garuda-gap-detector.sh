#!/bin/zsh
# garuda-gap-detector.sh — Gap detector: Neo4j → nexus:gaps
# LaunchAgent: com.garuda.gap-detector.twice-daily (07:00 + 18:00 WITA)
set -uo pipefail

NEXUS_DIR="/Users/nuzantara/Desktop/OSINT-Nexus"
VENV_PY="${NEXUS_DIR}/.venv/bin/python"
LOG="/Users/nuzantara/logs/garuda-gap-detector.log"
export NEXUS_GAP_DEDUPE_SECONDS="${NEXUS_GAP_DEDUPE_SECONDS:-21600}"

echo "" >> "$LOG"
echo "=== Gap Detector — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

if [ ! -x "$VENV_PY" ]; then
    echo "[gap-detector] FATAL: Nexus venv python not found" >> "$LOG"
    exit 2
fi

# Redis on this host requires AUTH. Give redis-cli the credential via
# REDISCLI_AUTH (which it reads natively) rather than `-a`, so the secret never
# lands in argv / `ps`. Extracted in a SUBSHELL so nothing else from the secrets
# file leaks into this job's environment.
if [[ -z "${REDISCLI_AUTH:-}" && -f "$HOME/.nuzantara-secrets.env" ]]; then
    _redis_pw="$(set -a; source "$HOME/.nuzantara-secrets.env" >/dev/null 2>&1; printf '%s' "${REDIS_PASSWORD:-}")"
    if [[ -n "$_redis_pw" ]]; then
        export REDISCLI_AUTH="$_redis_pw"
    fi
    unset _redis_pw
fi

# Grade the REPLY, not the exit code (scar W104): redis-cli EXITS 0 even when
# the server refuses the command, answering `NOAUTH Authentication required.`
# on stdout — so `if ! redis-cli ping` passed unauthenticated and this gate was
# decorative.
if [ "$(redis-cli ping 2>/dev/null)" != "PONG" ]; then
    echo "[gap-detector] FATAL: Redis unreachable or refusing (no PONG)" >> "$LOG"
    exit 3
fi

if ! /usr/bin/nc -z localhost 17687 2>/dev/null; then
    echo "[gap-detector] FATAL: Neo4j unreachable on port 17687" >> "$LOG"
    exit 4
fi

cd "$NEXUS_DIR"
"$VENV_PY" -m bridge.gap_detector >> "$LOG" 2>&1

EXIT_CODE=$?
echo "[$(date '+%H:%M:%S')] Gap detector exit=$EXIT_CODE" >> "$LOG"
exit $EXIT_CODE
