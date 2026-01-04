"""
Unit tests for CollectiveMemoryService
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

from services.memory.collective_memory_service import CollectiveMemory, CollectiveMemoryService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    return pool


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=[0.1] * 1536)
    return embedder


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant client"""
    client = MagicMock()
    client.search = AsyncMock(return_value=[])
    client.upsert = AsyncMock()
    return client


@pytest.fixture
def collective_memory_service(mock_db_pool, mock_embedder, mock_qdrant):
    """Create collective memory service instance"""
    return CollectiveMemoryService(
        pool=mock_db_pool, embedder=mock_embedder, qdrant_client=mock_qdrant
    )


class TestCollectiveMemoryService:
    """Tests for CollectiveMemoryService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = CollectiveMemoryService(pool=mock_db_pool)
        assert service.pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_contribute_fact(self, collective_memory_service, mock_db_pool):
        """Test contributing a fact"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        collective_memory_service.pool = mock_db_pool
        mock_db_pool.acquire = acquire
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing fact
        mock_conn.fetchval = AsyncMock(return_value=1)  # New memory ID
        mock_conn.execute = AsyncMock()

        result = await collective_memory_service.add_contribution(
            user_id="test@example.com", content="KITAS costs 15M", category="pricing"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_contribute_fact_promotion(self, collective_memory_service, mock_db_pool):
        """Test fact promotion when threshold reached"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        collective_memory_service.pool = mock_db_pool
        mock_db_pool.acquire = acquire
        mock_conn.fetchrow = AsyncMock(
            return_value={"id": 1, "source_count": 2, "is_promoted": False}
        )
        mock_conn.fetchval = AsyncMock(return_value=3)  # 3 sources = promotion threshold
        mock_conn.execute = AsyncMock()

        result = await collective_memory_service.add_contribution(
            user_id="test@example.com", content="KITAS costs 15M", category="pricing"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_refute_fact(self, collective_memory_service, mock_db_pool):
        """Test refuting a fact"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "confidence": 0.5})
        mock_conn.execute = AsyncMock()

        result = await collective_memory_service.refute_fact(
            user_id="test@example.com", memory_id=1, reason="Incorrect information"
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_promoted_facts(self, collective_memory_service, mock_db_pool):
        """Test getting promoted facts"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetch = AsyncMock(
            return_value=[{"content": "Fact 1", "confidence": 0.9, "source_count": 3}]
        )

        # Use get_collective_context which returns promoted facts
        facts = await collective_memory_service.get_collective_context(category="pricing", limit=10)
        assert len(facts) > 0

    @pytest.mark.asyncio
    async def test_search_facts(self, collective_memory_service):
        """Test semantic search for facts"""
        with (
            patch.object(collective_memory_service, "_get_embedder") as mock_get_embedder,
            patch.object(collective_memory_service, "_get_qdrant") as mock_get_qdrant,
        ):
            mock_embedder = MagicMock()
            mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_get_embedder.return_value = mock_embedder

            mock_qdrant = MagicMock()
            mock_qdrant.search = AsyncMock(
                return_value={"documents": [["test fact"]], "metadatas": [{"confidence": 0.9}]}
            )
            mock_get_qdrant.return_value = mock_qdrant

            results = await collective_memory_service.get_relevant_context("test query", limit=5)
            assert results is not None


class TestCollectiveMemory:
    """Tests for CollectiveMemory dataclass"""

    def test_to_dict(self):
        """Test conversion to dict"""
        from datetime import datetime

        memory = CollectiveMemory(
            id=1,
            content="test",
            category="pricing",
            confidence=0.9,
            source_count=3,
            is_promoted=True,
            first_learned_at=datetime.now(),
            last_confirmed_at=datetime.now(),
            metadata={},
        )

        result = memory.to_dict()
        assert result["id"] == 1
        assert result["content"] == "test"
        assert result["is_promoted"] is True

    @pytest.mark.asyncio
    async def test_set_pool(self, collective_memory_service, mock_db_pool):
        """Test setting pool"""
        collective_memory_service.set_pool(mock_db_pool)
        assert collective_memory_service.pool == mock_db_pool

    def test_get_embedder(self, collective_memory_service):
        """Test getting embedder"""
        # Reset embedder to None to force initialization
        collective_memory_service._embedder = None
        with patch("core.embeddings.create_embeddings_generator") as mock_create:
            mock_embedder = MagicMock()
            mock_create.return_value = mock_embedder
            embedder = collective_memory_service._get_embedder()
            assert embedder is not None
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_qdrant(self, collective_memory_service):
        """Test getting Qdrant client"""
        # Reset qdrant to None to force initialization
        collective_memory_service._qdrant = None
        collective_memory_service._qdrant_initialized = False
        with (
            patch("core.qdrant_db.QdrantClient") as mock_qdrant_class,
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.qdrant_url = "http://localhost:6333"
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.create_collection = AsyncMock()
            mock_qdrant_class.return_value = mock_qdrant_instance

            qdrant = await collective_memory_service._get_qdrant()
            assert qdrant is not None
            mock_qdrant_class.assert_called()

    def test_hash_content(self):
        """Test content hashing"""
        hash1 = CollectiveMemoryService._hash_content("test content")
        hash2 = CollectiveMemoryService._hash_content("test content")
        hash3 = CollectiveMemoryService._hash_content("different content")

        assert hash1 == hash2  # Same content = same hash
        assert hash1 != hash3  # Different content = different hash

    @pytest.mark.asyncio
    async def test_get_all_memories(self, collective_memory_service, mock_db_pool):
        """Test getting all memories"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "content": "Fact 1",
                    "category": "pricing",
                    "confidence": 0.9,
                    "source_count": 3,
                    "is_promoted": True,
                    "first_learned_at": None,
                    "last_confirmed_at": None,
                    "metadata": {},
                },
            ]
        )

        memories = await collective_memory_service.get_all_memories(limit=10)
        assert len(memories) > 0

    @pytest.mark.asyncio
    async def test_get_memory_sources(self, collective_memory_service, mock_db_pool):
        """Test getting memory sources"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"user_id": "user1@example.com", "action": "contribute", "created_at": None}
            ]
        )

        sources = await collective_memory_service.get_memory_sources(1)
        assert len(sources) > 0

    @pytest.mark.asyncio
    async def test_search_similar(self, collective_memory_service, mock_db_pool):
        """Test search for similar memories (ILIKE search)"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "content": "test fact",
                    "category": "pricing",
                    "confidence": 0.9,
                    "source_count": 3,
                    "is_promoted": True,
                    "first_learned_at": None,
                    "last_confirmed_at": None,
                    "metadata": {},
                }
            ]
        )

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        collective_memory_service.pool = mock_db_pool
        mock_db_pool.acquire = acquire

        results = await collective_memory_service.search_similar("test", limit=5)
        assert len(results) > 0
        assert results[0].content == "test fact"

    @pytest.mark.asyncio
    async def test_get_stats(self, collective_memory_service, mock_db_pool):
        """Test getting service stats"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        collective_memory_service.pool = mock_db_pool
        mock_db_pool.acquire = acquire
        mock_conn.fetchval = AsyncMock(side_effect=[10, 5])  # total, promoted
        mock_conn.fetch = AsyncMock(return_value=[])

        stats = await collective_memory_service.get_stats()
        assert isinstance(stats, dict)
        assert "total_facts" in stats
        assert stats["total_facts"] == 10

    @pytest.mark.asyncio
    async def test_sync_to_qdrant(self, collective_memory_service, mock_db_pool):
        """Test syncing memory to Qdrant"""
        from contextlib import asynccontextmanager

        with (
            patch.object(collective_memory_service, "_get_embedder") as mock_get_embedder,
            patch.object(collective_memory_service, "_get_qdrant") as mock_get_qdrant,
        ):
            mock_embedder = MagicMock()
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
            mock_get_embedder.return_value = mock_embedder

            mock_qdrant = MagicMock()
            mock_qdrant.upsert_documents = AsyncMock(return_value={"success": True})
            mock_get_qdrant.return_value = mock_qdrant

            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()

            @asynccontextmanager
            async def acquire():
                yield mock_conn

            collective_memory_service.pool = mock_db_pool
            mock_db_pool.acquire = acquire

            result = await collective_memory_service._sync_to_qdrant(1, "test content", "pricing")
            assert result is True

    @pytest.mark.asyncio
    async def test_refute_fact_not_found(self, collective_memory_service, mock_db_pool):
        """Test refuting non-existent fact"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetchval = AsyncMock(return_value=False)  # Fact doesn't exist

        result = await collective_memory_service.refute_fact("user@example.com", 999, "Wrong")
        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_refute_fact_low_confidence_removal(
        self, collective_memory_service, mock_db_pool
    ):
        """Test fact removal when confidence too low"""
        from contextlib import asynccontextmanager

        mock_conn = AsyncMock()

        @asynccontextmanager
        async def acquire():
            yield mock_conn

        mock_db_pool.acquire = acquire
        mock_conn.fetchval = AsyncMock(return_value=True)  # Fact exists
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"confidence": 0.1, "is_promoted": False}
        )  # Low confidence

        result = await collective_memory_service.refute_fact("user@example.com", 1, "Wrong")
        assert result["status"] == "removed"
