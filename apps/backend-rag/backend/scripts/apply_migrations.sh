#!/bin/bash
# Apply database migrations before deployment
# This script is called automatically during Fly.io deployment

set -e

echo "🔄 Applying database migrations..."

# Change to backend directory
cd "$(dirname "$0")/.." || exit 1

# Apply all pending migrations
python -m db.migrate apply-all

if [ $? -eq 0 ]; then
    echo "✅ Migrations applied successfully"
    exit 0
else
    echo "❌ Migration failed"
    exit 1
fi


















