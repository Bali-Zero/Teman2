#!/bin/bash
set -e

# ==============================================================================
# NUZANTARA DATABASE BACKUP TOOL
# ==============================================================================
# Uso:
#   ./scripts/db_backup.sh [full|schema] [env]
#
# Esempi:
#   ./scripts/db_backup.sh           # Backup completo locale (default)
#   ./scripts/db_backup.sh schema    # Solo schema locale
#   ./scripts/db_backup.sh full prod # (Futuro) Backup produzione Fly.io
# ==============================================================================

TYPE=${1:-full}
ENV=${2:-local}
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="./backend/data/backups"
CONTAINER_NAME="nuzantara-postgres"
DB_USER="postgres"
DB_NAME="nuzantara"

# Colori per output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Avvio procedura backup database ($ENV | $TYPE)...${NC}"

# Assicurati che la directory esista
mkdir -p "$BACKUP_DIR"

if [ "$ENV" == "local" ]; then
    # Verifica che il container sia attivo
    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}❌ Errore: Il container $CONTAINER_NAME non è attivo.${NC}"
        echo "Esegui 'docker compose up -d postgres' prima di lanciare il backup."
        exit 1
    fi

    if [ "$TYPE" == "schema" ]; then
        FILENAME="schema_dump_${TIMESTAMP}.sql"
        echo -e "📦 Estrazione SOLO SCHEMA in corso..."
        docker exec -t "$CONTAINER_NAME" pg_dump -U "$DB_USER" --schema-only --no-owner --no-privileges "$DB_NAME" > "$BACKUP_DIR/$FILENAME"
    else
        FILENAME="full_dump_${TIMESTAMP}.sql"
        echo -e "📦 Estrazione COMPLETA (Dati + Schema) in corso..."
        docker exec -t "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/$FILENAME"
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Backup completato con successo!${NC}"
        echo -e "📁 File salvato in: ${BACKUP_DIR}/$FILENAME"
        
        # Statistiche file
        SIZE=$(ls -lh "$BACKUP_DIR/$FILENAME" | awk '{print $5}')
        echo -e "📊 Dimensione: $SIZE"
    else
        echo -e "${RED}❌ Errore durante il backup.${NC}"
        exit 1
    fi

elif [ "$ENV" == "prod" ]; then
    echo -e "${YELLOW}⚠️ Backup produzione (Fly.io) non ancora implementato completamente in questo script.${NC}"
    echo "Usa: fly postgres connect -a <app-db-name> e pg_dump manualmente per ora."
    exit 1
else
    echo -e "${RED}❌ Ambiente sconosciuto: $ENV${NC}"
    exit 1
fi
