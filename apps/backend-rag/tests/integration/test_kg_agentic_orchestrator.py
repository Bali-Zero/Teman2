"""
Integration Tests for KG-Agentic Orchestrator

Comprehensive test suite covering:
1. Golden route matching
2. KG traversal and entity extraction
3. Collection routing based on intent/entities
4. End-to-end query processing
5. Response structure validation
6. Edge cases and error handling

Run with:
    cd apps/backend-rag
    source .venv/bin/activate
    pytest tests/integration/test_kg_agentic_orchestrator.py -v --tb=short

Author: Nuzantara Team
Date: 2026-01-28
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:64732/test")


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db_pool():
    """Create mock database pool."""
    pool = AsyncMock()
    pool.acquire = AsyncMock()

    # Mock context manager
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)

    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    return pool


@pytest.fixture
def mock_retriever():
    """Create mock search service retriever."""
    retriever = AsyncMock()
    retriever.search_with_reranking = AsyncMock(
        return_value={
            "results": [
                {
                    "doc_id": "doc_001",
                    "title": "PT PMA Requirements",
                    "snippet": "To establish PT PMA, minimum capital is 10 billion IDR...",
                    "score": 0.92,
                },
                {
                    "doc_id": "doc_002",
                    "title": "KITAS Work Permit Process",
                    "snippet": "KITAS requires RPTKA approval first...",
                    "score": 0.88,
                },
            ]
        }
    )
    return retriever


@pytest.fixture
def mock_llm_gateway():
    """Create mock LLM gateway."""
    gateway = MagicMock()

    # Mock chat session
    chat = MagicMock()
    gateway.create_chat_with_history = MagicMock(return_value=chat)

    # Mock response
    response_obj = MagicMock()
    response_obj.usage_metadata = MagicMock()
    response_obj.usage_metadata.total_token_count = 500

    gateway.send_message = AsyncMock(
        return_value=(
            "Per aprire un ristorante a Bali come straniero, devi seguire questi passaggi:\n\n"
            "1. Scegliere il codice KBLI 56101 (Restaurant)\n"
            "2. Costituire una PT PMA (max 67% foreign ownership)\n"
            "3. Ottenere NIB via OSS\n"
            "4. Applicare per RPTKA e IMTA\n"
            "5. Ottenere KITAS\n\n"
            "Timeline stimato: 2-3 mesi. Costo: $8,000-15,000 USD.",
            "gemini-1.5-pro",
            response_obj,
        )
    )

    return gateway


@pytest.fixture
def mock_intent_classifier():
    """Create mock intent classifier."""
    classifier = MagicMock()
    classifier.classify_intent = AsyncMock(
        return_value={
            "category": "business_setup",
            "confidence": 0.85,
            "suggested_ai": "pro",
        }
    )
    return classifier


# =============================================================================
# GOLDEN ROUTE MATCHING TESTS
# =============================================================================


class TestGoldenRouteMatching:
    """Test golden route pattern matching."""

    @pytest.mark.asyncio
    async def test_restaurant_route_english(self, mock_db_pool, mock_retriever):
        """Test matching restaurant golden route (English query)."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        queries = [
            "How to open a restaurant in Bali as a foreigner?",
            "Start a restaurant business in Indonesia",
            "Open a cafe in Bali foreigner",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is not None, f"Should match restaurant route for: {query}"
            assert "restaurant" in route.route_id.lower(), (
                f"Should be restaurant route for: {query}"
            )

    @pytest.mark.asyncio
    async def test_it_company_route(self, mock_db_pool):
        """Test matching IT company golden route."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        # These queries should match IT company route
        queries = [
            "Start a software company in Indonesia foreigner",
            "Setup IT company as foreigner",
            "KBLI 62011 company setup",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is not None, f"Should match IT route for: {query}"

    @pytest.mark.asyncio
    async def test_work_permit_route(self, mock_db_pool):
        """Test matching work permit golden route."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        queries = [
            "I want to work in Bali",
            "Work permit for Indonesia",
            "How to get work permit in Indonesia?",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is not None, f"Should match work route for: {query}"
            assert route.route_id == "route:work_in_indonesia"

    @pytest.mark.asyncio
    async def test_kitas_kitap_conversion_route(self, mock_db_pool):
        """Test matching KITAS to KITAP conversion route."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        # Queries specifically mentioning KITAS to KITAP conversion
        queries = [
            "Convert KITAS to KITAP",
            "Upgrade KITAS to KITAP",
            "KITAS ke KITAP",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is not None, f"Should match KITAS-KITAP route for: {query}"
            assert route.route_id == "route:kitas_to_kitap", f"Wrong route for: {query}"

    @pytest.mark.asyncio
    async def test_digital_nomad_route(self, mock_db_pool):
        """Test matching digital nomad golden route."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        queries = [
            "Digital nomad visa Bali",
            "Remote worker visa Indonesia",
            "E33G visa requirements",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is not None, f"Should match nomad route for: {query}"
            assert route.route_id == "route:digital_nomad"

    @pytest.mark.asyncio
    async def test_no_route_match(self, mock_db_pool):
        """Test that unrelated queries don't match any route."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        queries = [
            "What's the weather in Bali?",
            "Best beaches in Indonesia",
            "Hello how are you?",
        ]

        for query in queries:
            route = kg_retrieval.match_golden_route(query)
            assert route is None, f"Should NOT match any route for: {query}"


# =============================================================================
# ENTITY EXTRACTION TESTS
# =============================================================================


class TestEntityExtraction:
    """Test entity extraction from queries."""

    @pytest.mark.asyncio
    async def test_extract_kbli_codes(self, mock_db_pool):
        """Test extraction of KBLI codes from query."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        query = "What permits do I need for KBLI 56101?"
        entities = kg_retrieval.extract_entities_from_query(query)

        kbli_entities = [e for e in entities if e[1] == "kbli"]
        assert len(kbli_entities) >= 1, "Should extract KBLI code"
        assert "56101" in kbli_entities[0][0]

    @pytest.mark.asyncio
    async def test_extract_permit_types(self, mock_db_pool):
        """Test extraction of permit types (KITAS, KITAP, etc.)."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        query = "How do I extend my KITAS and apply for KITAP?"
        entities = kg_retrieval.extract_entities_from_query(query)

        entity_types = [e[1] for e in entities]
        assert "kitas" in entity_types, "Should extract KITAS"
        assert "kitap" in entity_types, "Should extract KITAP"

    @pytest.mark.asyncio
    async def test_extract_company_types(self, mock_db_pool):
        """Test extraction of company types (PT PMA, CV, etc.)."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        query = "What's the difference between PT PMA and PT PMDN?"
        entities = kg_retrieval.extract_entities_from_query(query)

        entity_types = [e[1] for e in entities]
        assert "pt_pma" in entity_types, "Should extract PT PMA"
        assert "pt_pmdn" in entity_types, "Should extract PT PMDN"

    @pytest.mark.asyncio
    async def test_extract_work_documents(self, mock_db_pool):
        """Test extraction of work documents (RPTKA, IMTA)."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        query = "Do I need RPTKA and IMTA for work permit?"
        entities = kg_retrieval.extract_entities_from_query(query)

        entity_types = [e[1] for e in entities]
        assert "rptka" in entity_types, "Should extract RPTKA"
        assert "imta" in entity_types, "Should extract IMTA"

    @pytest.mark.asyncio
    async def test_extract_tax_types(self, mock_db_pool):
        """Test extraction of tax types (PPh, PPN, etc.)."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        kg_retrieval = KGEnhancedRetrieval(db_pool=mock_db_pool)

        query = "What are PPh 21 and PPN rates for PT PMA?"
        entities = kg_retrieval.extract_entities_from_query(query)

        entity_types = [e[1] for e in entities]
        assert "pph_21" in entity_types or "pph" in entity_types, "Should extract PPh"
        assert "ppn" in entity_types, "Should extract PPN"


# =============================================================================
# COLLECTION ROUTING TESTS
# =============================================================================


class TestCollectionRouting:
    """Test intelligent collection routing."""

    @pytest.mark.asyncio
    async def test_visa_query_routes_to_visa_collection(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that visa queries route to visa_oracle collection."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        # Override intent classifier
        mock_intent_classifier.classify_intent = AsyncMock(
            return_value={
                "category": "visa_immigration",
                "confidence": 0.9,
                "suggested_ai": "pro",
            }
        )

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        # Mock KG context
        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[{"name": "KITAS", "entity_type": "kitas"}],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.8,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="How to get KITAS work visa?",
                session_id="test_session",
            )

            assert "visa_oracle" in result.collections_searched

    @pytest.mark.asyncio
    async def test_tax_query_routes_to_tax_collection(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that tax queries route to tax_genius_hybrid collection."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        mock_intent_classifier.classify_intent = AsyncMock(
            return_value={
                "category": "tax_finance",
                "confidence": 0.9,
                "suggested_ai": "pro",
            }
        )

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[{"name": "PPh 21", "entity_type": "pph"}],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.8,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="What is PPh 21 tax rate?",
                session_id="test_session",
            )

            assert "tax_genius_hybrid" in result.collections_searched

    @pytest.mark.asyncio
    async def test_business_query_routes_to_multiple_collections(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that business setup queries route to multiple collections."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        mock_intent_classifier.classify_intent = AsyncMock(
            return_value={
                "category": "business_company",
                "confidence": 0.9,
                "suggested_ai": "pro",
            }
        )

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[
                    {"name": "PT PMA", "entity_type": "pt_pma"},
                    {"name": "KBLI 62011", "entity_type": "kbli"},
                ],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.8,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="How to setup PT PMA with KBLI 62011?",
                session_id="test_session",
            )

            # Should search multiple collections
            assert len(result.collections_searched) >= 2


# =============================================================================
# END-TO-END ORCHESTRATOR TESTS
# =============================================================================


class TestKGAgenticOrchestrator:
    """End-to-end orchestrator tests."""

    @pytest.mark.asyncio
    async def test_full_orchestration_with_golden_route(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test full orchestration flow with golden route match."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        # Mock KG context with golden route
        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import GoldenRoute, KGContext

            mock_kg.return_value = KGContext(
                entities_found=[
                    {"name": "Restaurant", "entity_type": "kbli_code"},
                    {"name": "PT PMA", "entity_type": "company_type"},
                ],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="[KNOWLEDGE GRAPH CONTEXT]\nKBLI 56101 → PT PMA → KITAS",
                confidence=0.9,
                golden_route=GoldenRoute(
                    route_id="route:foreigner_open_restaurant_bali",
                    name="Foreigner Opening Restaurant in Bali",
                    description="Complete path for a foreigner to open a restaurant",
                    path=["kbli:56101", "company:pt_pma", "license:nib", "permit:kitas"],
                    key_conditions=["Maximum 67% foreign ownership", "Need Indonesian partner"],
                    estimated_timeline_months=3,
                    estimated_cost_range_usd=[8000, 15000],
                ),
            )

            result = await orchestrator.process(
                query="How to open a restaurant in Bali as a foreigner?",
                session_id="test_session",
            )

        # Validate response structure
        assert result.answer is not None
        assert len(result.answer) > 0
        assert result.confidence > 0
        assert len(result.reasoning_trace) > 0
        assert result.golden_route_matched == "route:foreigner_open_restaurant_bali"
        assert result.estimated_timeline is not None
        assert result.estimated_cost is not None
        assert "$8,000" in result.estimated_cost or "8,000" in result.estimated_cost

    @pytest.mark.asyncio
    async def test_response_structure_validation(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that response has all required fields."""
        from backend.services.rag.agentic.kg_orchestrator import (
            AgenticResponse,
            KGAgenticOrchestrator,
        )

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.5,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="General question about Indonesia",
                session_id="test_session",
            )

        # Check all required fields
        assert isinstance(result, AgenticResponse)
        assert hasattr(result, "answer")
        assert hasattr(result, "confidence")
        assert hasattr(result, "reasoning_trace")
        assert hasattr(result, "sources")
        assert hasattr(result, "estimated_timeline")
        assert hasattr(result, "estimated_cost")
        assert hasattr(result, "intent_category")
        assert hasattr(result, "golden_route_matched")
        assert hasattr(result, "kg_entities_found")
        assert hasattr(result, "collections_searched")
        assert hasattr(result, "total_time_ms")
        assert hasattr(result, "model_used")

    @pytest.mark.asyncio
    async def test_reasoning_trace_completeness(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that reasoning trace captures all steps."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[{"name": "KITAS", "entity_type": "permit"}],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.7,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="How to get KITAS?",
                session_id="test_session",
            )

        trace = result.reasoning_trace

        # Should have at least: intent, entities, route check, vector search, synthesis
        assert len(trace) >= 4, f"Expected at least 4 trace steps, got {len(trace)}"

        # Check for key trace elements
        trace_text = " ".join(trace).lower()
        assert "intent" in trace_text or "detected" in trace_text, "Should mention intent detection"
        assert "search" in trace_text or "vector" in trace_text, "Should mention vector search"

    @pytest.mark.asyncio
    async def test_confidence_calculation(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test confidence score calculation logic."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        # Test with golden route (should boost confidence)
        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import GoldenRoute, KGContext

            mock_kg.return_value = KGContext(
                entities_found=[{"name": "Test", "entity_type": "test"}] * 5,
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.9,
                golden_route=GoldenRoute(
                    route_id="route:test",
                    name="Test Route",
                    description="Test",
                    path=["a", "b"],
                    key_conditions=[],
                ),
            )

            result_with_route = await orchestrator.process(
                query="Digital nomad visa",
                session_id="test_session",
            )

        # Test without golden route (lower confidence)
        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.5,
                golden_route=None,
            )

            result_without_route = await orchestrator.process(
                query="Random question",
                session_id="test_session",
            )

        # Golden route should boost confidence
        assert result_with_route.confidence > result_without_route.confidence


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_handles_llm_failure_gracefully(
        self, mock_db_pool, mock_retriever, mock_intent_classifier
    ):
        """Test graceful handling of LLM failure."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        # Create LLM gateway that raises exception
        failing_llm = MagicMock()
        failing_llm.create_chat_with_history = MagicMock()
        failing_llm.send_message = AsyncMock(side_effect=Exception("LLM API Error"))

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=failing_llm,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.5,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="Test query",
                session_id="test_session",
            )

        # Should return fallback response, not crash
        assert result is not None
        assert result.confidence == 0.0
        # Fallback message says "Mi dispiace..." or contains error indication
        assert "dispiace" in result.answer.lower() or "riprova" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_handles_empty_query(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test handling of edge case queries."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.0,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="   ",  # Whitespace only
                session_id="test_session",
            )

        assert result is not None


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_response_time_tracked(
        self, mock_db_pool, mock_retriever, mock_llm_gateway, mock_intent_classifier
    ):
        """Test that response time is tracked."""
        from backend.services.rag.agentic.kg_orchestrator import KGAgenticOrchestrator

        orchestrator = KGAgenticOrchestrator(
            db_pool=mock_db_pool,
            retriever=mock_retriever,
            llm_gateway=mock_llm_gateway,
            intent_classifier=mock_intent_classifier,
        )

        with patch.object(orchestrator.kg_retrieval, "get_context_for_query") as mock_kg:
            from backend.services.rag.kg_enhanced_retrieval import KGContext

            mock_kg.return_value = KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.5,
                golden_route=None,
            )

            result = await orchestrator.process(
                query="Test query",
                session_id="test_session",
            )

        assert result.total_time_ms > 0, "Should track response time"


# =============================================================================
# INTEGRATION WITH REAL DB (optional, skip if no DB)
# =============================================================================


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set, skipping real DB tests"
)
class TestRealDatabaseIntegration:
    """Tests that require actual database connection."""

    @pytest.fixture
    async def real_db_pool(self):
        """Create real database pool."""
        import asyncpg

        pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
        try:
            yield pool
        finally:
            await pool.close()

    @pytest.mark.asyncio
    async def test_kg_path_query_real(self, real_db_pool):
        """Test KG path query against real database."""
        from backend.services.rag.kg_enhanced_retrieval import KGEnhancedRetrieval

        # Need to await the fixture properly
        pool = real_db_pool
        if hasattr(pool, "__anext__"):
            pool = await pool.__anext__()

        kg_retrieval = KGEnhancedRetrieval(db_pool=pool)

        # This should work if seed data was imported
        kg_context = await kg_retrieval.get_context_for_query(
            query="How to open a restaurant and get KITAS?",
            max_depth=2,
        )

        # Should find entities if seed data exists
        # (may be empty if seed data not imported)
        assert kg_context is not None


# =============================================================================
# RUN CONFIGURATION
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
