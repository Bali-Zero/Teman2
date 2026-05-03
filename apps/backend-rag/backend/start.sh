#!/bin/bash
# Fly.io startup script with proper PORT handling

echo "🔍 [start.sh] PORT environment variable: ${PORT:-'NOT SET'}"
echo "🔍 [start.sh] All env vars:"
env | grep -i port || echo "No PORT-related vars found"

PORT="${PORT:-8080}"
echo "✅ [start.sh] Using port: $PORT"
echo "🚀 [start.sh] Starting Uvicorn on 0.0.0.0:$PORT..."

uvicorn app.main_cloud:app --host 0.0.0.0 --port "$PORT"
