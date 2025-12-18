#!/bin/bash

# Script per eseguire test E2E dopo il deploy
# Usage: ./scripts/run-e2e-post-deploy.sh

set -e

echo "🚀 Running E2E tests after deployment..."
echo "=========================================="

# Verifica che l'app sia deployata e raggiungibile
APP_URL="${PLAYWRIGHT_BASE_URL:-https://nuzantara-mouth.fly.dev}"
echo "📡 Testing app at: $APP_URL"

# Attendi che l'app sia pronta
echo "⏳ Waiting for app to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
  if curl -f -s "$APP_URL" > /dev/null 2>&1; then
    echo "✅ App is ready!"
    break
  fi
  attempt=$((attempt + 1))
  echo "   Attempt $attempt/$max_attempts..."
  sleep 2
done

if [ $attempt -eq $max_attempts ]; then
  echo "❌ App is not responding after $max_attempts attempts"
  exit 1
fi

# Esegui i test E2E multi-turno
echo ""
echo "🧪 Running multi-turn conversation E2E tests..."
echo "================================================"

cd "$(dirname "$0")/.."

export PLAYWRIGHT_BASE_URL="$APP_URL"

npm run test:e2e -- e2e/chat/multi-turn-conversation.spec.ts --reporter=list

echo ""
echo "✅ E2E tests completed!"

