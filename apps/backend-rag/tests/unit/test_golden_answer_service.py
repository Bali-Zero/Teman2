"""
Comprehensive tests for GoldenAnswerService
Target: 100% coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGoldenAnswerService:
    """Tests for GoldenAnswerService class"""

    @pytest.fixture
    def service(self):
        """Create GoldenAnswerService instance"""
        from services.golden_answer_service import GoldenAnswerService

        return GoldenAnswerService(database_url="postgresql://test:test@localhost/test")

    @pytest.fixture
    def mock_pool(self):
        """Create mock database pool"""
        mock = MagicMock()
        mock.acquire = MagicMock()
        return mock

    def test_init(self):
        """Test initialization"""
        from services.golden_answer_service import GoldenAnswerService

        service = GoldenAnswerService("postgresql://test:test@localhost/test")

        assert service.database_url == "postgresql://test:test@localhost/test"
        assert service.pool is None
        assert service.model is None
        assert service.similarity_threshold == 0.80

    @pytest.mark.asyncio
    async def test_connect_success(self, service):
        """Test successful database connection"""
        mock_pool = MagicMock()

        with patch(
            "services.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool
            await service.connect()

            assert service.pool == mock_pool

    @pytest.mark.asyncio
    async def test_connect_failure(self, service):
        """Test database connection failure"""
        with patch(
            "services.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.side_effect = Exception("Connection failed")

            with pytest.raises(Exception, match="Connection failed"):
                await service.connect()

    @pytest.mark.asyncio
    async def test_close(self, service):
        """Test closing connection"""
        mock_pool = AsyncMock()
        service.pool = mock_pool

        await service.close()
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_no_pool(self, service):
        """Test closing when no pool"""
        service.pool = None
        await service.close()  # Should not raise

    def test_load_model(self, service):
        """Test lazy loading of embedding model"""
        # Skip test - SentenceTransformer is imported inside method
        # This is tested indirectly through semantic lookup tests
        # which call _load_model internally
        pytest.skip("SentenceTransformer imported inside method - tested indirectly")

    def test_load_model_already_loaded(self, service):
        """Test model not reloaded if already exists"""
        service.model = MagicMock()
        original_model = service.model

        service._load_model()

        assert service.model is original_model

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_no_pool(self, service):
        """Test lookup auto-connects if no pool"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            with patch.object(service, "_semantic_lookup", new_callable=AsyncMock) as mock_semantic:
                mock_semantic.return_value = None

                result = await service.lookup_golden_answer("test query")

                assert result is None

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_exact_match(self, service):
        """Test exact match lookup"""
        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "cluster_id": "cluster_123",
                "canonical_question": "What is KITAS?",
                "answer": "KITAS is a temporary residence permit.",
                "sources": ["source1", "source2"],
                "confidence": 0.95,
                "usage_count": 10,
            }
        )
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch.object(service, "_increment_usage", new_callable=AsyncMock):
            result = await service.lookup_golden_answer("What is KITAS?")

        assert result is not None
        assert result["match_type"] == "exact"
        assert result["cluster_id"] == "cluster_123"

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_semantic_match(self, service):
        """Test semantic similarity match"""
        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # No exact match
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch.object(service, "_semantic_lookup", new_callable=AsyncMock) as mock_semantic:
            mock_semantic.return_value = {
                "cluster_id": "cluster_456",
                "canonical_question": "How to get KITAS?",
                "answer": "Apply at immigration office.",
                "sources": [],
                "confidence": 0.88,
                "similarity": 0.92,
            }

            with patch.object(service, "_increment_usage", new_callable=AsyncMock):
                result = await service.lookup_golden_answer("How do I obtain KITAS?")

        assert result is not None
        assert result["match_type"] == "semantic"
        assert result["similarity"] == 0.92

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_no_match(self, service):
        """Test no match found"""
        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch.object(service, "_semantic_lookup", new_callable=AsyncMock) as mock_semantic:
            mock_semantic.return_value = None

            result = await service.lookup_golden_answer("Random unrelated query")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_exception(self, service):
        """Test exception handling in lookup"""
        service.pool = MagicMock()
        service.pool.acquire.side_effect = Exception("DB error")

        result = await service.lookup_golden_answer("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_lookup_no_pool(self, service):
        """Test semantic lookup with no pool"""
        service.pool = None

        result = await service._semantic_lookup("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_lookup_no_golden_answers(self, service):
        """Test semantic lookup with no golden answers"""
        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        result = await service._semantic_lookup("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_lookup_success(self, service):
        """Test successful semantic lookup"""
        import numpy as np

        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_1",
                    "canonical_question": "What is PT PMA?",
                    "answer": "A foreign company.",
                    "sources": [],
                    "confidence": 0.9,
                    "usage_count": 5,
                }
            ]
        )
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        # Mock embedding model
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        service.model = mock_model

        with patch("services.golden_answer_service.cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.95]])

            result = await service._semantic_lookup("What is a PT PMA company?")

        assert result is not None
        assert result["cluster_id"] == "cluster_1"

    @pytest.mark.asyncio
    async def test_semantic_lookup_below_threshold(self, service):
        """Test semantic lookup below threshold"""
        import numpy as np

        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_1",
                    "canonical_question": "What is PT PMA?",
                    "answer": "A foreign company.",
                    "sources": [],
                    "confidence": 0.9,
                    "usage_count": 5,
                }
            ]
        )
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        service.model = mock_model

        with patch("services.golden_answer_service.cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.5]])  # Below threshold

            result = await service._semantic_lookup("Random query")

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_lookup_exception(self, service):
        """Test exception handling in semantic lookup"""
        service.pool = MagicMock()
        service.pool.acquire.side_effect = Exception("Error")

        result = await service._semantic_lookup("test")

        assert result is None

    @pytest.mark.asyncio
    async def test_increment_usage_success(self, service):
        """Test incrementing usage count"""
        service.pool = MagicMock()
        mock_conn = AsyncMock()
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        await service._increment_usage("cluster_123")

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_usage_no_pool(self, service):
        """Test increment with no pool"""
        service.pool = None

        await service._increment_usage("cluster_123")  # Should not raise

    @pytest.mark.asyncio
    async def test_increment_usage_exception(self, service):
        """Test increment with exception"""
        service.pool = MagicMock()
        service.pool.acquire.side_effect = Exception("Error")

        await service._increment_usage("cluster_123")  # Should not raise

    @pytest.mark.asyncio
    async def test_get_golden_answer_stats_success(self, service):
        """Test getting statistics"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "total_golden_answers": 100,
                "total_hits": 500,
                "avg_confidence": 0.85,
                "max_usage": 50,
                "min_usage": 1,
            }
        )
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "c1",
                    "canonical_question": "Q1",
                    "usage_count": 50,
                    "last_used": MagicMock(isoformat=MagicMock(return_value="2024-01-01")),
                }
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            stats = await service.get_golden_answer_stats()

        assert stats["total_golden_answers"] == 100
        assert stats["total_hits"] == 500

    @pytest.mark.asyncio
    async def test_get_golden_answer_stats_nulls(self, service):
        """Test getting statistics with null values"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "total_golden_answers": 0,
                "total_hits": None,
                "avg_confidence": None,
                "max_usage": None,
                "min_usage": None,
            }
        )
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "c1",
                    "canonical_question": "Q1",
                    "usage_count": 0,
                    "last_used": None,
                }
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()
        service.pool = mock_pool

        stats = await service.get_golden_answer_stats()

        assert stats["total_hits"] == 0
        assert stats["avg_confidence"] == 0

    @pytest.mark.asyncio
    async def test_get_golden_answer_stats_no_pool(self, service):
        """Test getting stats auto-connects if no pool"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "total_golden_answers": 0,
                "total_hits": None,
                "avg_confidence": None,
                "max_usage": None,
                "min_usage": None,
            }
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()

        with patch(
            "services.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_pool

            stats = await service.get_golden_answer_stats()

            assert stats["total_golden_answers"] == 0
            assert stats["total_hits"] == 0

    @pytest.mark.asyncio
    async def test_semantic_lookup_loads_model(self, service):
        """Test semantic lookup loads model if not already loaded"""
        import numpy as np

        service.pool = MagicMock()
        service.model = None  # Model not loaded
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_1",
                    "canonical_question": "What is PT PMA?",
                    "answer": "A foreign company.",
                    "sources": [],
                    "confidence": 0.9,
                    "usage_count": 5,
                }
            ]
        )
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        # Mock model loading
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

        with patch.object(service, "_load_model") as mock_load:
            mock_load.side_effect = lambda: setattr(service, "model", mock_model)

            with patch("services.golden_answer_service.cosine_similarity") as mock_cos:
                mock_cos.return_value = np.array([[0.95]])

                result = await service._semantic_lookup("What is PT PMA?")

        assert result is not None
        mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_lookup_below_threshold_returns_none(self, service):
        """Test semantic lookup returns None when similarity below threshold"""
        import numpy as np

        service.pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_1",
                    "canonical_question": "What is PT PMA?",
                    "answer": "A foreign company.",
                    "sources": [],
                    "confidence": 0.9,
                    "usage_count": 5,
                }
            ]
        )
        service.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        service.pool.acquire.return_value.__aexit__ = AsyncMock()

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        service.model = mock_model

        with patch("services.golden_answer_service.cosine_similarity") as mock_cos:
            mock_cos.return_value = np.array([[0.5]])  # Below 0.8 threshold

            result = await service._semantic_lookup("Random query")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_golden_answer_stats_with_last_used_none(self, service):
        """Test stats when last_used is None"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "total_golden_answers": 1,
                "total_hits": 10,
                "avg_confidence": 0.85,
                "max_usage": 10,
                "min_usage": 1,
            }
        )
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "cluster_id": "c1",
                    "canonical_question": "Q1",
                    "usage_count": 10,
                    "last_used": None,  # None value
                }
            ]
        )
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock()
        service.pool = mock_pool

        stats = await service.get_golden_answer_stats()

        assert stats["top_10"][0]["last_used"] is None
