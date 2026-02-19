#!/bin/bash
# Sync PostgreSQL from Fly.io production to localhost
# Usage: ./sync_postgres_from_production.sh [--tables-only]

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_DIR="/tmp/nuzantara_dumps"
LOG_FILE="$DUMP_DIR/sync_log_$TIMESTAMP.txt"
DUMP_FILE="$DUMP_DIR/nuzantara_rag_dump_$TIMESTAMP.sql"

# Production connection (via fly proxy)
PROD_HOST="localhost"
PROD_PORT="15432"
PROD_DB="nuzantara_rag"
PROD_USER="backend_rag_v2"
PROD_PASS="2zEjit43IF6gNUV"
PROD_CONN="postgresql://$PROD_USER:$PROD_PASS@$PROD_HOST:$PROD_PORT/$PROD_DB?sslmode=disable"

# Local connection
LOCAL_HOST="localhost"
LOCAL_PORT="5432"
LOCAL_DB="nuzantara_dev"
LOCAL_USER="postgres"
LOCAL_CONN="postgresql://$LOCAL_USER@$LOCAL_HOST:$LOCAL_PORT/$LOCAL_DB"

mkdir -p "$DUMP_DIR"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if fly proxy is running
check_proxy() {
    if ! nc -z $PROD_HOST $PROD_PORT 2>/dev/null; then
        log "❌ Fly proxy non attivo su $PROD_HOST:$PROD_PORT"
        log "Avvia con: cd ~/Projects/nuzantara && fly proxy 15432:5432 -a nuzantara-postgres &"
        exit 1
    fi
    log "✅ Fly proxy attivo"
}

# Compare record counts before sync
compare_counts() {
    log "📊 Confronto record counts..."
    
    PROD_COUNTS=$(psql "$PROD_CONN" -t -c "
        SELECT 
            (SELECT COUNT(*) FROM parent_documents) as parent_docs,
            (SELECT COUNT(*) FROM kbli_documents) as kbli_docs,
            (SELECT COUNT(*) FROM kg_nodes) as kg_nodes,
            (SELECT COUNT(*) FROM kg_edges) as kg_edges,
            (SELECT COUNT(*) FROM golden_routes) as golden_routes,
            (SELECT COUNT(*) FROM clients) as clients,
            (SELECT COUNT(*) FROM practices) as practices;
    ")
    
    LOCAL_COUNTS=$(psql "$LOCAL_CONN" -t -c "
        SELECT 
            (SELECT COUNT(*) FROM parent_documents) as parent_docs,
            (SELECT COUNT(*) FROM kbli_documents) as kbli_docs,
            (SELECT COUNT(*) FROM kg_nodes) as kg_nodes,
            (SELECT COUNT(*) FROM kg_edges) as kg_edges,
            (SELECT COUNT(*) FROM golden_routes) as golden_routes,
            (SELECT COUNT(*) FROM clients) as clients,
            (SELECT COUNT(*) FROM practices) as practices;
    " 2>/dev/null || echo "0 | 0 | 0 | 0 | 0 | 0 | 0")
    
    log "Production: $PROD_COUNTS"
    log "Local:      $LOCAL_COUNTS"
}

# Dump production database
dump_production() {
    log "📥 Dump production database..."
    pg_dump "$PROD_CONN" \
        --no-owner \
        --no-privileges \
        --clean \
        --if-exists \
        -f "$DUMP_FILE" 2>&1 | tee -a "$LOG_FILE"
    
    DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
    log "✅ Dump completato: $DUMP_FILE ($DUMP_SIZE)"
}

# Import to local
import_local() {
    log "📤 Import in locale..."
    
    if [ "$1" == "--tables-only" ]; then
        log "⚠️  Solo dati (tables only), schema esistente preservato"
        psql "$LOCAL_CONN" -f "$DUMP_FILE" 2>&1 | tail -20 | tee -a "$LOG_FILE"
    else
        log "🔄 Drop + ricreazione database"
        psql "postgresql://$LOCAL_USER@$LOCAL_HOST:$LOCAL_PORT/postgres" -c "DROP DATABASE IF EXISTS $LOCAL_DB;" 2>&1 | tee -a "$LOG_FILE"
        psql "postgresql://$LOCAL_USER@$LOCAL_HOST:$LOCAL_PORT/postgres" -c "CREATE DATABASE $LOCAL_DB OWNER antonellosiano;" 2>&1 | tee -a "$LOG_FILE"
        psql "$LOCAL_CONN" -f "$DUMP_FILE" 2>&1 | tail -20 | tee -a "$LOG_FILE"
    fi
    
    log "✅ Import completato"
}

# Cleanup old dumps (keep last 5)
cleanup_dumps() {
    log "🧹 Cleanup vecchi dump..."
    cd "$DUMP_DIR"
    ls -t nuzantara_rag_dump_*.sql 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t sync_log_*.txt 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    log "✅ Cleanup completato"
}

# Main
main() {
    log "🚀 Avvio sync PostgreSQL production → locale"
    
    check_proxy
    compare_counts
    dump_production
    import_local "$1"
    compare_counts
    cleanup_dumps
    
    log "🎉 Sync completato con successo!"
    log "📋 Log: $LOG_FILE"
}

main "$@"
