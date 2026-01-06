#!/bin/bash
# Script per vedere i log del bot Telegram in tempo reale

APP_NAME="nuzantara-rag"

echo "📱 Telegram Bot Logs - App: $APP_NAME"
echo "======================================"
echo ""
echo "Filtri disponibili:"
echo "  - Tutti i log Telegram: grep '📱'"
echo "  - Solo streaming: grep 'Streaming'"
echo "  - Solo errori: grep '❌\|ERROR'"
echo "  - Solo aggiornamenti: grep 'Message updated'"
echo ""
echo "Premi Ctrl+C per uscire"
echo ""

# flyctl logs fa streaming di default (non serve --follow)
# Usa grep con --line-buffered per output in tempo reale
flyctl logs --app "$APP_NAME" 2>&1 | grep --line-buffered -E "📱|Telegram|telegram|streaming|Streaming"

