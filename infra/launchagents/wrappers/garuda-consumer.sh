#!/bin/zsh
# garuda-consumer.sh — Bridge consumer: garuda:raw → Neo4j
# LaunchAgent: com.garuda.consumer.daily (06:15 WITA)
# Uses Nexus venv (has neo4j 6.1) via adhoc-signed python (TCC bypass)
set -uo pipefail

NEXUS_DIR="/Users/nuzantara/Desktop/OSINT-Nexus"
VENV_PY="${NEXUS_DIR}/.venv/bin/python"
LOG="/Users/nuzantara/logs/garuda-consumer.log"

echo "" >> "$LOG"
echo "=== Garuda Consumer (Neo4j Bridge) — $(date '+%Y-%m-%d %H:%M:%S %Z') ===" >> "$LOG"

# Nexus venv python is adhoc-signed → can read ~/Desktop/ under launchd
if [ ! -x "$VENV_PY" ]; then
    echo "[garuda-consumer] FATAL: Nexus venv python not found at $VENV_PY" >> "$LOG"
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

# Check Redis reachable — grade the REPLY, not the exit code (scar W104):
# redis-cli EXITS 0 even when the server refuses the command, answering
# `NOAUTH Authentication required.` on stdout. `if ! redis-cli ping` therefore
# passed unauthenticated, making this gate decorative.
if [ "$(redis-cli ping 2>/dev/null)" != "PONG" ]; then
    echo "[garuda-consumer] FATAL: Redis unreachable or refusing (no PONG)" >> "$LOG"
    exit 3
fi

# Check Neo4j reachable (bolt port)
if ! /usr/bin/nc -z localhost 17687 2>/dev/null; then
    echo "[garuda-consumer] FATAL: Neo4j unreachable on port 17687" >> "$LOG"
    exit 4
fi

# Run bridge consumer from Nexus dir (one-shot: reads new entries)
cd "$NEXUS_DIR"
"$VENV_PY" -m bridge.consumer >> "$LOG" 2>&1

EXIT_CODE=$?
echo "[$(date '+%H:%M:%S')] Consumer exit=$EXIT_CODE" >> "$LOG"
exit $EXIT_CODE
