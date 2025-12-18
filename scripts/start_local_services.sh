#!/bin/bash
# NUZANTARA - Start All Local Services
# Starts backend-rag, bali-intel-scraper, and zantara-media in tmux

set -e

echo "============================================"
echo "NUZANTARA - Starting Local Services"
echo "============================================"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux not found. Install it first:"
    echo "   macOS: brew install tmux"
    echo "   Linux: sudo apt-get install tmux"
    exit 1
fi

# Check environment variables
if [ -z "$DATABASE_URL" ]; then
    echo "⚠️  DATABASE_URL not set. Using default..."
    export DATABASE_URL="postgresql://localhost:5432/nuzantara_db"
fi

echo "✓ Environment ready"
echo ""

# Session name
SESSION="nuzantara"

# Kill existing session if it exists
tmux kill-session -t $SESSION 2>/dev/null || true

# Create new session
echo "Creating tmux session: $SESSION"
tmux new-session -d -s $SESSION -n "backend-rag"

# Window 1: Backend RAG (port 8080)
echo "Starting Backend RAG on port 8080..."
tmux send-keys -t $SESSION:0 "cd apps/backend-rag" C-m
tmux send-keys -t $SESSION:0 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:0 "echo 'BACKEND RAG - Port 8080'" C-m
tmux send-keys -t $SESSION:0 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:0 "uvicorn backend.app.main:app --port 8080 --reload" C-m

# Window 2: Bali Intel Scraper API (port 8002)
echo "Starting Bali Intel Scraper API on port 8002..."
tmux new-window -t $SESSION:1 -n "scraper-api"
tmux send-keys -t $SESSION:1 "cd apps/bali-intel-scraper" C-m
tmux send-keys -t $SESSION:1 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:1 "echo 'BALI INTEL SCRAPER API - Port 8002'" C-m
tmux send-keys -t $SESSION:1 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:1 "python -m uvicorn api.main:app --port 8002 --reload" C-m

# Window 3: Zantara Media (port 8001)
echo "Starting Zantara Media on port 8001..."
tmux new-window -t $SESSION:2 -n "zantara-media"
tmux send-keys -t $SESSION:2 "cd apps/zantara-media/backend" C-m
tmux send-keys -t $SESSION:2 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:2 "echo 'ZANTARA MEDIA - Port 8001'" C-m
tmux send-keys -t $SESSION:2 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:2 "uvicorn app.main:app --port 8001 --reload" C-m

# Window 4: Commands (for testing)
tmux new-window -t $SESSION:3 -n "commands"
tmux send-keys -t $SESSION:3 "cd /Users/antonellosiano/Desktop/nuzantara" C-m
tmux send-keys -t $SESSION:3 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:3 "echo 'TEST COMMANDS'" C-m
tmux send-keys -t $SESSION:3 "echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m
tmux send-keys -t $SESSION:3 "echo 'Health Checks:'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl http://localhost:8080/health  # Backend RAG'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl http://localhost:8002/health  # Scraper API'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl http://localhost:8001/health  # Zantara Media'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m
tmux send-keys -t $SESSION:3 "echo 'Trigger Pipeline:'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl -X POST http://localhost:8001/api/automation/trigger'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m
tmux send-keys -t $SESSION:3 "echo 'Check Status:'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl http://localhost:8001/api/automation/status'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m
tmux send-keys -t $SESSION:3 "echo 'View Content:'" C-m
tmux send-keys -t $SESSION:3 "echo '  curl http://localhost:8001/api/content | jq'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m
tmux send-keys -t $SESSION:3 "echo 'API Docs:'" C-m
tmux send-keys -t $SESSION:3 "echo '  http://localhost:8001/docs  # Zantara Media'" C-m
tmux send-keys -t $SESSION:3 "echo '  http://localhost:8002/docs  # Scraper API'" C-m
tmux send-keys -t $SESSION:3 "echo ''" C-m

# Select first window
tmux select-window -t $SESSION:0

echo ""
echo "============================================"
echo "✓ Services Starting in tmux session: $SESSION"
echo "============================================"
echo ""
echo "Services:"
echo "  1. Backend RAG      - http://localhost:8080"
echo "  2. Scraper API      - http://localhost:8002"
echo "  3. Zantara Media    - http://localhost:8001"
echo ""
echo "Commands:"
echo "  tmux attach -t $SESSION    # Attach to session"
echo "  tmux kill-session -t $SESSION    # Stop all services"
echo ""
echo "Tmux Shortcuts (after attaching):"
echo "  Ctrl+b then 0-3   # Switch between windows"
echo "  Ctrl+b then d     # Detach (keeps services running)"
echo "  Ctrl+b then [     # Scroll mode (q to exit)"
echo ""
echo "Waiting 10 seconds for services to start..."
sleep 10

echo ""
echo "Testing services..."

# Test health checks
if curl -s http://localhost:8080/health | grep -q "healthy"; then
    echo "✓ Backend RAG is healthy"
else
    echo "⚠️  Backend RAG not responding yet"
fi

if curl -s http://localhost:8002/health | grep -q "healthy"; then
    echo "✓ Scraper API is healthy"
else
    echo "⚠️  Scraper API not responding yet"
fi

if curl -s http://localhost:8001/health | grep -q "healthy"; then
    echo "✓ Zantara Media is healthy"
else
    echo "⚠️  Zantara Media not responding yet"
fi

echo ""
echo "To view logs, attach to tmux session:"
echo "  tmux attach -t $SESSION"
echo ""
