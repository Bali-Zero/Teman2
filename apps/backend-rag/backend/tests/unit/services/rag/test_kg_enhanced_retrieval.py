"""
Tests for KGEnhancedRetrieval
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.kg_enhanced_retrieval import KGContext, KGEnhancedRetrieval


class TestKGContext:
    """Test KGContext dataclass"""

    def test_kg_context_init(self):
        """Test KGContext initialization"""
        context = KGContext(
            entities_found=[{"name": "Test Entity"}],
            relationships=[{"type": "related_to"}],
            source_chunk_ids=["chunk1", "chunk2"],
            graph_summary="Test summary",
            confidence=0.8,
        )

        assert len(context.entities_found) == 1
        assert len(context.relationships) == 1
        assert len(context.source_chunk_ids) == 2
        assert context.graph_summary == "Test summary"
        assert context.confidence == 0.8


class TestKGEnhancedRetrieval:
    """Test KGEnhancedRetrieval class"""

    def test_init(self):
        """Test KGEnhancedRetrieval initialization"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        assert retrieval.db_pool == mock_pool

    def test_extract_entities_from_query_uu(self):
        """Test extracting UU entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana UU No 12 Tahun 2024?"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("UU" in mention for mention, _ in entities)

    def test_extract_entities_from_query_pp(self):
        """Test extracting PP entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "PP No 15 Tahun 2023"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("PP" in mention.upper() for mention, _ in entities)

    def test_extract_entities_from_query_kitas(self):
        """Test extracting KITAS entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana cara mendapatkan KITAS?"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("KITAS" in mention for mention, _ in entities)

    def test_extract_entities_from_query_pt_pma(self):
        """Test extracting PT PMA entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Saya ingin mendirikan PT PMA"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("PT PMA" in mention or "PMA" in mention for mention, _ in entities)

    def test_extract_entities_from_query_nib(self):
        """Test extracting NIB entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana cara mendapatkan NIB?"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("NIB" in mention for mention, _ in entities)

    def test_extract_entities_from_query_pasal(self):
        """Test extracting Pasal entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Pasal 1 menjelaskan tentang..."
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("PASAL" in mention.upper() for mention, _ in entities)

    def test_extract_entities_from_query_pph(self):
        """Test extracting PPh entities from query"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana PPh 21?"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) > 0
        assert any("PPH" in mention.upper() for mention, _ in entities)

    def test_extract_entities_from_query_no_entities(self):
        """Test extracting entities from query with no matches"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "This is a regular question without any entities"
        entities = retrieval.extract_entities_from_query(query)

        assert len(entities) == 0

    def test_extract_entities_deduplication(self):
        """Test that duplicate entities are removed"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "KITAS KITAS KITAS"
        entities = retrieval.extract_entities_from_query(query)

        # Should deduplicate
        mentions = [mention for mention, _ in entities]
        assert len(mentions) == len(set(mentions))

    @pytest.mark.asyncio
    async def test_find_kg_entities_empty_mentions(self):
        """Test find_kg_entities with empty mentions"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        result = await retrieval.find_kg_entities([])

        assert result == []

    @pytest.mark.asyncio
    async def test_find_kg_entities_success(self):
        """Test find_kg_entities with successful match"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        # Use dict to match what dict(row) produces
        mock_row = {
            "entity_id": "entity1",
            "entity_type": "undang_undang",
            "name": "UU No 12 Tahun 2024",
            "confidence": 0.9,
            "source_chunk_ids": ["chunk1", "chunk2"],
        }

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        retrieval = KGEnhancedRetrieval(mock_pool)

        mentions = [("UU No 12 Tahun 2024", "undang_undang")]
        result = await retrieval.find_kg_entities(mentions)

        assert len(result) > 0
        assert result[0]["entity_id"] == "entity1"
        assert result[0]["matched_mention"] == "UU No 12 Tahun 2024"

    @pytest.mark.asyncio
    async def test_get_related_entities_empty(self):
        """Test get_related_entities with empty entity_ids"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        entities, relationships = await retrieval.get_related_entities([])

        assert entities == []
        assert relationships == []

    @pytest.mark.asyncio
    async def test_get_related_entities_success(self):
        """Test get_related_entities with successful traversal"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        # Mock edge as dict
        mock_edge = {
            "relationship_id": "rel1",
            "source_entity_id": "entity1",
            "target_entity_id": "entity2",
            "relationship_type": "related_to",
            "confidence": 0.8,
            "source_chunk_ids": ["chunk1"],
            "source_name": "Entity 1",
            "source_type": "undang_undang",
            "target_name": "Entity 2",
            "target_type": "peraturan_pemerintah",
        }

        # Mock related entity as dict
        mock_entity = {
            "entity_id": "entity2",
            "entity_type": "peraturan_pemerintah",
            "name": "Entity 2",
            "confidence": 0.7,
            "source_chunk_ids": ["chunk2"],
        }

        mock_conn.fetch = AsyncMock(side_effect=[[mock_edge], [mock_entity]])

        retrieval = KGEnhancedRetrieval(mock_pool)

        entities, relationships = await retrieval.get_related_entities(["entity1"], max_depth=1)

        assert len(relationships) > 0
        assert len(entities) > 0

    @pytest.mark.asyncio
    async def test_get_source_chunks_empty(self):
        """Test get_source_chunks with empty entity_ids"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        result = await retrieval.get_source_chunks([])

        assert result == []

    @pytest.mark.asyncio
    async def test_get_source_chunks_success(self):
        """Test get_source_chunks with successful retrieval"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        # Mock node with chunks as dict
        mock_node = {"source_chunk_ids": ["chunk1", "chunk2"]}

        # Mock edge with chunks as dict
        mock_edge = {"source_chunk_ids": ["chunk3"]}

        mock_conn.fetch = AsyncMock(side_effect=[[mock_node], [mock_edge]])

        retrieval = KGEnhancedRetrieval(mock_pool)

        result = await retrieval.get_source_chunks(["entity1"])

        assert len(result) > 0
        assert "chunk1" in result
        assert "chunk2" in result
        assert "chunk3" in result

    def test_build_graph_summary_empty(self):
        """Test build_graph_summary with empty entities and relationships"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        summary = retrieval.build_graph_summary([], [], [])

        assert summary == ""

    def test_build_graph_summary_with_entities(self):
        """Test build_graph_summary with entities"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        entities = [
            {"entity_type": "undang_undang", "name": "UU No 12"},
            {"entity_type": "undang_undang", "name": "UU No 15"},
            {"entity_type": "peraturan_pemerintah", "name": "PP No 5"},
        ]

        summary = retrieval.build_graph_summary(entities, [], [])

        assert "[KNOWLEDGE GRAPH CONTEXT]" in summary
        assert "undang_undang" in summary
        assert "peraturan_pemerintah" in summary
        assert "UU No 12" in summary

    def test_build_graph_summary_with_relationships(self):
        """Test build_graph_summary with relationships"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        relationships = [
            {
                "source_name": "Entity 1",
                "target_name": "Entity 2",
                "relationship_type": "related_to",
            }
        ]

        summary = retrieval.build_graph_summary([], relationships, [])

        assert "Key relationships:" in summary
        assert "Entity 1" in summary
        assert "Entity 2" in summary
        assert "related_to" in summary

    def test_build_graph_summary_deduplicates_relationships(self):
        """Test build_graph_summary deduplicates relationships"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        relationships = [
            {
                "source_name": "Entity 1",
                "target_name": "Entity 2",
                "relationship_type": "related_to",
            },
            {
                "source_name": "Entity 1",
                "target_name": "Entity 2",
                "relationship_type": "related_to",
            },
        ]

        summary = retrieval.build_graph_summary([], relationships, [])

        # Should only appear once
        assert summary.count("Entity 1 --[related_to]--> Entity 2") == 1

    @pytest.mark.asyncio
    async def test_get_context_for_query_no_mentions(self):
        """Test get_context_for_query with no entity mentions"""
        mock_pool = MagicMock()
        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "This is a regular question without entities"
        context = await retrieval.get_context_for_query(query)

        assert context.entities_found == []
        assert context.relationships == []
        assert context.source_chunk_ids == []
        assert context.graph_summary == ""
        assert context.confidence == 0.0

    @pytest.mark.asyncio
    async def test_get_context_for_query_no_kg_entities(self):
        """Test get_context_for_query when no KG entities match"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire
        mock_conn.fetch = AsyncMock(return_value=[])

        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana UU No 999?"
        context = await retrieval.get_context_for_query(query)

        assert context.entities_found == []
        assert context.confidence == 0.0

    @pytest.mark.asyncio
    async def test_get_context_for_query_success(self):
        """Test get_context_for_query with successful retrieval"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        # Mock entity as dict (required for dict(row) in the code)
        mock_entity = {
            "entity_id": "entity1",
            "entity_type": "undang_undang",
            "name": "UU No 12 Tahun 2024",
            "confidence": 0.9,
            "source_chunk_ids": ["chunk1"],
        }

        # Mock chunk IDs as dict
        mock_chunk_row = {"source_chunk_ids": ["chunk1", "chunk2"]}

        # Query "Bagaimana UU No 12 Tahun 2024?" extracts 4 mentions:
        # - UU NO 12 TAHUN 2024, 12, 2024, 12 TAHUN
        # So find_kg_entities makes 4 fetch calls, then:
        # - get_related_entities: 1 fetch for edges
        # - get_source_chunks: 2 fetches (nodes, edges)
        mock_conn.fetch = AsyncMock(side_effect=[
            [mock_entity],   # find_kg_entities - UU mention
            [],              # find_kg_entities - 12
            [],              # find_kg_entities - 2024
            [],              # find_kg_entities - 12 TAHUN
            [],              # get_related_entities - edges
            [mock_chunk_row],  # get_source_chunks - nodes
            [],              # get_source_chunks - edges
        ])

        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana UU No 12 Tahun 2024?"
        context = await retrieval.get_context_for_query(query)

        assert len(context.entities_found) > 0
        assert len(context.source_chunk_ids) > 0
        assert context.graph_summary != ""
        assert context.confidence > 0.0

    @pytest.mark.asyncio
    async def test_get_context_for_query_with_related_entities(self):
        """Test get_context_for_query with related entities"""
        from contextlib import asynccontextmanager

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        # Mock entity as dict
        mock_entity = {
            "entity_id": "entity1",
            "entity_type": "undang_undang",
            "name": "UU No 12",
            "confidence": 0.9,
            "source_chunk_ids": ["chunk1"],
        }

        # Mock edge as dict
        mock_edge = {
            "relationship_id": "rel1",
            "source_entity_id": "entity1",
            "target_entity_id": "entity2",
            "relationship_type": "related_to",
            "confidence": 0.8,
            "source_chunk_ids": ["chunk2"],
            "source_name": "UU No 12",
            "source_type": "undang_undang",
            "target_name": "PP No 5",
            "target_type": "peraturan_pemerintah",
        }

        # Mock related entity as dict
        mock_related = {
            "entity_id": "entity2",
            "entity_type": "peraturan_pemerintah",
            "name": "PP No 5",
            "confidence": 0.7,
            "source_chunk_ids": ["chunk3"],
        }

        # Mock chunk rows as dict
        mock_chunk_row = {"source_chunk_ids": ["chunk1", "chunk2", "chunk3"]}

        # Query "Bagaimana UU No 12?" extracts 2 mentions: UU NO 12, 12
        # Flow: find_kg_entities (2 fetches) + get_related_entities (2 fetches with edges) + get_source_chunks (2 fetches)
        mock_conn.fetch = AsyncMock(
            side_effect=[
                [mock_entity],   # find_kg_entities - UU mention
                [],              # find_kg_entities - 12 mention
                [mock_edge],     # get_related_entities - edges
                [mock_related],  # get_related_entities - related entities
                [mock_chunk_row],  # get_source_chunks - nodes
                [],              # get_source_chunks - edges
            ]
        )

        retrieval = KGEnhancedRetrieval(mock_pool)

        query = "Bagaimana UU No 12?"
        context = await retrieval.get_context_for_query(query, max_depth=1)

        assert len(context.entities_found) > 0
        assert len(context.relationships) > 0
        assert len(context.source_chunk_ids) > 0
        assert context.confidence > 0.0
