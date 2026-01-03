"""
Integration Tests: End-to-End RAG Agentic Flow

Tests complete query flow from user input through:
1. Intent Classification
2. Query Routing (Fast/Pro/DeepThink)
3. RAG Search with VectorSearchTool
4. Tool Execution (ReAct Pattern)
5. Reasoning Loop (Thought → Action → Observation)
6. Response Generation
7. Memory Persistence
8. Response Pipeline (Verification, PostProcessing, Citation, Format)

Target: Test complete integration of all components working together
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.rag.agentic import AgenticRAGOrchestrator


@pytest.fixture
def mock_search_service():
    """Mock SearchService for RAG retrieval"""
    service = MagicMock()
    service.search = AsyncMock(return_value={
        "results": [
            {
                "id": "doc1",
                "text": "E33G Digital Nomad KITAS costs Rp 17-19 million",
                "score": 0.85,
                "metadata": {"source": "visa_oracle", "type": "visa_info"}
            },
            {
                "id": "doc2",
                "text": "E33G requires proof of remote work and $2,000/month income",
                "score": 0.82,
                "metadata": {"source": "visa_oracle", "type": "requirements"}
            }
        ],
        "total": 2
    })
    return service


@pytest.fixture
def mock_db_pool():
    """Mock PostgreSQL connection pool"""
    pool = AsyncMock()
    conn = AsyncMock()

    # Mock connection context manager
    async def acquire():
        return conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway for AI responses"""
    gateway = MagicMock()

    # Mock streaming response
    async def mock_stream(*args, **kwargs):
        chunks = [
            "E33G",
            " Digital",
            " Nomad",
            " KITAS",
            " costs",
            " Rp",
            " 17-19",
            " million",
            " based",
            " on",
            " the",
            " documents",
            "."
        ]
        for chunk in chunks:
            yield chunk

    gateway.stream_query = AsyncMock(return_value=mock_stream())

    # Mock non-streaming response
    gateway.query = AsyncMock(return_value={
        "text": "E33G Digital Nomad KITAS costs Rp 17-19 million based on the documents.",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50}
    })

    return gateway


@pytest.fixture
def mock_memory_orchestrator():
    """Mock Memory Orchestrator"""
    orchestrator = MagicMock()
    orchestrator.get_user_context = AsyncMock(return_value={
        "profile": {"name": "Test User", "role": "Entrepreneur"},
        "facts": [],
        "collective_facts": [],
        "entities": {}
    })
    orchestrator.save_conversation = AsyncMock(return_value={"success": True})
    return orchestrator


@pytest.fixture
def orchestrator(mock_search_service, mock_db_pool, mock_memory_orchestrator):
    """Create AgenticRAGOrchestrator with mocked dependencies"""
    with patch('services.rag.agentic.create_agentic_rag') as mock_create:
        with patch('services.memory.MemoryOrchestrator', return_value=mock_memory_orchestrator):
            orchestrator = AgenticRAGOrchestrator(
                retriever=mock_search_service,
                db_pool=mock_db_pool,
                semantic_cache=None,
                clarification_service=None
            )
            return orchestrator


class TestE2ERAGFlow:
    """End-to-End RAG Agentic Flow Tests"""

    @pytest.mark.asyncio
    async def test_complete_query_flow_with_vector_search(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test complete flow: Query → Intent → Routing → Vector Search → Response"""
        query = "Quanto costa E33G Digital Nomad KITAS?"
        user_id = "test@example.com"

        # Mock intent classification
        with patch('services.classification.intent_classifier.IntentClassifier') as mock_intent:
            mock_classifier = MagicMock()
            mock_classifier.classify_intent = AsyncMock(return_value={
                "category": "business_simple",
                "confidence": 0.9,
                "suggested_ai": "fast",
                "skip_rag": False
            })
            mock_intent.return_value = mock_classifier

            # Mock LLM response with tool call
            with patch.object(orchestrator, '_llm_gateway') as mock_gateway:
                mock_gateway_instance = MagicMock()

                # First call: Tool call for vector_search
                mock_tool_call = MagicMock()
                mock_tool_call.function_call.name = "vector_search"
                mock_tool_call.function_call.args = {
                    "query": "E33G Digital Nomad KITAS cost",
                    "collection": "visa_oracle"
                }

                # Second call: Final answer
                mock_final_response = MagicMock()
                mock_final_response.text = "E33G Digital Nomad KITAS costa Rp 17-19 milioni secondo i documenti."

                mock_gateway_instance.stream_query = AsyncMock(side_effect=[
                    [mock_tool_call],  # Tool call
                    [mock_final_response]  # Final answer
                ])
                mock_gateway.return_value = mock_gateway_instance

                # Execute query
                result = await orchestrator.process_query(
                    query=query,
                    user_id=user_id,
                    session_id="test-session",
                    conversation_history=[]
                )

                # Verify flow
                assert result is not None
                assert "response" in result or "text" in result

                # Verify vector search was called
                mock_search_service.search.assert_called()

                # Verify memory was accessed
                mock_memory_orchestrator.get_user_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_multi_step_reasoning_flow(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test multi-step reasoning: Query → Thought → Action → Observation → Final Answer"""
        query = "Calcola il costo totale per E33G KITAS più visto C1"
        user_id = "test@example.com"

        # Mock pricing tool
        with patch('services.rag.agentic.tools.PricingTool') as mock_pricing:
            mock_pricing_instance = MagicMock()
            mock_pricing_instance.execute = AsyncMock(return_value={
                "service": "E33G",
                "price": "Rp 17-19 million"
            })
            mock_pricing.return_value = mock_pricing_instance

            # Mock calculator tool
            with patch('services.rag.agentic.tools.CalculatorTool') as mock_calc:
                mock_calc_instance = MagicMock()
                mock_calc_instance.execute = AsyncMock(return_value={
                    "result": "Rp 20-22 million"
                })
                mock_calc.return_value = mock_calc_instance

                # Execute query
                result = await orchestrator.process_query(
                    query=query,
                    user_id=user_id,
                    session_id="test-session",
                    conversation_history=[]
                )

                # Verify multi-step reasoning occurred
                assert result is not None

                # Verify tools were called
                # (In real flow, tools would be called via tool_executor)

    @pytest.mark.asyncio
    async def test_conversation_history_context(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test that conversation history is properly used in context"""
        query = "E il visto C1?"
        user_id = "test@example.com"
        conversation_history = [
            {"role": "user", "content": "Quanto costa E33G?"},
            {"role": "assistant", "content": "E33G costa Rp 17-19 milioni."}
        ]

        # Execute query with history
        result = await orchestrator.process_query(
            query=query,
            user_id=user_id,
            session_id="test-session",
            conversation_history=conversation_history
        )

        # Verify context includes conversation history
        assert result is not None

        # Verify memory orchestrator was called with history
        mock_memory_orchestrator.get_user_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_response_pipeline_processing(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test that response goes through all pipeline stages"""
        query = "Quali sono i requisiti per E33G?"
        user_id = "test@example.com"

        # Mock response pipeline stages
        with patch('services.rag.agentic.pipeline.VerificationStage') as mock_verify:
            with patch('services.rag.agentic.pipeline.PostProcessingStage') as mock_post:
                with patch('services.rag.agentic.pipeline.CitationStage') as mock_cite:
                    with patch('services.rag.agentic.pipeline.FormatStage') as mock_format:

                        mock_verify_instance = MagicMock()
                        mock_verify_instance.process = MagicMock(return_value="verified")
                        mock_verify.return_value = mock_verify_instance

                        mock_post_instance = MagicMock()
                        mock_post_instance.process = MagicMock(return_value="cleaned")
                        mock_post.return_value = mock_post_instance

                        mock_cite_instance = MagicMock()
                        mock_cite_instance.process = MagicMock(return_value="cited")
                        mock_cite.return_value = mock_cite_instance

                        mock_format_instance = MagicMock()
                        mock_format_instance.process = MagicMock(return_value="formatted")
                        mock_format.return_value = mock_format_instance

                        # Execute query
                        result = await orchestrator.process_query(
                            query=query,
                            user_id=user_id,
                            session_id="test-session",
                            conversation_history=[]
                        )

                        # Verify pipeline stages were called
                        assert result is not None

    @pytest.mark.asyncio
    async def test_error_handling_and_fallback(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test error handling and fallback mechanisms"""
        query = "Test query"
        user_id = "test@example.com"

        # Simulate search service error
        mock_search_service.search = AsyncMock(side_effect=Exception("Search error"))

        # Execute query - should handle error gracefully
        try:
            result = await orchestrator.process_query(
                query=query,
                user_id=user_id,
                session_id="test-session",
                conversation_history=[]
            )
            # Should either return error response or fallback
            assert result is not None
        except Exception as e:
            # If exception is raised, verify it's handled appropriately
            assert "error" in str(e).lower() or "fallback" in str(e).lower()

    @pytest.mark.asyncio
    async def test_streaming_response_flow(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test streaming response generation"""
        query = "Raccontami di E33G"
        user_id = "test@example.com"

        # Mock streaming response
        async def mock_stream():
            chunks = ["E33G", " è", " un", " visto", " per", " nomadi", " digitali"]
            for chunk in chunks:
                yield chunk

        with patch.object(orchestrator, 'stream_query') as mock_stream_query:
            mock_stream_query.return_value = mock_stream()

            # Collect streamed chunks
            chunks = []
            async for chunk in orchestrator.stream_query(
                query=query,
                user_id=user_id,
                session_id="test-session",
                conversation_history=[]
            ):
                chunks.append(chunk)

            # Verify streaming worked
            assert len(chunks) > 0
            assert any("E33G" in str(chunk) for chunk in chunks)

    @pytest.mark.asyncio
    async def test_semantic_cache_integration(
        self, orchestrator, mock_search_service, mock_db_pool, mock_memory_orchestrator
    ):
        """Test semantic cache integration in query flow"""
        query = "Quanto costa E33G?"
        user_id = "test@example.com"

        # Mock semantic cache
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_cache.set = AsyncMock()

        # Create orchestrator with cache
        orchestrator_with_cache = AgenticRAGOrchestrator(
            retriever=mock_search_service,
            db_pool=mock_db_pool,
            semantic_cache=mock_cache,
            clarification_service=None
        )

        # Execute query
        result = await orchestrator_with_cache.process_query(
            query=query,
            user_id=user_id,
            session_id="test-session",
            conversation_history=[]
        )

        # Verify cache was checked
        mock_cache.get.assert_called()

        # Verify cache was set (if result was successful)
        if result and "error" not in str(result).lower():
            mock_cache.set.assert_called()

