#!/bin/bash
# release_migrate.sh - Safe migration runner for Fly.io release_command
#
# This script runs migrations before the app starts.
# It handles errors gracefully to prevent deployment failures from blocking releases.
#
# Usage: Called automatically by Fly.io via release_command in fly.toml
#
# Exit codes:
#   0 - Success (migrations applied or no pending migrations)
#   0 - Database unreachable (allows deployment to continue - app will retry on startup)
#   1 - Migration failure (blocks deployment to prevent schema drift)

set -e

echo "=========================================="
echo "NUZANTARA RAG - Release Migration Script"
echo "=========================================="

cd /app/backend

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "WARNING: DATABASE_URL not set, skipping migrations"
    echo "App will attempt migrations on startup"
    exit 0
fi

# Run migrations with timeout (2 minutes max)
echo "Running database migrations..."
timeout 120 python -m db.migrate apply-all

MIGRATION_EXIT_CODE=$?

if [ $MIGRATION_EXIT_CODE -eq 0 ]; then
    echo "Migrations completed successfully"
    exit 0
elif [ $MIGRATION_EXIT_CODE -eq 124 ]; then
    # Timeout - allow deployment but log warning
    echo "WARNING: Migration timed out after 120s"
    echo "App will retry migrations on startup"
    exit 0
else
    echo "ERROR: Migration failed with exit code $MIGRATION_EXIT_CODE"
    echo "Blocking deployment to prevent schema drift"
    exit 1
fi
