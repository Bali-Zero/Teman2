#!/bin/bash
# ZANTARA MEDIA - Database Migration Script
# Runs the PostgreSQL migration for content storage

set -e

echo "============================================"
echo "ZANTARA MEDIA - Database Migration"
echo "============================================"
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL environment variable not set"
    echo ""
    echo "Set it first:"
    echo "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    echo ""
    exit 1
fi

echo "Database: $DATABASE_URL"
echo ""

# Path to migration file
MIGRATION_FILE="../backend-rag/backend/db/migrations/017_zantara_media_content.sql"

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "❌ Migration file not found: $MIGRATION_FILE"
    exit 1
fi

echo "Migration file: $MIGRATION_FILE"
echo ""

# Ask for confirmation
read -p "Run migration? This will create tables in the database. (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo "Running migration..."
echo ""

# Run migration
psql "$DATABASE_URL" -f "$MIGRATION_FILE"

echo ""
echo "============================================"
echo "✓ Migration completed successfully!"
echo "============================================"
echo ""
echo "Tables created:"
echo "  • zantara_content"
echo "  • intel_signals"
echo "  • content_distributions"
echo "  • media_assets"
echo "  • content_versions"
echo "  • automation_runs"
echo "  • content_analytics_daily"
echo ""
echo "You can now start the application:"
echo "  cd backend"
echo "  uvicorn app.main:app --reload --port 8001"
echo ""
