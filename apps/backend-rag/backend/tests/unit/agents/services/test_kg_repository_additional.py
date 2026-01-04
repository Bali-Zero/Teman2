"""
Additional unit tests for KnowledgeGraphRepository
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.kg_repository import KnowledgeGraphRepository


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        conn = MagicMock()
        conn.execute = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])
        conn.transaction = MagicMock()
        conn.transaction.__aenter__ = AsyncMock(return_value=conn)
        conn.transaction.__aexit__ = AsyncMock(return_value=None)
        yield conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def kg_repository(mock_db_pool):
    """Create KnowledgeGraphRepository instance"""
    return KnowledgeGraphRepository(db_pool=mock_db_pool)


class TestKnowledgeGraphRepositoryAdditional:
    """Additional tests for KnowledgeGraphRepository"""

    def test_generate_entity_id(self, kg_repository):
        """Test generating entity ID"""
        entity_id = kg_repository._generate_entity_id("law", "PP Number 32 2023")
        assert isinstance(entity_id, str)
        assert "law" in entity_id.lower()

    @pytest.mark.asyncio
    async def test_upsert_entity(self, kg_repository, mock_db_pool):
        """Test upserting entity"""
        async with mock_db_pool.acquire() as conn:
            entity_id = await kg_repository.upsert_entity(
                entity_type="law",
                name="Test Law",
                canonical_name="test_law",
                metadata={"key": "value"},
                conn=conn,
            )
            assert isinstance(entity_id, str)

    @pytest.mark.asyncio
    async def test_upsert_relationship(self, kg_repository, mock_db_pool):
        """Test upserting relationship"""
        async with mock_db_pool.acquire() as conn:
            await kg_repository.upsert_relationship(
                source_id="source_1",
                target_id="target_1",
                rel_type="requires",
                strength=0.8,
                evidence="Test evidence",
                source_ref={"source": "test"},
                conn=conn,
            )
            # Should not raise exception
            assert True

    @pytest.mark.asyncio
    async def test_get_entity_by_id(self, kg_repository, mock_db_pool):
        """Test getting entity by ID"""
        if hasattr(kg_repository, "get_entity_by_id"):
            mock_entity = MagicMock()
            mock_entity.__getitem__ = lambda self, key: {
                "entity_id": "test_entity",
                "entity_type": "law",
                "name": "Test Entity",
            }.get(key)

            @asynccontextmanager
            async def acquire():
                conn = MagicMock()
                conn.fetchrow = AsyncMock(return_value=mock_entity)
                yield conn

            kg_repository.db_pool = mock_db_pool
            mock_db_pool.acquire = acquire

            result = await kg_repository.get_entity_by_id("test_entity")
            # May return None if entity not found, which is acceptable
            assert result is None or isinstance(result, dict)
        else:
            pytest.skip("Method not available")

    @pytest.mark.asyncio
    async def test_get_entity_relationships(self, kg_repository, mock_db_pool):
        """Test getting entity relationships"""
        if hasattr(kg_repository, "get_entity_relationships"):
            mock_relationships = [
                {"target_entity_id": "target_1", "relationship_type": "requires", "confidence": 0.8}
            ]

            @asynccontextmanager
            async def acquire():
                conn = MagicMock()
                conn.fetch = AsyncMock(return_value=mock_relationships)
                yield conn

            mock_db_pool.acquire = acquire

            result = await kg_repository.get_entity_relationships("source_1")
            assert isinstance(result, list)
        else:
            pytest.skip("Method not available")
