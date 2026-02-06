#!/bin/bash
# Script per eseguire la migration su database PostgreSQL su Fly.io

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATION_FILE="$SCRIPT_DIR/001_add_performance_indexes.sql"

echo "🚀 Migration per Fly.io PostgreSQL"
echo "===================================="
echo ""

# Verifica che flyctl sia installato
if ! command -v flyctl &> /dev/null; then
    echo "❌ Errore: flyctl non trovato"
    echo "Installa flyctl: curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Verifica autenticazione flyctl
if ! flyctl auth whoami &> /dev/null; then
    echo "❌ Errore: Non autenticato su Fly.io"
    echo "Esegui: flyctl auth login"
    exit 1
fi

echo "✅ flyctl trovato e autenticato"
echo ""

# Cerca app PostgreSQL
DB_APP=$(flyctl list apps --json 2>/dev/null | grep -o '"Name": "[^"]*postgres[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$DB_APP" ]; then
    echo "⚠️  Nessuna app PostgreSQL trovata automaticamente"
    echo ""
    echo "App disponibili:"
    flyctl list apps | grep -E "(NAME|postgres)" || flyctl list apps | head -20
    echo ""
    read -p "Inserisci il nome dell'app PostgreSQL: " DB_APP
else
    echo "🗄️  Database trovato: $DB_APP"
    read -p "Conferma (o inserisci altro nome) [$DB_APP]: " USER_INPUT
    DB_APP=${USER_INPUT:-$DB_APP}
fi

echo ""
echo "📋 Dettagli migration:"
echo "   File: $MIGRATION_FILE"
echo "   Database App: $DB_APP"
echo ""
echo "⚠️  La migration creerà:"
echo "   - 8 indici di performance"
echo "   - 1 funzione di normalizzazione telefoni"
echo "   - 1 trigger automatico"
echo ""
read -p "Procedere? (y/N): " CONFIRM

if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "❌ Migration annullata"
    exit 0
fi

echo ""
echo "🔌 Apertura proxy verso il database..."
echo "   (Lascia questo terminale aperto)"
echo ""

# Ottieni la connection string
DB_URL=$(flyctl postgres connect -a "$DB_APP" --url 2>/dev/null | grep "postgres://" | head -1)

if [ -z "$DB_URL" ]; then
    echo "⚠️  Impossibile ottenere URL automaticamente"
    echo ""
    echo "Metodo alternativo:"
    echo "1. Apri un nuovo terminale"
    echo "2. Esegui: flyctl proxy 5433:5432 -a $DB_APP"
    echo "3. In questo terminale, esegui:"
    echo "   psql postgresql://user:pass@localhost:5433/db -f $MIGRATION_FILE"
    echo ""
    read -p "Premi INVIO quando il proxy è attivo..."
fi

# Esegui la migration
echo "🚀 Esecuzione migration..."
if [ -n "$DB_URL" ]; then
    psql "$DB_URL" -f "$MIGRATION_FILE"
else
    echo "❌ Impossibile connettersi al database"
    exit 1
fi

echo ""
echo "✅ Migration completata con successo!"
