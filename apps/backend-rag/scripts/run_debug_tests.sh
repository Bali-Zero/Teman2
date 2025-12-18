#!/bin/bash
# Run debug tests with extensive logging

set -e

echo "=========================================="
echo "Running Conversation Memory Debug Tests"
echo "=========================================="
echo ""

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/apps/backend-rag/backend"
export DATABASE_URL="${DATABASE_URL:-postgresql://test:test@localhost:5432/test}"
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export GOOGLE_API_KEY="${GOOGLE_API_KEY:-test_google_api_key_for_testing}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-test_openai_api_key_for_testing}"

echo "Environment:"
echo "  DATABASE_URL: $DATABASE_URL"
echo "  QDRANT_URL: $QDRANT_URL"
echo ""

# Run tests with debug logging
echo "Running debug tests..."
echo ""

cd apps/backend-rag

pytest tests/integration/test_conversation_memory_debug.py \
    -v \
    -s \
    --log-cli-level=DEBUG \
    --log-cli-format="%(asctime)s - %(name)s - %(levelname)s - %(message)s" \
    --tb=short \
    "$@"

echo ""
echo "=========================================="
echo "Debug tests completed"
echo "=========================================="

