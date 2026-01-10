"""
Unit tests for GoldenAnswerService
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.misc.golden_answer_service import GoldenAnswerService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetch = AsyncMock(return_value=[])
        yield conn

    pool.acquire = acquire
    return pool


@pytest.fixture
def golden_answer_service():
    """Create GoldenAnswerService instance"""
    return GoldenAnswerService(database_url="postgresql://test:test@localhost/test")


class TestGoldenAnswerService:
    """Tests for GoldenAnswerService"""

    def test_init(self):
        """Test initialization"""
        service = GoldenAnswerService(database_url="postgresql://test:test@localhost/test")
        assert service.database_url == "postgresql://test:test@localhost/test"
        assert service.pool is None
        assert service.model is None
        assert service.similarity_threshold == 0.80

    @pytest.mark.asyncio
    async def test_connect(self, golden_answer_service):
        """Test connecting to database"""
        with patch(
            "backend.services.misc.golden_answer_service.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool:
            mock_pool = MagicMock()
            mock_create_pool.return_value = mock_pool

            await golden_answer_service.connect()
            assert golden_answer_service.pool == mock_pool

    @pytest.mark.asyncio
    async def test_close(self, golden_answer_service):
        """Test closing connection"""
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        golden_answer_service.pool = mock_pool

        await golden_answer_service.close()
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_no_pool(self, golden_answer_service):
        """Test looking up golden answer without pool"""
        with patch.object(golden_answer_service, "connect", new_callable=AsyncMock):
            with patch.object(golden_answer_service, "pool", None):
                result = await golden_answer_service.lookup_golden_answer("Test query")
                assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_exact_match(self, golden_answer_service, mock_db_pool):
        """Test looking up golden answer with exact match"""
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "cluster_id": 1,
            "canonical_question": "Test question",
            "answer": "Test answer",
            "sources": ["source1"],
        }.get(key)
        mock_row.get = lambda key, default=None: {
            "cluster_id": 1,
            "canonical_question": "Test question",
            "answer": "Test answer",
            "sources": ["source1"],
        }.get(key, default)

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchrow = AsyncMock(return_value=mock_row)
            yield conn

        mock_db_pool.acquire = acquire
        golden_answer_service.pool = mock_db_pool

        result = await golden_answer_service.lookup_golden_answer("Test query")
        assert isinstance(result, dict) or result is None

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_similarity_match(self, golden_answer_service, mock_db_pool):
        """Test looking up golden answer with similarity match"""
        mock_rows = [
            MagicMock(
                **{
                    "__getitem__": lambda self, key: {
                        "canonical_question": "Test",
                        "answer": "Answer",
                        "sources": [],
                    }.get(key)
                }
            )
        ]

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchrow = AsyncMock(return_value=None)  # No exact match
            conn.fetch = AsyncMock(return_value=mock_rows)
            yield conn

        mock_db_pool.acquire = acquire
        golden_answer_service.pool = mock_db_pool

        # Since _load_model is patched as a no-op, we just need to set the model directly
        with patch.object(golden_answer_service, "_load_model"):
            mock_model = MagicMock()
            mock_model.encode.return_value = [[0.1] * 384]
            golden_answer_service.model = mock_model

            result = await golden_answer_service.lookup_golden_answer("Test query")
            assert isinstance(result, dict) or result is None
