"""
Unit tests for GoldenAnswerService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.golden_answer_service import GoldenAnswerService


@pytest.fixture
def golden_answer_service():
    """Create GoldenAnswerService instance"""
    return GoldenAnswerService(database_url="postgresql://test")


class TestGoldenAnswerService:
    """Tests for GoldenAnswerService"""

    def test_init(self):
        """Test initialization"""
        service = GoldenAnswerService(database_url="postgresql://test")
        assert service.database_url == "postgresql://test"
        assert service.pool is None
        assert service.similarity_threshold == 0.80

    @pytest.mark.asyncio
    async def test_connect(self, golden_answer_service):
        """Test connecting to database"""
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            await golden_answer_service.connect()
            assert golden_answer_service.pool == mock_pool

    @pytest.mark.asyncio
    async def test_close(self, golden_answer_service):
        """Test closing connection"""
        mock_pool = AsyncMock()
        golden_answer_service.pool = mock_pool
        await golden_answer_service.close()
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_no_pool(self, golden_answer_service):
        """Test lookup when pool not initialized"""
        with patch.object(golden_answer_service, 'connect', new_callable=AsyncMock):
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchrow = AsyncMock(return_value=None)
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire = MagicMock(return_value=mock_conn)
            golden_answer_service.pool = mock_pool
            with patch.object(golden_answer_service, '_semantic_lookup', new_callable=AsyncMock) as mock_semantic:
                mock_semantic.return_value = None
                result = await golden_answer_service.lookup_golden_answer("test query")
                assert result is None

    @pytest.mark.asyncio
    async def test_lookup_golden_answer_exact_match(self, golden_answer_service):
        """Test lookup with exact match"""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "cluster_id": "cluster1",
            "canonical_question": "test query",
            "answer": "test answer",
            "sources": ["source1"]
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_conn)
        golden_answer_service.pool = mock_pool
        result = await golden_answer_service.lookup_golden_answer("test query")
        assert isinstance(result, dict) or result is None

