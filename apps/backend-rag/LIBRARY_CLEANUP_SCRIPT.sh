#!/bin/bash
# Library Cleanup Script - Safe Cleanup Only
# Data: 2026-01-16
# Spazio Liberabile: ~9.2 GB

set -e

echo "=== LIBRARY CLEANUP SCRIPT ==="
echo "Spazio Liberabile: ~9.2 GB"
echo ""

# 1. Cache Yarn (4.0 GB)
echo "1. Pulizia Cache Yarn..."
yarn cache clean
echo "   ✅ Completato"
echo ""

# 2. Docker non usato (4.5 GB)
echo "2. Pulizia Docker non usato..."
docker system prune -a --volumes -f
echo "   ✅ Completato"
echo ""

# 3. Cache pnpm (213 MB)
echo "3. Pulizia Cache pnpm..."
pnpm store prune 2>/dev/null || echo "   ⚠️  pnpm non disponibile"
echo "   ✅ Completato"
echo ""

# 4. Cache pip (135 MB)
echo "4. Pulizia Cache pip..."
pip cache purge 2>/dev/null || echo "   ⚠️  pip non disponibile"
echo "   ✅ Completato"
echo ""

# 5. Cache Playwright (233 MB)
echo "5. Pulizia Cache Playwright..."
rm -rf ~/Library/Caches/ms-playwright* 2>/dev/null
echo "   ✅ Completato"
echo ""

# 6. Cache Homebrew (73 MB)
echo "6. Pulizia Cache Homebrew..."
brew cleanup --prune=all 2>/dev/null || echo "   ⚠️  Homebrew non disponibile"
echo "   ✅ Completato"
echo ""

# 7. Logs (44 MB)
echo "7. Pulizia Logs..."
rm -rf ~/Library/Logs/*/* 2>/dev/null
echo "   ✅ Completato"
echo ""

echo "=== PULIZIA COMPLETATA ==="
echo "Spazio liberato: ~9.2 GB"
echo ""
echo "Per verificare lo spazio disponibile:"
echo "  df -h /"
