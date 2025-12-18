#!/bin/bash
echo "🚀 Starting ZANTARA RAG on port ${PORT:-8080}..."
echo "📂 PWD: $(pwd)"
echo "🐍 PYTHONPATH: $PYTHONPATH"

# Run uvicorn in foreground (required for Fly.io)
exec python -m uvicorn app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080} --log-level info
