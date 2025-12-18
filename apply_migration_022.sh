#!/bin/bash
# Apply migration 022 to PostgreSQL
set -e

echo "====================================="
echo "Applying Migration 022: Dedup Constraints"
echo "====================================="

# Read migration file
MIGRATION_FILE="/Users/antonellosiano/Desktop/nuzantara/apps/backend-rag/backend/db/migrations/022_dedup_constraints.sql"

# Connect to Fly.io PostgreSQL via proxy
fly proxy 5433:5432 -a nuzantara-db &
PROXY_PID=$!

# Wait for proxy to start
sleep 3

# Apply migration
psql "postgresql://nuzantara:uLNT1jX9mKQKN1KzIYH2kQ@localhost:5433/nuzantara?sslmode=disable" -f "$MIGRATION_FILE"

echo ""
echo "✅ Migration 022 applied successfully!"
echo ""

# Verify new columns
echo "📊 Verificando nuove colonne..."
psql "postgresql://nuzantara:uLNT1jX9mKQKN1KzIYH2kQ@localhost:5433/nuzantara?sslmode=disable" -c "\d parent_documents"

# Kill proxy
kill $PROXY_PID

echo ""
echo "✅ DONE"
