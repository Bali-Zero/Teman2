"""
Unit tests for KnowledgeGraphRepository
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.services.kg_repository import KnowledgeGraphRepository


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


@pytest.fixture
def kg_repository(mock_db_pool):
    """Create KG repository instance"""
    return KnowledgeGraphRepository(db_pool=mock_db_pool)


class TestKnowledgeGraphRepository:
    """Tests for KnowledgeGraphRepository"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        repo = KnowledgeGraphRepository(db_pool=mock_db_pool)
        assert repo.db_pool == mock_db_pool

    def test_generate_entity_id(self, kg_repository):
        """Test entity ID generation"""
        entity_id = kg_repository._generate_entity_id("law", "PP Number 32")
        assert "law" in entity_id.lower()
        assert "pp" in entity_id.lower()

    @pytest.mark.asyncio
    async def test_upsert_entity(self, kg_repository):
        """Test upserting entity"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        entity_id = await kg_repository.upsert_entity(
            entity_type="law",
            name="PP 32",
            canonical_name="PP Number 32",
            metadata={"year": 2023},
            conn=mock_conn,
        )

        assert entity_id is not None
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_entity_with_source_chunk(self, kg_repository):
        """Test upserting entity with source chunk"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        entity_id = await kg_repository.upsert_entity(
            entity_type="law",
            name="PP 32",
            canonical_name="PP Number 32",
            metadata={},
            conn=mock_conn,
            source_chunk_id="chunk_123",
        )

        assert entity_id is not None

    @pytest.mark.asyncio
    async def test_upsert_relation(self, kg_repository):
        """Test upserting relation"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        kg_repository.db_pool.acquire = acquire

        await kg_repository.upsert_relationship(
            source_id="entity1",
            target_id="entity2",
            rel_type="REQUIRES",
            strength=0.9,
            evidence="requires",
            source_ref={},
            conn=mock_conn,
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_entity(self, kg_repository):
        """Test getting entity"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "entity_id": "test_id",
                "entity_type": "law",
                "name": "Test",
                "description": None,
                "properties": {},
                "confidence": 1.0,
                "source_collection": None,
                "source_chunk_ids": [],
                "created_at": None,
                "updated_at": None,
            }
        )

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        kg_repository.db_pool.acquire = acquire

        entity = await kg_repository.get_entity_by_id("test_id")
        assert entity is not None

    @pytest.mark.asyncio
    async def test_traverse_graph(self, kg_repository):
        """Test graph traversal"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "relationship_id": "rel1",
                    "relationship_type": "REQUIRES",
                    "confidence": 0.9,
                    "properties": {},
                    "source_chunk_ids": [],
                    "direction": "outgoing",
                    "connected_entity_id": "entity2",
                    "connected_entity_name": "Entity 2",
                    "connected_entity_type": "Organization",
                }
            ]
        )

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        kg_repository.db_pool.acquire = acquire

        neighbors = await kg_repository.get_entity_relationships(entity_id="entity1", limit=20)

        assert isinstance(neighbors, list)
