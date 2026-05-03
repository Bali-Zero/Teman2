#!/usr/bin/env bash
# Anti-rogue-AI gate: verify FastAPI import chain after backend changes
# Triggered by pre-commit when any apps/backend-rag/backend/ file is modified
# Prevents Gemini/Windsurf/Cursor from silently removing critical imports
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/../.." && pwd)/apps/backend-rag"

if [ -d "$BACKEND_DIR/.venv" ]; then
    PYTHON="$BACKEND_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

echo "🔗 Testing FastAPI import chain (anti-rogue-AI)..."
PYTHONPATH="$BACKEND_DIR" "$PYTHON" -c \
    "from backend.app.dependencies import get_current_user; print('✅ import chain OK')" || {
    echo ""
    echo "❌ CRITICO: import chain rotta!"
    echo "   Verifica: cd apps/backend-rag && python -c 'from backend.app.dependencies import get_current_user'"
    echo "   Causa probabile: rogue AI ha rimosso un import critico."
    echo "   Fix: ripristina l'import mancante, NON usare --no-verify."
    exit 1
}
