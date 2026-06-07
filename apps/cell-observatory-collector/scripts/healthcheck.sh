#!/usr/bin/env bash
set -euo pipefail

set -a
source ~/.nuzantara-secrets.env
set +a

URL="http://127.0.0.1:${OBSERVATORY_API_PORT:-17891}/api/observatory/health"
KEY="${OBSERVATORY_API_KEY:-}"
HEARTBEAT_LIB="${ORGANISM_HEARTBEAT_LIB:-${HOME}/Desktop/nuzantara/scripts/lib/heartbeat.sh}"
[[ -f "$HEARTBEAT_LIB" ]] && source "$HEARTBEAT_LIB" || true

ORGANISM_HB_STATUS="starting"
ORGANISM_HB_NOTE="cell observatory selfcheck start"

organism_hb_set() {
    ORGANISM_HB_STATUS="$1"
    ORGANISM_HB_NOTE="${2:-}"
}

organism_hb_finalize() {
    local rc="${1:-0}"
    if [ "$rc" -eq 0 ]; then
        if [ "$ORGANISM_HB_STATUS" = "starting" ]; then
            organism_hb_set ok "completed"
        fi
    elif [ "$ORGANISM_HB_STATUS" = "starting" ] || [ "$ORGANISM_HB_STATUS" = "ok" ]; then
        organism_hb_set error "rc=${rc}"
    fi
    if declare -F organism_heartbeat >/dev/null 2>&1; then
        organism_heartbeat "cell.observatory_selfcheck" "$ORGANISM_HB_STATUS" "$ORGANISM_HB_NOTE"
    fi
}

trap 'rc=$?; organism_hb_finalize "$rc"' EXIT

resp=$(curl -fsS -m 5 -H "X-Observatory-Key: $KEY" "$URL" || echo "FAIL")

if [ "$resp" = "FAIL" ]; then
    echo "[$(date -u +%FT%TZ)] CRITICAL: cell-observatory unreachable" >&2
    organism_hb_set error "unreachable"
    exit 1
fi

echo "[$(date -u +%FT%TZ)] OK: $resp"
organism_hb_set ok "healthy"
