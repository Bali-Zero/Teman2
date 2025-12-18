"""
Comprehensive tests for services/golden_answer_service.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.golden_answer_service import GoldenAnswerService


class TestGoldenAnswerService:
    """Comprehensive test suite for GoldenAnswerService"""

    @pytest.fixture
    def mock_pool(self):
        """Mock asyncpg pool"""
        pool = AsyncMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        conn.fetchrow = AsyncMock()
        return pool, conn

    @pytest.fixture
    def service(self):
        """Create GoldenAnswerService instance"""
        return GoldenAnswerService(database_url="postgresql://test")

    def test_init(self, service):
        """Test GoldenAnswerService initialization"""
        assert service.database_url == "postgresql://test"
        assert service.similarity_threshold == 0.80
        assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect_success(self, service, mock_pool):
        """Test connect success"""
        pool, conn = mock_pool
        with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=pool):
            await service.connect()
            assert service.pool == pool

    @pytest.mark.asyncio
    async def test_connect_error(self, service):
        """Test connect error"""
        with patch("asyncpg.create_pool", new_callable=AsyncMock, side_effect=Exception("Error")):
            with pytest.raises(Exception):
                await service.connect()

    @pytest.mark.asyncio
    async def test_close(self, service, mock_pool):
        """Test close"""
        pool, conn = mock_pool
        service.pool = pool
        await service.close()
        pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_exact_match(self, service, mock_pool):
        """Test lookup_golden_answer with exact match"""
        pool, conn = mock_pool
        service.pool = pool
        conn.fetchrow.return_value = {
            "id": 1,
            "query": "test query",
            "answer": "test answer",
            "embedding": b"test",
        }
        service._load_model = MagicMock()
        service.model = MagicMock()
        service.model.encode = MagicMock(return_value=[[0.1, 0.2, 0.3]])

        result = await service.lookup_golden_answer("test query")
        assert result is not None

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_no_match(self, service, mock_pool):
        """Test lookup_golden_answer with no match"""
        pool, conn = mock_pool
        service.pool = pool
        conn.fetchrow.return_value = None
        service._load_model = MagicMock()
        service.model = MagicMock()
        service.model.encode = MagicMock(return_value=[[0.1, 0.2, 0.3]])

        result = await service.lookup_golden_answer("test query")
        assert result is None

    def test_load_model(self, service):
        """Test _load_model"""
        with patch("services.golden_answer_service.SentenceTransformer") as mock_st:
            service._load_model()
            assert service.model is not None
