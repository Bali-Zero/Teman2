#!/bin/bash
# Claude Max Enrichment for Intel Articles
# Hourly batch processing of staged articles

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEL_DIR="$SCRIPT_DIR/.."
DATA_DIR="$INTEL_DIR/data"
STAGING_DIR="$DATA_DIR/staging/news"
ENRICHED_DIR="$DATA_DIR/enriched"
LOG_DIR="$DATA_DIR/logs"

mkdir -p "$ENRICHED_DIR" "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/enrichment_$TIMESTAMP.log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 Starting Claude Max enrichment batch"

# Find articles needing enrichment (not already enriched)
ARTICLES_TO_ENRICH=$(find "$STAGING_DIR" -name "*.json" -type f 2>/dev/null | while read -r article; do
    article_id=$(basename "$article" .json)
    if [ ! -f "$ENRICHED_DIR/${article_id}_enriched.json" ]; then
        echo "$article"
    fi
done)

ARTICLE_COUNT=$(echo "$ARTICLES_TO_ENRICH" | grep -c . || echo "0")

if [ "$ARTICLE_COUNT" -eq 0 ]; then
    log "✅ No articles to enrich"
    exit 0
fi

log "📊 Found $ARTICLE_COUNT articles to enrich"

# Enrich each article
ENRICHED_COUNT=0
ERROR_COUNT=0

echo "$ARTICLES_TO_ENRICH" | while read -r article; do
    if [ -z "$article" ]; then
        continue
    fi
    
    article_id=$(basename "$article" .json)
    log "🔄 Enriching: $article_id"
    
    # Extract article content
    title=$(jq -r '.title // "Untitled"' "$article")
    content=$(jq -r '.content // .body // ""' "$article")
    
    if [ -z "$content" ]; then
        log "⚠️  Skipping $article_id: no content"
        ((ERROR_COUNT++))
        continue
    fi
    
    # Call Claude Max via CLI (assuming claude CLI is available)
    enrichment_prompt="Analyze this news article and provide:
1. Executive Brief (max 200 words)
2. Key Facts (5 bullet points)
3. Actionable Insights (3 bullet points)
4. Legal/Regulatory Implications (if any)

Title: $title

Content: $content

Respond in JSON format with keys: executive_brief, key_facts, insights, legal_analysis"
    
    # Use claude CLI
    enriched_json=$(echo "$enrichment_prompt" | claude --model opus-4-6 --json 2>&1) || {
        log "❌ Error enriching $article_id: Claude CLI failed"
        ((ERROR_COUNT++))
        continue
    }
    
    # Merge original article with enrichment
    jq --argjson enrichment "$enriched_json" '. + {enrichment: $enrichment, enriched_at: now | todate}' "$article" > "$ENRICHED_DIR/${article_id}_enriched.json"
    
    log "✅ Enriched: $article_id"
    ((ENRICHED_COUNT++))
    
    # Rate limit: ~6 requests/min (Claude Max quota)
    sleep 10
done

log "🎉 Enrichment batch complete"
log "   ✅ Enriched: $ENRICHED_COUNT"
log "   ❌ Errors: $ERROR_COUNT"
log "📋 Log: $LOG_FILE"
