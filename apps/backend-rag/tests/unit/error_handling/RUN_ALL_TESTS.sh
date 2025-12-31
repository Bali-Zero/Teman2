#!/bin/bash
# Script to run all error handling tests

set -e

echo "🧪 Running Complete Error Handling Test Suite"
echo "=============================================="

cd "$(dirname "$0")/../../.."

# Set PYTHONPATH
export PYTHONPATH=.

echo ""
echo "📊 AREA 1: AgenticRAGOrchestrator"
pytest tests/unit/services/rag/agentic/test_orchestrator_error_handling.py -v --tb=short

echo ""
echo "📊 AREA 2: SearchService"
pytest tests/unit/services/search/test_search_service_error_handling.py -v --tb=short

echo ""
echo "📊 AREA 3: MemoryOrchestrator"
pytest tests/unit/services/memory/test_memory_orchestrator_error_handling.py -v --tb=short

echo ""
echo "📊 AREA 4: LLM Gateway"
pytest tests/unit/services/rag/agentic/test_llm_gateway_error_handling.py -v --tb=short

echo ""
echo "📊 AREA 5: Database Pool"
pytest tests/unit/app/setup/test_database_error_recovery.py -v --tb=short

echo ""
echo "📊 AREA 6: Qdrant Client"
pytest tests/unit/core/test_qdrant_error_classification.py -v --tb=short

echo ""
echo "📊 AREA 7: Reasoning Engine"
pytest tests/unit/services/rag/agentic/test_reasoning_context_validation.py -v --tb=short

echo ""
echo "📊 AREA 8: Streaming Endpoints"
pytest tests/unit/app/routers/test_streaming_error_propagation.py -v --tb=short

echo ""
echo "📊 Comprehensive Integration Suite"
pytest tests/unit/error_handling/test_complete_error_handling_suite.py -v --tb=short

echo ""
echo "✅ All Error Handling Tests Complete!"
echo "======================================"

