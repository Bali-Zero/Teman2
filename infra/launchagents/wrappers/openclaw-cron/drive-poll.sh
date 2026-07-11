#!/bin/bash
# Drive Changes Poll - Ogni 5 minuti
# Triggera il polling di Google Drive per nuovi file via API endpoint dedicato

source "$HOME/.openclaw-cron-env" 2>/dev/null || true

LOG="/tmp/openclaw-drive-poll.log"
API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
API_KEY="${NUZANTARA_API_KEY:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"
}

log "=== Drive Poll Start ==="

if [ -z "$API_KEY" ]; then
    log "❌ NUZANTARA_API_KEY non impostata"
    exit 1
fi

# Chiama direttamente il poll endpoint (sveglia il backend + esegue il poll)
HTTP_CODE=$(curl -s -o /tmp/drive_poll_body.tmp -w "%{http_code}" --max-time 120 \
    -X POST \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    "${API_URL}/api/admin/drive/poll" 2>/dev/null) || HTTP_CODE="000"
BODY=$(cat /tmp/drive_poll_body.tmp 2>/dev/null || echo "")

if [ "$HTTP_CODE" = "200" ]; then
    PROCESSED=$(echo "$BODY" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('processed',0))" 2>/dev/null || echo "?")
    log "✅ Drive poll OK: $PROCESSED new files processed"
elif [ "$HTTP_CODE" = "000" ]; then
    log "⚠️ Backend not responding (timeout/unreachable) — Fly may be sleeping"
else
    log "⚠️ Drive poll failed (HTTP $HTTP_CODE): $BODY"
fi

# Trunca log
if [ -f "$LOG" ] && [ $(stat -f%z "$LOG" 2>/dev/null || echo 0) -gt 1048576 ]; then
    tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

log "=== Drive Poll End ==="
