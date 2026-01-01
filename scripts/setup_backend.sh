#!/bin/bash
set -e

echo "🔧 Setting up Backend RAG environment..."

cd apps/backend-rag

if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

echo "🔌 Activating virtual environment..."
source .venv/bin/activate

echo "📥 Installing dependencies (including langgraph)..."
pip install -r requirements.txt

echo "✅ Setup complete! run 'source apps/backend-rag/.venv/bin/activate' to use."
