#!/bin/bash
# Helper script to run flyctl for mouth (frontend)
# Usage: ./scripts/fly-frontend.sh [command] [args...]

cd "$(dirname "$0")/../apps/mouth" || exit
echo "👄 Running flyctl in apps/mouth context..."
flyctl "$@"
