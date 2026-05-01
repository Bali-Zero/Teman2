#!/usr/bin/env bash
set -euo pipefail

set -a
source ~/.nuzantara-secrets.env
set +a

URL="http://127.0.0.1:${OBSERVATORY_API_PORT:-17891}/api/observatory/health"
KEY="${OBSERVATORY_API_KEY:-}"

resp=$(curl -fsS -m 5 -H "X-Observatory-Key: $KEY" "$URL" || echo "FAIL")

if [ "$resp" = "FAIL" ]; then
    echo "[$(date -u +%FT%TZ)] CRITICAL: cell-observatory unreachable" >&2
    exit 1
fi

echo "[$(date -u +%FT%TZ)] OK: $resp"
