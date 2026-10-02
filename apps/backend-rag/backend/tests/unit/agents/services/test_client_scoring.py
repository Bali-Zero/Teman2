"""
Unit tests for ClientScoringService
Target: >95% coverage
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.agents.services.client_scoring import ClientScoringService


class FakeRow(dict[str, Any]):
    """Small mapping with asyncpg.Record-like indexing for unit tests."""


def make_row(**overrides: Any) -> FakeRow:
    now = datetime.now(tz=timezone.utc)
    row = FakeRow(
        {
            "client_id": "123",
            "name": "Synthetic Client",
            "email": "client@example.invalid",
            "phone": "+620000000000",
            "created_at": now - timedelta(days=100),
            "interaction_count": 10,
            "avg_sentiment": 0.75,
            "recent_interactions": 5,
            "last_interaction": now - timedelta(days=5),
            "conversation_count": 8,
            "avg_rating": 4.5,
            "practice_statuses": ["active", "pending"],
            "practice_count": 2,
        }
    )
    row.update(overrides)
    return row


def set_pool_fetchrow(
    pool: MagicMock,
    *,
    row: FakeRow | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    fetchrow = AsyncMock(side_effect=side_effect) if side_effect else AsyncMock(return_value=row)

    @asynccontextmanager
    async def acquire() -> AsyncIterator[MagicMock]:
        conn = MagicMock()
        conn.fetchrow = fetchrow
        yield conn

    pool.acquire = acquire
    return fetchrow


def set_pool_fetch(
    pool: MagicMock,
    *,
    rows: list[FakeRow] | None = None,
    side_effect: Exception | None = None,
) -> AsyncMock:
    fetch = AsyncMock(side_effect=side_effect) if side_effect else AsyncMock(return_value=rows or [])

    @asynccontextmanager
    async def acquire() -> AsyncIterator[MagicMock]:
        conn = MagicMock()
        conn.fetch = fetch
        yield conn

    pool.acquire = acquire
    return fetch


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
            "created_at": datetime.now(tz=timezone.utc) - timedelta(days=100),
            "interaction_count": 10,
            "avg_sentiment": 0.75,
            "recent_interactions": 5,
            "last_interaction": datetime.now(tz=timezone.utc) - timedelta(days=5),
            "conversation_count": 8,
            "avg_rating": 4.5,
            "practice_statuses": ["active", "pending"],
            "practice_count": 2,
        }.get(key)
        mock_row.get = lambda key, default=None: {
            "name": "Test Client",
            "email": "test@example.com",
            "phone": "+1234567890",
            "created_at": datetime.now(tz=timezone.utc) - timedelta(days=100),
            "interaction_count": 10,
            "avg_sentiment": 0.75,
            "recent_interactions": 5,
            "last_interaction": datetime.now(tz=timezone.utc) - timedelta(days=5),
            "conversation_count": 8,
            "avg_rating": 4.5,
            "practice_statuses": ["active", "pending"],
            "practice_count": 2,
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
        set_pool_fetch(
            mock_db_pool,
            rows=[
                make_row(client_id="1", interaction_count=1),
                make_row(client_id="2", interaction_count=20),
            ],
        )

        result = await client_scoring_service.calculate_scores_batch(["1", "2"])
        assert set(result) == {"1", "2"}
        assert result["1"]["client_id"] == "1"
        assert result["2"]["engagement_score"] == 100

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_empty(self, client_scoring_service):
        """Test calculating scores batch with empty list"""
        result = await client_scoring_service.calculate_scores_batch([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_calculate_client_score_invalid_id_returns_none(
        self,
        client_scoring_service: ClientScoringService,
        mock_db_pool: MagicMock,
    ) -> None:
        """Non-numeric ids are rejected by the guarded unexpected-error path."""
        fetchrow = set_pool_fetchrow(mock_db_pool, row=make_row())

        result = await client_scoring_service.calculate_client_score("not-an-int")

        assert result is None
        fetchrow.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_client_score_handles_asyncpg_error(
        self,
        client_scoring_service: ClientScoringService,
        mock_db_pool: MagicMock,
    ) -> None:
        """Database-specific asyncpg errors return None instead of escaping."""
        set_pool_fetchrow(mock_db_pool, side_effect=asyncpg.PostgresError("boom"))

        result = await client_scoring_service.calculate_client_score("123")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_invalid_id_returns_empty(
        self,
        client_scoring_service: ClientScoringService,
        mock_db_pool: MagicMock,
    ) -> None:
        """Batch conversion failures are contained and do not query partial ids."""
        fetch = set_pool_fetch(mock_db_pool, rows=[make_row(client_id="1")])

        result = await client_scoring_service.calculate_scores_batch(["1", "bad"])

        assert result == {}
        fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_handles_asyncpg_error(
        self,
        client_scoring_service: ClientScoringService,
        mock_db_pool: MagicMock,
    ) -> None:
        """Batch database errors degrade to an empty result."""
        set_pool_fetch(mock_db_pool, side_effect=asyncpg.InterfaceError("connection closed"))

        result = await client_scoring_service.calculate_scores_batch(["1", "2"])

        assert result == {}

    def test_calculate_scores_from_row_applies_caps_and_defaults(
        self,
        client_scoring_service: ClientScoringService,
    ) -> None:
        """Score components cap at 100 and nullable aggregates fall back safely."""
        row = make_row(
            interaction_count=50,
            avg_sentiment=None,
            recent_interactions=20,
            avg_rating=None,
            practice_count=10,
            last_interaction=None,
            conversation_count=None,
            practice_statuses=None,
        )

        result = client_scoring_service._calculate_scores_from_row(row, "123")

        assert result["engagement_score"] == 100
        assert result["sentiment_score"] == 50
        assert result["recency_score"] == 100
        assert result["quality_score"] == 0
        assert result["practice_score"] == 100
        assert result["days_since_last_interaction"] == 999
        assert result["total_conversations"] == 0
        assert result["practice_statuses"] == []

    def test_calculate_scores_from_row_accepts_naive_datetime(
        self,
        client_scoring_service: ClientScoringService,
    ) -> None:
        naive_last_interaction = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(
            days=3
        )

        result = client_scoring_service._calculate_scores_from_row(
            make_row(last_interaction=naive_last_interaction),
            "123",
        )

        assert result["days_since_last_interaction"] >= 3
