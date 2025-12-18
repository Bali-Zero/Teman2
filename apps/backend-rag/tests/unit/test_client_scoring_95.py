"""
Unit Tests for agents/services/client_scoring.py - 95% Coverage Target
Tests the ClientScoringService class
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test ClientScoringService initialization
# ============================================================================


class TestClientScoringServiceInit:
    """Test suite for ClientScoringService initialization"""

    def test_init_with_db_pool(self):
        """Test initialization with database pool"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        assert service.db_pool == mock_pool


# ============================================================================
# Test calculate_client_score
# ============================================================================


class TestCalculateClientScore:
    """Test suite for calculate_client_score method"""

    @pytest.mark.asyncio
    async def test_calculate_client_score_success(self):
        """Test successful score calculation"""
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "name": "Test Client",
                "email": "test@example.com",
                "phone": "+1234567890",
                "created_at": datetime.now() - timedelta(days=365),
                "interaction_count": 10,
                "avg_sentiment": 0.5,
                "recent_interactions": 5,
                "last_interaction": datetime.now() - timedelta(days=5),
                "conversation_count": 8,
                "avg_rating": 4.5,
                "practice_statuses": ["active", "completed"],
                "practice_count": 3,
            }
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_client_score("123")

        assert result is not None
        assert result["client_id"] == "123"
        assert result["name"] == "Test Client"
        assert "ltv_score" in result
        assert "engagement_score" in result

    @pytest.mark.asyncio
    async def test_calculate_client_score_empty_client_id(self):
        """Test with empty client ID"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        result = await service.calculate_client_score("")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_none_client_id(self):
        """Test with None client ID"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        result = await service.calculate_client_score(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_not_found(self):
        """Test when client not found"""
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_client_score("999")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_postgres_error(self):
        """Test PostgreSQL error handling"""
        import asyncpg
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=asyncpg.PostgresError("Connection error"))

        # Use AsyncMock for the context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_cm.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_client_score("123")

        assert result is None

    @pytest.mark.asyncio
    async def test_calculate_client_score_generic_error(self):
        """Test generic error handling"""
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("Unexpected error"))

        # Use AsyncMock for the context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_cm.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_client_score("123")

        assert result is None


# ============================================================================
# Test calculate_scores_batch
# ============================================================================


class TestCalculateScoresBatch:
    """Test suite for calculate_scores_batch method"""

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_success(self):
        """Test successful batch score calculation"""
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "client_id": "1",
                    "name": "Client 1",
                    "email": "client1@example.com",
                    "phone": "+1111111111",
                    "created_at": datetime.now() - timedelta(days=100),
                    "interaction_count": 5,
                    "avg_sentiment": 0.3,
                    "recent_interactions": 2,
                    "last_interaction": datetime.now() - timedelta(days=10),
                    "conversation_count": 3,
                    "avg_rating": 4.0,
                    "practice_statuses": ["active"],
                    "practice_count": 1,
                },
                {
                    "client_id": "2",
                    "name": "Client 2",
                    "email": "client2@example.com",
                    "phone": "+2222222222",
                    "created_at": datetime.now() - timedelta(days=200),
                    "interaction_count": 20,
                    "avg_sentiment": 0.8,
                    "recent_interactions": 10,
                    "last_interaction": datetime.now() - timedelta(days=1),
                    "conversation_count": 15,
                    "avg_rating": 5.0,
                    "practice_statuses": ["completed"],
                    "practice_count": 5,
                },
            ]
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()
            )
        )

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_scores_batch(["1", "2"])

        assert len(result) == 2
        assert "1" in result
        assert "2" in result
        assert result["1"]["name"] == "Client 1"
        assert result["2"]["name"] == "Client 2"

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_empty_list(self):
        """Test with empty client ID list"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        result = await service.calculate_scores_batch([])

        assert result == {}

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_postgres_error(self):
        """Test PostgreSQL error handling in batch"""
        import asyncpg
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=asyncpg.PostgresError("Connection error"))

        # Use AsyncMock for the context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_cm.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_scores_batch(["1", "2"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_calculate_scores_batch_generic_error(self):
        """Test generic error handling in batch"""
        from agents.services.client_scoring import ClientScoringService

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("Unexpected error"))

        # Use AsyncMock for the context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_conn
        mock_cm.__aexit__.return_value = None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_cm

        service = ClientScoringService(db_pool=mock_pool)
        result = await service.calculate_scores_batch(["1", "2"])

        assert result == {}


# ============================================================================
# Test _calculate_scores_from_row
# ============================================================================


class TestCalculateScoresFromRow:
    """Test suite for _calculate_scores_from_row method"""

    def test_calculate_scores_from_row_full_data(self):
        """Test score calculation with full data"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "name": "Test Client",
                "email": "test@example.com",
                "phone": "+1234567890",
                "interaction_count": 10,
                "avg_sentiment": 0.5,
                "recent_interactions": 5,
                "last_interaction": datetime.now() - timedelta(days=5),
                "conversation_count": 8,
                "avg_rating": 4.5,
                "practice_statuses": ["active", "completed"],
                "practice_count": 3,
            }[key]
        )

        result = service._calculate_scores_from_row(mock_row, "123")

        assert result["client_id"] == "123"
        assert result["name"] == "Test Client"
        assert result["ltv_score"] > 0
        assert result["engagement_score"] == 50.0  # 10 * 5 = 50
        assert result["practice_score"] == 45.0  # 3 * 15 = 45

    def test_calculate_scores_from_row_null_values(self):
        """Test score calculation with null values"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "name": "Test Client",
                "email": None,
                "phone": None,
                "interaction_count": None,
                "avg_sentiment": None,
                "recent_interactions": None,
                "last_interaction": None,
                "conversation_count": None,
                "avg_rating": None,
                "practice_statuses": None,
                "practice_count": None,
            }[key]
        )

        result = service._calculate_scores_from_row(mock_row, "123")

        assert result["client_id"] == "123"
        assert result["total_interactions"] == 0
        assert result["days_since_last_interaction"] == 999  # No interaction
        assert result["practice_statuses"] == []

    def test_calculate_scores_from_row_max_values(self):
        """Test score calculation with max values (scores capped at 100)"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "name": "Super Client",
                "email": "super@example.com",
                "phone": "+9999999999",
                "interaction_count": 100,  # Would be 500, but capped at 100
                "avg_sentiment": 1.0,  # Max positive
                "recent_interactions": 50,  # Would be 500, but capped at 100
                "last_interaction": datetime.now(),
                "conversation_count": 100,
                "avg_rating": 5.0,  # Max rating
                "practice_statuses": ["completed"] * 10,
                "practice_count": 20,  # Would be 300, but capped at 100
            }[key]
        )

        result = service._calculate_scores_from_row(mock_row, "123")

        assert result["engagement_score"] == 100  # Capped
        assert result["recency_score"] == 100  # Capped
        assert result["practice_score"] == 100  # Capped
        assert result["quality_score"] == 100  # 5 * 20 = 100
        assert result["sentiment_score"] == 100  # (1 + 1) * 50 = 100

    def test_calculate_scores_from_row_negative_sentiment(self):
        """Test score calculation with negative sentiment"""
        from agents.services.client_scoring import ClientScoringService

        mock_pool = MagicMock()
        service = ClientScoringService(db_pool=mock_pool)

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "name": "Unhappy Client",
                "email": "unhappy@example.com",
                "phone": "+0000000000",
                "interaction_count": 5,
                "avg_sentiment": -0.8,  # Very negative
                "recent_interactions": 1,
                "last_interaction": datetime.now() - timedelta(days=30),
                "conversation_count": 2,
                "avg_rating": 1.0,  # Low rating
                "practice_statuses": ["cancelled"],
                "practice_count": 0,
            }[key]
        )

        result = service._calculate_scores_from_row(mock_row, "456")

        assert result["client_id"] == "456"
        assert result["sentiment_score"] == 10.0  # (-0.8 + 1) * 50 = 10
        assert result["quality_score"] == 20.0  # 1 * 20 = 20
        assert result["ltv_score"] < 50  # Low overall score
