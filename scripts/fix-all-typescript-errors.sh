#!/bin/bash
# Script per correggere tutti gli errori TypeScript logger in batch

set -e

echo "🔧 Correzione batch errori TypeScript logger..."
echo ""

# Pattern per logger.error con oggetto
find apps/backend-ts/src -name "*.ts" -type f -exec sed -i '' \
  -e 's/logger\.error(\([^,]*\), { error: error\.message });/logger.error(\1, error instanceof Error ? error : undefined, { error: String(error) });/g' \
  -e 's/logger\.error(\([^,]*\), { error });/logger.error(\1, error instanceof Error ? error : undefined, { error: String(error) });/g' \
  -e 's/logger\.error(\([^,]*\), error);/logger.error(\1, error instanceof Error ? error : undefined, { error: String(error) });/g' \
  {} \;

# Pattern per logger.warn/info/debug con oggetto error
find apps/backend-ts/src -name "*.ts" -type f -exec sed -i '' \
  -e 's/logger\.warn(\([^,]*\), { error: error\.message });/logger.warn(\1, { error: String(error) });/g' \
  -e 's/logger\.warn(\([^,]*\), error);/logger.warn(\1, { error: String(error) });/g' \
  -e 's/logger\.info(\([^,]*\), { error: error\.message });/logger.info(\1, { error: String(error) });/g' \
  -e 's/logger\.info(\([^,]*\), error);/logger.info(\1, { error: String(error) });/g' \
  -e 's/logger\.debug(\([^,]*\), error);/logger.debug(\1, { error: String(error) });/g' \
  {} \;

echo "✅ Correzione completata!"
echo "Esegui: npm run typecheck per verificare"
