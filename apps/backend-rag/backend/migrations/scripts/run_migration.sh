#!/bin/bash
# Script per eseguire la migration dei database indexes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_FILE="$SCRIPT_DIR/001_add_performance_indexes.sql"

# Carica DATABASE_URL dal file .env se esiste
if [ -f "$SCRIPT_DIR/../../../.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/../../../.env" | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
    echo "❌ Errore: DATABASE_URL non trovato"
    echo "Assicurati di avere il file .env configurato correttamente"
    exit 1
fi

echo "🚀 Esecuzione migration: 001_add_performance_indexes.sql"
echo "📊 Questa migration creerà:"
echo "   - 8 nuovi indici di performance"
echo "   - 1 trigger per normalizzazione telefoni"
echo "   - 1 funzione di normalizzazione"
echo ""

# Esegui la migration
psql "$DATABASE_URL" -f "$MIGRATION_FILE"

echo ""
echo "✅ Migration completata con successo!"
echo ""
echo "📋 Indici creati:"
echo "   - idx_clients_email_lower"
echo "   - idx_clients_phone_normalized (con trigger)"
echo "   - idx_clients_birth_month"
echo "   - idx_clients_birth_day"
echo "   - idx_clients_birth_month_day"
echo "   - idx_documents_client_visibility_type_created"
echo "   - idx_documents_client_id"
echo "   - idx_collective_memories_promoted"
echo "   - idx_collective_memories_category"
