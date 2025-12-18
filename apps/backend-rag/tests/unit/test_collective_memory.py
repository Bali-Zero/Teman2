"""
Unit Tests for CollectiveMemoryService
Tests the shared knowledge memory system
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCollectiveMemoryService:
    """Tests for CollectiveMemoryService"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock asyncpg pool"""
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock())
        return pool

    @pytest.fixture
    def service(self, mock_pool):
        """Create CollectiveMemoryService instance"""
        from services.collective_memory_service import CollectiveMemoryService

        return CollectiveMemoryService(pool=mock_pool)

    @pytest.fixture
    def service_no_pool(self):
        """Create CollectiveMemoryService without pool"""
        from services.collective_memory_service import CollectiveMemoryService

        return CollectiveMemoryService(pool=None)

    def test_init(self, service):
        """Test service initialization"""
        assert service.pool is not None
        assert service.PROMOTION_THRESHOLD == 3
        assert service.MAX_COLLECTIVE_CONTEXT == 10

    def test_init_no_pool(self, service_no_pool):
        """Test initialization without pool"""
        assert service_no_pool.pool is None

    def test_hash_content(self, service):
        """Test content hashing for deduplication"""
        content = "The PT PMA process takes 60-90 days"

        hash1 = service._hash_content(content)
        hash2 = service._hash_content(content.upper())  # Same content, different case
        hash3 = service._hash_content("  " + content + "  ")  # With whitespace

        # Should normalize and produce same hash
        assert hash1 == hash2
        assert hash1 == hash3
        assert len(hash1) == 64  # SHA256 produces 64 hex chars

    def test_hash_content_different(self, service):
        """Test that different content produces different hashes"""
        hash1 = service._hash_content("PT PMA takes 60 days")
        hash2 = service._hash_content("PT PMA takes 90 days")

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_add_contribution_no_pool(self, service_no_pool):
        """Test add_contribution without database"""
        result = await service_no_pool.add_contribution(
            user_id="test@example.com",
            content="Test fact",
            category="general",
        )

        assert result["status"] == "skipped"
        assert result["reason"] == "no_database"

    @pytest.mark.asyncio
    async def test_add_contribution_new_fact(self, service, mock_pool):
        """Test adding a new fact"""
        # Setup mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing fact
        mock_conn.fetchval = AsyncMock(return_value=1)  # New memory ID
        mock_conn.execute = AsyncMock()

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.add_contribution(
            user_id="test@example.com",
            content="PT PMA process takes 60-90 days",
            category="process",
        )

        assert result["status"] == "created"
        assert result["memory_id"] == 1
        assert result["source_count"] == 1
        assert result["is_promoted"] is False

    @pytest.mark.asyncio
    async def test_add_contribution_confirm_existing(self, service, mock_pool):
        """Test confirming an existing fact"""
        # Setup mock connection
        mock_conn = AsyncMock()
        # Existing fact found
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                {"id": 1, "source_count": 2, "is_promoted": False},  # First call - check existing
                {"source_count": 3, "is_promoted": True, "confidence": 0.8},  # After confirmation
            ]
        )
        mock_conn.fetchval = AsyncMock(return_value=False)  # User hasn't contributed yet
        mock_conn.execute = AsyncMock()

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.add_contribution(
            user_id="newuser@example.com",
            content="PT PMA process takes 60-90 days",
            category="process",
        )

        assert result["status"] == "confirmed"
        assert result["memory_id"] == 1
        assert result["source_count"] == 3
        assert result["is_promoted"] is True

    @pytest.mark.asyncio
    async def test_add_contribution_already_contributed(self, service, mock_pool):
        """Test that user can't contribute same fact twice"""
        # Setup mock connection
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={"id": 1, "source_count": 2, "is_promoted": False}
        )
        mock_conn.fetchval = AsyncMock(return_value=True)  # User already contributed

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.add_contribution(
            user_id="existing@example.com",
            content="PT PMA process takes 60-90 days",
            category="process",
        )

        assert result["status"] == "already_contributed"
        assert result["memory_id"] == 1

    @pytest.mark.asyncio
    async def test_get_collective_context_no_pool(self, service_no_pool):
        """Test get_collective_context without database"""
        result = await service_no_pool.get_collective_context()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_collective_context(self, service, mock_pool):
        """Test getting collective facts"""
        # Setup mock connection
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "content": "PT PMA process takes 60-90 days",
                    "confidence": 0.9,
                    "source_count": 5,
                },
                {"content": "KITAS visa requires sponsor", "confidence": 0.8, "source_count": 4},
            ]
        )

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.get_collective_context()

        assert len(result) == 2
        assert "PT PMA" in result[0]
        assert "KITAS" in result[1]

    @pytest.mark.asyncio
    async def test_get_collective_context_with_category(self, service, mock_pool):
        """Test getting collective facts filtered by category"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"content": "Notary X is fast", "confidence": 0.85, "source_count": 3},
            ]
        )

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.get_collective_context(category="provider")

        assert len(result) == 1
        assert "Notary" in result[0]

    @pytest.mark.asyncio
    async def test_refute_fact_no_pool(self, service_no_pool):
        """Test refute_fact without database"""
        result = await service_no_pool.refute_fact(
            user_id="test@example.com",
            memory_id=1,
        )
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_refute_fact_not_found(self, service, mock_pool):
        """Test refuting non-existent fact"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)  # Fact doesn't exist

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.refute_fact(
            user_id="test@example.com",
            memory_id=999,
        )

        assert result["status"] == "not_found"

    @pytest.mark.asyncio
    async def test_refute_fact_success(self, service, mock_pool):
        """Test successfully refuting a fact"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)  # Fact exists
        mock_conn.fetchrow = AsyncMock(return_value={"confidence": 0.5, "is_promoted": True})
        mock_conn.execute = AsyncMock()

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.refute_fact(
            user_id="test@example.com",
            memory_id=1,
        )

        assert result["status"] == "refuted"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_refute_fact_removes_low_confidence(self, service, mock_pool):
        """Test that low confidence facts are removed"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)
        mock_conn.fetchrow = AsyncMock(return_value={"confidence": 0.1, "is_promoted": False})
        mock_conn.execute = AsyncMock()

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.refute_fact(
            user_id="test@example.com",
            memory_id=1,
        )

        assert result["status"] == "removed"
        assert result["reason"] == "low_confidence"

    @pytest.mark.asyncio
    async def test_get_stats_no_pool(self, service_no_pool):
        """Test get_stats without database"""
        result = await service_no_pool.get_stats()
        assert result["status"] == "no_database"

    @pytest.mark.asyncio
    async def test_get_stats(self, service, mock_pool):
        """Test getting collective memory stats"""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[10, 5])  # total, promoted
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"category": "process", "count": 3},
                {"category": "location", "count": 2},
            ]
        )

        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await service.get_stats()

        assert result["total_facts"] == 10
        assert result["promoted_facts"] == 5
        assert result["pending_facts"] == 5
        assert result["by_category"]["process"] == 3
        assert result["by_category"]["location"] == 2


class TestCollectiveMemoryDataClass:
    """Tests for CollectiveMemory dataclass"""

    def test_collective_memory_to_dict(self):
        """Test CollectiveMemory serialization"""
        from datetime import datetime

        from services.collective_memory_service import CollectiveMemory

        memory = CollectiveMemory(
            id=1,
            content="Test fact",
            category="process",
            confidence=0.85,
            source_count=3,
            is_promoted=True,
            first_learned_at=datetime(2025, 1, 1, 12, 0, 0),
            last_confirmed_at=datetime(2025, 1, 15, 12, 0, 0),
            metadata={"source": "test"},
        )

        result = memory.to_dict()

        assert result["id"] == 1
        assert result["content"] == "Test fact"
        assert result["category"] == "process"
        assert result["confidence"] == 0.85
        assert result["source_count"] == 3
        assert result["is_promoted"] is True
        assert "2025-01-01" in result["first_learned_at"]


class TestMemoryContextWithCollective:
    """Tests for MemoryContext with collective facts"""

    def test_memory_context_with_collective_facts(self):
        """Test MemoryContext includes collective facts"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            profile_facts=["User is Roberto", "User is lawyer"],
            collective_facts=["PT PMA takes 60-90 days", "KITAS requires sponsor"],
            has_data=True,
        )

        assert len(context.profile_facts) == 2
        assert len(context.collective_facts) == 2
        assert not context.is_empty()

    def test_memory_context_to_system_prompt(self):
        """Test MemoryContext formatting as system prompt"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@example.com",
            profile_facts=["User is Roberto"],
            collective_facts=["PT PMA takes 60-90 days"],
            has_data=True,
        )

        prompt = context.to_system_prompt()

        assert "Collective Knowledge" in prompt
        assert "Personal Memory" in prompt
        assert "PT PMA" in prompt
        assert "Roberto" in prompt

    def test_memory_context_only_collective(self):
        """Test MemoryContext with only collective facts"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="new_user@example.com",
            profile_facts=[],
            collective_facts=["PT PMA takes 60-90 days"],
            has_data=False,  # Note: has_data is False, but collective_facts exist
        )

        # Should not be empty because collective facts exist (is_empty checks both)
        assert not context.is_empty()

        prompt = context.to_system_prompt()
        assert "Collective Knowledge" in prompt
        assert "PT PMA" in prompt


class TestQueryAwareRetrieval:
    """Tests for query-aware semantic retrieval"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock asyncpg pool"""
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=AsyncMock())
        return pool

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embeddings generator"""
        embedder = MagicMock()
        embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
        embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 1536)
        return embedder

    @pytest.fixture
    def mock_qdrant(self):
        """Create mock Qdrant client"""
        qdrant = AsyncMock()
        qdrant.search = AsyncMock(
            return_value={
                "documents": ["PT PMA takes 60-90 days", "KITAS requires sponsor"],
                "metadatas": [
                    {"id": 1, "confidence": 0.9, "is_promoted": True},
                    {"id": 2, "confidence": 0.8, "is_promoted": True},
                ],
                "distances": [0.1, 0.2],
            }
        )
        qdrant.create_collection = AsyncMock(return_value=True)
        qdrant.upsert_documents = AsyncMock(return_value={"success": True})
        return qdrant

    @pytest.mark.asyncio
    async def test_get_relevant_context_with_query(self, mock_pool, mock_embedder, mock_qdrant):
        """Test query-aware retrieval returns semantically relevant facts"""
        from services.collective_memory_service import CollectiveMemoryService

        service = CollectiveMemoryService(
            pool=mock_pool,
            embedder=mock_embedder,
            qdrant_client=mock_qdrant,
        )
        service._qdrant_initialized = True  # Skip collection creation

        result = await service.get_relevant_context(
            query="How long does PT PMA take?",
            limit=5,
        )

        assert len(result) == 2
        assert "PT PMA" in result[0]
        mock_embedder.generate_query_embedding.assert_called_once()
        mock_qdrant.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_relevant_context_fallback(self, mock_pool):
        """Test fallback to confidence-based when semantic search fails"""
        from services.collective_memory_service import CollectiveMemoryService

        # Setup mock connection for fallback
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"content": "Fallback fact 1", "confidence": 0.9, "source_count": 5},
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        service = CollectiveMemoryService(pool=mock_pool)
        # Mock embedder to raise an error (simulating failure)
        service._embedder = MagicMock()
        service._embedder.generate_query_embedding = MagicMock(side_effect=Exception("API error"))

        result = await service.get_relevant_context(
            query="Test query",
            limit=5,
        )

        # Should fallback to confidence-based retrieval
        assert len(result) == 1
        assert "Fallback fact 1" in result[0]

    @pytest.mark.asyncio
    async def test_sync_to_qdrant_on_creation(self, mock_pool, mock_embedder, mock_qdrant):
        """Test that new facts are synced to Qdrant"""
        from services.collective_memory_service import CollectiveMemoryService

        # Setup mock connection for new fact creation
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing fact
        mock_conn.fetchval = AsyncMock(return_value=1)  # New memory ID
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        service = CollectiveMemoryService(
            pool=mock_pool,
            embedder=mock_embedder,
            qdrant_client=mock_qdrant,
        )
        service._qdrant_initialized = True

        result = await service.add_contribution(
            user_id="test@example.com",
            content="New fact about taxes",
            category="tax",
        )

        assert result["status"] == "created"
        # Verify Qdrant upsert was called
        mock_qdrant.upsert_documents.assert_called_once()
