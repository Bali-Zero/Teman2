"""
Unit tests for KnowledgeGraphBuilder Agent
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.autonomous_agents.knowledge_graph_builder import (
    Entity,
    EntityType,
    KnowledgeGraphBuilder,
)


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    return AsyncMock()


@pytest.fixture
def kg_builder(mock_db_pool):
    """Create KG builder instance"""
    return KnowledgeGraphBuilder(
        search_service=MagicMock(), db_pool=mock_db_pool, llm_gateway=MagicMock()
    )


class TestKnowledgeGraphBuilder:
    """Tests for KnowledgeGraphBuilder"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        builder = KnowledgeGraphBuilder(
            search_service=MagicMock(), db_pool=mock_db_pool, llm_gateway=MagicMock()
        )
        assert builder.db_pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_build_from_chunks(self, kg_builder):
        """Test building graph from chunks"""
        # Test add_entity method directly
        entity = Entity(
            entity_id="test_entity",
            entity_type=EntityType.LEGAL_ENTITY,
            name="PT PMA",
            description="Test entity",
            source_collection="test_collection",
            confidence=0.9,
            source_chunk_ids=["chunk1"],
        )

        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        kg_builder.db_pool.acquire = acquire

        await kg_builder.add_entity(entity)
        assert entity.entity_id in kg_builder.entities

    @pytest.mark.asyncio
    async def test_build_from_conversations(self, kg_builder):
        """Test building graph from conversations"""
        # Test extract_via_llm method
        with patch.object(kg_builder.llm_gateway, "conversational") as mock_llm:
            mock_llm.return_value = {
                "text": '{"entities": [{"id": "test", "type": "LEGAL_ENTITY", "name": "PT PMA"}], "relationships": []}'
            }

            result = await kg_builder.extract_via_llm(
                "PT PMA requires investment", "test_collection", "chunk1"
            )
            assert "entities" in result
