#!/bin/bash
# Start Backend with minimal dependencies

cd /sessions/epic-gifted-thompson/mnt/antonellosiano/Desktop/nuzantara/apps/backend-rag

echo "Installing critical dependencies..."
python3 -m pip install --user \
  httpx redis aioredis tiktoken \
  qdrant-client openai anthropic \
  google-genai google-cloud-storage \
  sentence-transformers torch transformers \
  > /tmp/backend_deps.log 2>&1 &

PIP_PID=$!
echo "Dependencies installing in background (PID: $PIP_PID)"
echo "Log: /tmp/backend_deps.log"

# Wait a bit for essential packages
sleep 10

echo "Starting backend..."
export PYTHONPATH=$(pwd):$PYTHONPATH
export PATH="/sessions/epic-gifted-thompson/.local/bin:$PATH"

cd backend
uvicorn app.main_cloud:app --host 0.0.0.0 --port 8080 --reload
