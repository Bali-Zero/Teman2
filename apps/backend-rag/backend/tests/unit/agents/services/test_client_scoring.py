"""
Unit tests for ClientScoringService
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from agents.services.client_scoring import ClientScoringService


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
def client_scoring_service(mock_db_pool):
    """Create ClientScoringService instance"""
    return ClientScoringService(db_pool=mock_db_pool)


class TestClientScoringService:
    """Tests for ClientScoringService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = ClientScoringService(db_pool=mock_db_pool)
        assert service.db_pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_calculate_client_score(self, client_scoring_service, mock_db_pool):
        """Test calculating client score"""
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "name": "Test Client",
            "email": "test@example.com",
            "phone": "+1234567890",
            "created_at": datetime.now() - timedelta(days=100),
            "interaction_count": 10,
            "avg_sentiment": 0.75,
            "recent_interactions": 5,
            "last_interaction": datetime.now() - timedelta(days=5),
            "conversation_count": 8,
            "avg_rating": 4.5,
            "practice_statuses": ["active", "pending"],
            "practice_count": 2
        }.get(key)
        mock_row.get = lambda key, default=None: {
            "name": "Test Client",
            "email": "test@example.com",
            "phone": "+1234567890",
            "created_at": datetime.now() - timedelta(days=100),
            "interaction_count": 10,
            "avg_sentiment": 0.75,
            "recent_interactions": 5,
            "last_interaction": datetime.now() - timedelta(days=5),
            "conversation_count": 8,
            "avg_rating": 4.5,
            "practice_statuses": ["active", "pending"],
            "practice_count": 2
        }.get(key, default)

        async with mock_db_pool.acquire() as conn:
            conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_db_pool.acquire = lambda: mock_db_pool.acquire()

        # Patch the acquire method properly
        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchrow = AsyncMock(return_value=mock_row)
            yield conn

        mock_db_pool.acquire = acquire

        result = await client_scoring_service.calculate_client_score("123")
        assert result is not None
        assert "ltv_score" in result
        assert "client_id" in result

    @pytest.mark.asyncio
    async def test_calculate_client_score_empty_id(self, client_scoring_service):
        """Test calculating client score with empty ID"""
        result = await client_scoring_service.calculate_client_score("")
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_not_found(self, client_scoring_service, mock_db_pool):
        """Test calculating client score when client not found"""
        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchrow = AsyncMock(return_value=None)
            yield conn

        mock_db_pool.acquire = acquire

        result = await client_scoring_service.calculate_client_score("999")
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_db_error(self, client_scoring_service, mock_db_pool):
        """Test calculating client score with database error"""
        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
            yield conn

        mock_db_pool.acquire = acquire

        result = await client_scoring_service.calculate_client_score("123")
        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_scores_batch(self, client_scoring_service, mock_db_pool):
        """Test calculating scores in batch"""
        mock_rows = [
            MagicMock(**{"__getitem__": lambda self, key: {"id": "1"}.get(key)}),
            MagicMock(**{"__getitem__": lambda self, key: {"id": "2"}.get(key)})
        ]

        @asynccontextmanager
        async def acquire():
            conn = MagicMock()
            conn.fetch = AsyncMock(return_value=mock_rows)
            yield conn

        mock_db_pool.acquire = acquire

        result = await client_scoring_service.calculate_scores_batch(["1", "2"])
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_empty(self, client_scoring_service):
        """Test calculating scores batch with empty list"""
        result = await client_scoring_service.calculate_scores_batch([])
        assert result == {}




