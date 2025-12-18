#!/bin/bash
# Helper script to run flyctl for backend-rag
# Usage: ./scripts/fly-backend.sh [command] [args...]

cd "$(dirname "$0")/../apps/backend-rag" || exit
echo "🚀 Running flyctl in apps/backend-rag context..."
flyctl "$@"
