#!/bin/bash
#
# Start Ollama for Development
# Keeps Ollama running for manual testing/development
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting Ollama for development..."
echo "   (Ollama will stay running until you stop it)"
echo ""

"$SCRIPT_DIR/ollama_cron_window.sh" start

echo ""
echo "✅ Ollama is running!"
echo ""
echo "💡 Usage:"
echo "   - Run tests: ./scripts/auto_agent_test.sh"
echo "   - Stop Ollama: ./scripts/ollama_cron_window.sh stop"
echo "   - Status: ./scripts/ollama_cron_window.sh status"
