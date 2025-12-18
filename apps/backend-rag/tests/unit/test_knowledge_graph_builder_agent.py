"""
Unit Tests for Knowledge Graph Builder Agent
Tests agents/agents/knowledge_graph_builder.py

Target: Autonomous knowledge graph builder
File: backend/agents/agents/knowledge_graph_builder.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add tests directory to path to import conftest helpers
tests_path = Path(__file__).parent.parent
if str(tests_path) not in sys.path:
    sys.path.insert(0, str(tests_path))

from agents.agents.knowledge_graph_builder import KnowledgeGraphBuilder
from conftest import create_async_cm_mock


class TestKnowledgeGraphBuilderInit:
    """Test KnowledgeGraphBuilder initialization"""

    def test_init_with_db_pool(self):
        """Test: KnowledgeGraphBuilder initializes with provided db_pool"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        assert builder.db_pool == mock_pool
        assert builder.schema_service is not None
        assert builder.entity_extractor is not None
        assert builder.relationship_extractor is not None
        assert builder.repository is not None

    def test_init_without_db_pool_raises(self):
        """Test: KnowledgeGraphBuilder raises RuntimeError without db_pool"""
        # Should raise RuntimeError when no db_pool is available
        with pytest.raises(RuntimeError, match="Database pool not available"):
            KnowledgeGraphBuilder(db_pool=None)


class TestInitGraphSchema:
    """Test init_graph_schema method"""

    @pytest.mark.asyncio
    async def test_init_graph_schema_success(self):
        """Test: Successfully initializes graph schema"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Mock schema service
        builder.schema_service.init_schema = AsyncMock()

        await builder.init_graph_schema()

        builder.schema_service.init_schema.assert_called_once()


class TestExtractEntitiesFromText:
    """Test extract_entities_from_text method"""

    @pytest.mark.asyncio
    async def test_extract_entities_success(self):
        """Test: Successfully extracts entities from text"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Mock entity extractor
        mock_entities = [
            {"name": "John Doe", "type": "PERSON", "canonical_name": "john_doe"},
            {"name": "ABC Corp", "type": "ORGANIZATION", "canonical_name": "abc_corp"},
        ]
        builder.entity_extractor.extract_entities = AsyncMock(return_value=mock_entities)

        result = await builder.extract_entities_from_text(
            "John Doe works at ABC Corp", timeout=30.0
        )

        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[1]["type"] == "ORGANIZATION"
        builder.entity_extractor.extract_entities.assert_called_once_with(
            "John Doe works at ABC Corp", 30.0
        )

    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self):
        """Test: Handles empty text"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        builder.entity_extractor.extract_entities = AsyncMock(return_value=[])

        result = await builder.extract_entities_from_text("", timeout=30.0)

        assert result == []


class TestExtractRelationships:
    """Test extract_relationships method"""

    @pytest.mark.asyncio
    async def test_extract_relationships_success(self):
        """Test: Successfully extracts relationships"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        entities = [
            {"name": "John Doe", "type": "PERSON"},
            {"name": "ABC Corp", "type": "ORGANIZATION"},
        ]

        mock_relationships = [
            {
                "source": "John Doe",
                "target": "ABC Corp",
                "type": "WORKS_AT",
                "strength": 0.9,
            }
        ]

        builder.relationship_extractor.extract_relationships = AsyncMock(
            return_value=mock_relationships
        )

        result = await builder.extract_relationships(
            entities, "John Doe works at ABC Corp", timeout=30.0
        )

        assert len(result) == 1
        assert result[0]["type"] == "WORKS_AT"
        assert result[0]["strength"] == 0.9
        builder.relationship_extractor.extract_relationships.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_relationships_no_entities(self):
        """Test: Handles empty entity list"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        builder.relationship_extractor.extract_relationships = AsyncMock(return_value=[])

        result = await builder.extract_relationships([], "Some text", timeout=30.0)

        assert result == []


class TestUpsertEntity:
    """Test upsert_entity method"""

    @pytest.mark.asyncio
    async def test_upsert_entity_success(self):
        """Test: Successfully upserts entity"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        mock_conn = AsyncMock()
        mock_entity_id = 123

        builder.repository.upsert_entity = AsyncMock(return_value=mock_entity_id)

        result = await builder.upsert_entity(
            entity_type="PERSON",
            name="John Doe",
            canonical_name="john_doe",
            metadata={"info": "test"},
            conn=mock_conn,
        )

        assert result == mock_entity_id
        builder.repository.upsert_entity.assert_called_once_with(
            "PERSON", "John Doe", "john_doe", {"info": "test"}, mock_conn
        )


class TestUpsertRelationship:
    """Test upsert_relationship method"""

    @pytest.mark.asyncio
    async def test_upsert_relationship_success(self):
        """Test: Successfully upserts relationship"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        mock_conn = AsyncMock()
        builder.repository.upsert_relationship = AsyncMock()

        await builder.upsert_relationship(
            source_id=1,
            target_id=2,
            rel_type="WORKS_AT",
            strength=0.9,
            evidence="John works at ABC",
            source_ref={"conversation_id": "conv123"},
            conn=mock_conn,
        )

        builder.repository.upsert_relationship.assert_called_once_with(
            1, 2, "WORKS_AT", 0.9, "John works at ABC", {"conversation_id": "conv123"}, mock_conn
        )


class TestProcessConversation:
    """Test process_conversation method"""

    @pytest.mark.asyncio
    async def test_process_conversation_success(self):
        """Test: Successfully processes conversation"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Setup transaction - transaction() must be a regular (non-async) callable
        mock_transaction = MagicMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        # Setup pool acquire using helper
        mock_pool.acquire.return_value = create_async_cm_mock(mock_conn)

        # Mock conversation data
        conversation_messages = [
            {"role": "user", "content": "Hello, I'm John Doe from ABC Corp"},
            {"role": "assistant", "content": "Nice to meet you, John!"},
        ]

        mock_conn.fetchrow.return_value = {
            "messages": json.dumps(conversation_messages),
            "client_id": "client123",
            "created_at": datetime.now(),
        }

        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Mock entity extraction
        mock_entities = [
            {"name": "John Doe", "type": "PERSON", "canonical_name": "john_doe"},
            {"name": "ABC Corp", "type": "ORGANIZATION", "canonical_name": "abc_corp"},
        ]
        builder.entity_extractor.extract_entities = AsyncMock(return_value=mock_entities)

        # Mock relationship extraction
        mock_relationships = [
            {"source": "John Doe", "target": "ABC Corp", "type": "WORKS_AT", "strength": 0.9}
        ]
        builder.relationship_extractor.extract_relationships = AsyncMock(
            return_value=mock_relationships
        )

        # Mock repository operations
        builder.repository.upsert_entity = AsyncMock(side_effect=[1, 2])
        builder.repository.upsert_relationship = AsyncMock()

        await builder.process_conversation("conv123")

        # Verify DB query was made
        mock_conn.fetchrow.assert_called_once()

        # Verify entities were extracted
        builder.entity_extractor.extract_entities.assert_called_once()

        # Verify relationships were extracted
        builder.relationship_extractor.extract_relationships.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_conversation_not_found(self):
        """Test: Handles conversation not found"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Setup transaction - transaction() must be a regular (non-async) callable
        mock_transaction = MagicMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        # Setup pool acquire using helper
        mock_pool.acquire.return_value = create_async_cm_mock(mock_conn)

        # Conversation not found
        mock_conn.fetchrow.return_value = None

        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Should not raise exception
        await builder.process_conversation("nonexistent")

        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_conversation_empty_id(self):
        """Test: Handles empty conversation_id"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Should return early without querying
        await builder.process_conversation("")

        # No DB calls should be made
        mock_pool.acquire.assert_not_called()


class TestBuildGraphFromAllConversations:
    """Test build_graph_from_all_conversations method"""

    @pytest.mark.asyncio
    async def test_build_graph_no_conversations(self):
        """Test: Handles case with no conversations"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Setup pool acquire
        pool_cm = MagicMock()
        pool_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        pool_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = pool_cm

        # No conversations
        mock_conn.fetch.return_value = []

        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Should not raise exception
        await builder.build_graph_from_all_conversations(days_back=30)

        mock_conn.fetch.assert_called_once()


class TestGetEntityInsights:
    """Test get_entity_insights method"""

    @pytest.mark.asyncio
    async def test_get_entity_insights_success(self):
        """Test: Successfully retrieves entity insights"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Setup pool acquire using helper
        mock_pool.acquire.return_value = create_async_cm_mock(mock_conn)

        # Mock top entities - must match actual SQL query fields
        mock_conn.fetch.side_effect = [
            # Top entities (type, name, mention_count)
            [
                {"type": "PERSON", "name": "john_doe", "mention_count": 10},
                {"type": "ORGANIZATION", "name": "abc_corp", "mention_count": 8},
            ],
            # Entity hubs (type, name, connection_count)
            [
                {"type": "PERSON", "name": "john_doe", "connection_count": 15},
            ],
            # Relationship types (relationship_type, count)
            [
                {"relationship_type": "WORKS_AT", "count": 5},
                {"relationship_type": "KNOWS", "count": 3},
            ],
        ]

        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        result = await builder.get_entity_insights(top_n=10)

        assert "top_entities" in result
        assert "hubs" in result
        assert "relationship_types" in result
        assert len(result["top_entities"]) == 2
        assert result["top_entities"][0]["name"] == "john_doe"


class TestErrorHandling:
    """Test error handling in various scenarios"""

    @pytest.mark.asyncio
    async def test_process_conversation_database_error(self):
        """Test: Handles database errors gracefully"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Setup pool acquire
        pool_cm = MagicMock()
        pool_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        pool_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = pool_cm

        # Setup transaction to raise error
        mock_conn.transaction.side_effect = Exception("Database error")

        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        # Should not raise exception - should log and return
        await builder.process_conversation("conv123")

    @pytest.mark.asyncio
    async def test_extract_entities_timeout(self):
        """Test: Handles entity extraction timeout"""
        mock_pool = MagicMock()
        builder = KnowledgeGraphBuilder(db_pool=mock_pool)

        import asyncio

        # Mock timeout
        builder.entity_extractor.extract_entities = AsyncMock(side_effect=asyncio.TimeoutError())

        # Should raise TimeoutError
        with pytest.raises(asyncio.TimeoutError):
            await builder.extract_entities_from_text("Some text", timeout=0.001)
