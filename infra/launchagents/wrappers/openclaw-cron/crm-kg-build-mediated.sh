#!/bin/bash
# CRM KG Tier-B mediated edges builder — every 6h
# Calls Fly.io endpoint, returns immediately (background task on api side).
source "$HOME/.openclaw-cron-env" 2>/dev/null || true

LOG="$HOME/logs/cron-tmp/crm-kg-build-mediated.log"
API_URL="${API_URL:-https://nuzantara-rag.fly.dev}"
API_KEY="${NUZANTARA_API_KEY:-}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

log "=== build-mediated trigger ==="

if [ -z "$API_KEY" ]; then
    log "❌ NUZANTARA_API_KEY non impostata"
    exit 1
fi

HTTP_CODE=$(curl -s -o /tmp/crm_kg_mediated.tmp -w "%{http_code}" --max-time 30 \
    -X POST -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
    "${API_URL}/api/admin/crm-kg/build-mediated" 2>/dev/null) || HTTP_CODE="000"

BODY=$(cat /tmp/crm_kg_mediated.tmp 2>/dev/null || echo "")

if [ "$HTTP_CODE" = "200" ]; then
    log "✅ build-mediated OK: $BODY"
else
    log "⚠️ build-mediated HTTP $HTTP_CODE: $BODY"
fi

log "=== End ==="
