#!/bin/bash
# CRM KG garbage collector — daily 03:00 WITA
# Soft-deletes orphan nodes + hard-deletes old edges.
source "$HOME/.openclaw-cron-env" 2>/dev/null || true

LOG="$HOME/logs/cron-tmp/crm-kg-garbage-collect.log"
API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
API_KEY="${NUZANTARA_API_KEY:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== garbage-collect trigger ==="

if [ -z "$API_KEY" ]; then
    log "❌ NUZANTARA_API_KEY non impostata"
    exit 1
fi

HTTP_CODE=$(curl -s -o /tmp/crm_kg_gc.tmp -w "%{http_code}" --max-time 30 \
    -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
    "${API_URL}/api/admin/crm-kg/garbage-collect" 2>/dev/null) || HTTP_CODE="000"

BODY=$(cat /tmp/crm_kg_gc.tmp 2>/dev/null || echo "")

if [ "$HTTP_CODE" = "200" ]; then
    log "✅ garbage-collect OK: $BODY"
else
    log "⚠️ garbage-collect HTTP $HTTP_CODE: $BODY"
fi

log "=== End ==="
