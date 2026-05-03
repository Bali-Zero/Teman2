#!/bin/bash
# Start nuzantara-rag locally

cd "$(dirname "$0")"

# Load local env
export $(grep -v '^#' .env.local | xargs)

# Activate venv
source .venv/bin/activate

# Start server
echo "Starting Nuzantara RAG on http://localhost:8080"
uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload
