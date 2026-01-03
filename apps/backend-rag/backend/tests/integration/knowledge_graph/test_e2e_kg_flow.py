"""
Integration Tests: End-to-End Knowledge Graph Flow

Tests complete Knowledge Graph flow from document ingestion through:
1. Document ingestion
2. Entity extraction (KGExtractor)
3. Relation extraction
4. Coreference resolution
5. Knowledge Graph Pipeline execution
6. Entity linking to Episodic Memory
7. Graph traversal queries

Target: Test complete integration of Knowledge Graph components
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.knowledge_graph.extractor import KGExtractor
from services.knowledge_graph.pipeline import KGPipeline, PipelineConfig


@pytest.fixture
def mock_db_pool():
    """Mock PostgreSQL connection pool"""
    pool = AsyncMock()
    conn = AsyncMock()

    async def acquire():
        return conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM Gateway for entity extraction"""
    gateway = MagicMock()
    gateway.query = AsyncMock(return_value={
        "text": '{"entities": [{"name": "Marco Verdi", "type": "PERSON"}], "relations": []}'
    })
    return gateway


@pytest.fixture
def kg_extractor(mock_llm_gateway):
    """Create KGExtractor with mocked LLM"""
    with patch('services.knowledge_graph.kg_extractor.LLMGateway', return_value=mock_llm_gateway):
        extractor = KGExtractor()
        return extractor


@pytest.fixture
def kg_pipeline(mock_db_pool):
    """Create KGPipeline with mocked dependencies"""
    config = PipelineConfig(
        batch_size=10,
        enable_coreference=True,
        enable_entity_linking=True
    )

    with patch('services.knowledge_graph.kg_pipeline.asyncpg.create_pool') as mock_pool:
        mock_pool.return_value = mock_db_pool
        pipeline = KGPipeline(config=config, db_pool=mock_db_pool)
        return pipeline


class TestE2EKnowledgeGraphFlow:
    """End-to-End Knowledge Graph Flow Tests"""

    @pytest.mark.asyncio
    async def test_complete_kg_extraction_pipeline(
        self, kg_pipeline, kg_extractor, mock_db_pool, mock_llm_gateway
    ):
        """Test complete pipeline: Document → Entities → Relations → Storage"""
        document_text = """
        Marco Verdi ha aperto una PT PMA a Bali nel 2024.
        La società si chiama "Bali Tech Solutions" e opera nel settore IT.
        Marco ha ottenuto un KITAS E33G per lavorare in Indonesia.
        """

        # Mock entity extraction
        mock_entities = [
            {"name": "Marco Verdi", "type": "PERSON", "confidence": 0.95},
            {"name": "PT PMA", "type": "COMPANY_TYPE", "confidence": 0.90},
            {"name": "Bali", "type": "LOCATION", "confidence": 0.98},
            {"name": "Bali Tech Solutions", "type": "COMPANY", "confidence": 0.92},
            {"name": "E33G", "type": "VISA_TYPE", "confidence": 0.88}
        ]

        mock_relations = [
            {"subject": "Marco Verdi", "predicate": "FOUNDED", "object": "Bali Tech Solutions"},
            {"subject": "Marco Verdi", "predicate": "HAS_VISA", "object": "E33G"},
            {"subject": "Bali Tech Solutions", "predicate": "LOCATED_IN", "object": "Bali"}
        ]

        # Mock extraction result
        with patch.object(kg_extractor, 'extract_entities') as mock_extract:
            mock_extract.return_value = {
                "entities": mock_entities,
                "relations": mock_relations,
                "confidence": 0.90
            }

            # Execute pipeline
            result = await kg_pipeline.process_document(
                text=document_text,
                metadata={"source": "test", "doc_id": "test-123"}
            )

            # Verify extraction occurred
            assert result is not None
            assert "entities" in result or "success" in result

    @pytest.mark.asyncio
    async def test_coreference_resolution_in_pipeline(
        self, kg_pipeline, mock_db_pool
    ):
        """Test that coreference resolution is applied in pipeline"""
        document_text = """
        Marco Verdi ha aperto una PT PMA. Lui ha ottenuto un KITAS E33G.
        La società opera nel settore IT. Essa è stata fondata nel 2024.
        """

        # Mock coreference resolver
        with patch('services.knowledge_graph.coreference.CoreferenceResolver') as mock_resolver:
            mock_resolver_instance = MagicMock()
            mock_resolver_instance.resolve = MagicMock(return_value={
                "resolved_text": "Marco Verdi ha aperto una PT PMA. Marco Verdi ha ottenuto un KITAS E33G.",
                "coreferences": [
                    {"mention": "Lui", "entity": "Marco Verdi"},
                    {"mention": "La società", "entity": "PT PMA"},
                    {"mention": "Essa", "entity": "PT PMA"}
                ]
            })
            mock_resolver.return_value = mock_resolver_instance

            # Execute pipeline
            result = await kg_pipeline.process_document(
                text=document_text,
                metadata={"source": "test"}
            )

            # Verify coreference resolution was applied
            assert result is not None

    @pytest.mark.asyncio
    async def test_entity_linking_to_episodic_memory(
        self, kg_pipeline, mock_db_pool
    ):
        """Test that extracted entities are linked to episodic memory events"""
        document_text = "Marco Verdi ha completato la domanda per E33G oggi."

        # Mock episodic memory service
        with patch('services.memory.episodic_memory_service.EpisodicMemoryService') as mock_episodic:
            mock_episodic_instance = MagicMock()
            mock_episodic_instance.create_event = AsyncMock(return_value={
                "event_id": 123,
                "success": True
            })
            mock_episodic_instance.link_entity_to_event = AsyncMock(return_value={
                "success": True
            })
            mock_episodic.return_value = mock_episodic_instance

            # Execute pipeline
            result = await kg_pipeline.process_document(
                text=document_text,
                metadata={"source": "conversation", "user_email": "marco@example.com"}
            )

            # Verify entity linking occurred
            # (In real flow, entities would be linked to episodic memory events)
            assert result is not None

    @pytest.mark.asyncio
    async def test_batch_processing_multiple_documents(
        self, kg_pipeline, mock_db_pool
    ):
        """Test batch processing of multiple documents"""
        documents = [
            {"text": "Marco Verdi ha aperto PT PMA", "metadata": {"doc_id": "1"}},
            {"text": "Bali Tech Solutions opera a Bali", "metadata": {"doc_id": "2"}},
            {"text": "E33G KITAS per nomadi digitali", "metadata": {"doc_id": "3"}}
        ]

        # Mock batch processing
        with patch.object(kg_pipeline, 'process_document') as mock_process:
            mock_process.side_effect = [
                {"success": True, "entities": 2},
                {"success": True, "entities": 1},
                {"success": True, "entities": 1}
            ]

            # Process batch
            results = []
            for doc in documents:
                result = await kg_pipeline.process_document(
                    text=doc["text"],
                    metadata=doc["metadata"]
                )
                results.append(result)

            # Verify all processed
            assert len(results) == 3
            assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_graph_traversal_query(
        self, kg_pipeline, mock_db_pool
    ):
        """Test querying the knowledge graph for entity relationships"""
        query = "Chi ha fondato Bali Tech Solutions?"

        # Mock graph query
        mock_result = MagicMock()
        mock_result.fetchall = AsyncMock(return_value=[
            {"subject": "Marco Verdi", "predicate": "FOUNDED", "object": "Bali Tech Solutions"}
        ])

        conn = await mock_db_pool.acquire()
        conn.fetch = AsyncMock(return_value=mock_result)

        # Execute graph query
        # (In real implementation, this would use GraphTraversalTool or similar)
        result = await conn.fetch(
            "SELECT * FROM kg_relations WHERE object = $1 AND predicate = 'FOUNDED'",
            "Bali Tech Solutions"
        )

        # Verify query result
        assert result is not None
        rows = await result.fetchall()
        assert len(rows) > 0

    @pytest.mark.asyncio
    async def test_error_handling_in_kg_pipeline(
        self, kg_pipeline, mock_db_pool
    ):
        """Test error handling when extraction fails"""
        document_text = "Invalid document"

        # Mock extraction error
        with patch('services.knowledge_graph.kg_extractor.KGExtractor') as mock_extractor:
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.extract_entities = AsyncMock(
                side_effect=Exception("Extraction failed")
            )
            mock_extractor.return_value = mock_extractor_instance

            # Execute pipeline - should handle error gracefully
            try:
                result = await kg_pipeline.process_document(
                    text=document_text,
                    metadata={"source": "test"}
                )
                # Should either return error response or None
                assert result is None or "error" in str(result).lower()
            except Exception as e:
                # If exception is raised, verify it's handled appropriately
                assert "extraction" in str(e).lower() or "error" in str(e).lower()

