"""
Regression Tests for CRM Stats 503 Fixes

Tests verify that:
1. Stats endpoints return 200 when db_pool is available
2. Stats endpoints return 503 (not 500) when db_pool is None
3. Middleware handles errors without serializing Pool objects
4. Error messages are safe (no secrets leaked)
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestCRMStats503Regression:
    """Regression tests for 503 fixes in CRM stats endpoints"""

    def test_practices_stats_overview_with_db_pool(self, authenticated_client, test_app):
        """Test GET /api/crm/practices/stats/overview returns 200 when db_pool is available"""
        from app.dependencies import get_database_pool

        mock_pool, mock_conn = self._create_mock_pool_with_stats_data()

        def override_get_db_pool(*args, **kwargs):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_get_db_pool

        try:
            response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response.status_code == 200
            data = response.json()
            assert "total_practices" in data
            assert "active_practices" in data
            assert "by_status" in data
            assert "by_type" in data
            assert "revenue" in data
        finally:
            test_app.dependency_overrides.clear()

    def test_practices_stats_overview_without_db_pool(self, authenticated_client):
        """Test GET /api/crm/practices/stats/overview returns 503 when db_pool is None"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            from fastapi import HTTPException

            # Simulate db_pool being None
            def raise_503(*args, **kwargs):
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Database unavailable",
                        "message": "The database connection pool is not initialized.",
                        "retry_after": 30,
                        "service": "database",
                        "troubleshooting": [
                            "Ensure DATABASE_URL is configured and reachable",
                            "Check PostgreSQL service status and credentials",
                            "Verify initialize_services() was executed at startup",
                        ],
                    },
                )

            mock_get_pool.side_effect = raise_503

            response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            # Verify error message is safe (no Pool object serialized)
            detail_str = str(data["detail"])
            assert "Pool" not in detail_str or "Object of type Pool" not in detail_str

    def test_interactions_stats_overview_with_db_pool(self, authenticated_client, test_app):
        """Test GET /api/crm/interactions/stats/overview returns 200 when db_pool is available"""
        from app.dependencies import get_database_pool

        mock_pool, mock_conn = self._create_mock_pool_with_interaction_stats()

        def override_get_db_pool(*args, **kwargs):
            return mock_pool

        test_app.dependency_overrides[get_database_pool] = override_get_db_pool

        try:
            response = authenticated_client.get("/api/crm/interactions/stats/overview")

            assert response.status_code == 200
            data = response.json()
            assert "total_interactions" in data
            assert "by_type" in data
            assert "by_sentiment" in data
            assert "by_team_member" in data
        finally:
            test_app.dependency_overrides.clear()

    def test_interactions_stats_overview_without_db_pool(self, authenticated_client):
        """Test GET /api/crm/interactions/stats/overview returns 503 when db_pool is None"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            from fastapi import HTTPException

            def raise_503(*args, **kwargs):
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "Database unavailable",
                        "message": "The database connection pool is not initialized.",
                    },
                )

            mock_get_pool.side_effect = raise_503

            response = authenticated_client.get("/api/crm/interactions/stats/overview")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data
            # Verify error message is safe
            detail_str = str(data["detail"])
            assert "Pool" not in detail_str or "Object of type Pool" not in detail_str

    def test_middleware_error_handling_no_pool_serialization(self, test_client):
        """Test middleware handles errors without serializing Pool objects"""
        # Simulate an error that might contain a Pool reference
        with patch("middleware.hybrid_auth.HybridAuthMiddleware.authenticate_request") as mock_auth:
            import asyncpg

            # Create a mock Pool object
            mock_pool = MagicMock(spec=asyncpg.Pool)

            # Create an error that references the Pool
            class PoolError(Exception):
                def __init__(self, pool):
                    self.pool = pool
                    super().__init__(f"Database error with pool: {pool}")

            mock_auth.side_effect = PoolError(mock_pool)

            # Make request to protected endpoint
            response = test_client.get("/api/crm/practices/stats/overview")

            # Should return 503, not 500
            assert response.status_code == 503
            data = response.json()
            assert "detail" in data

            # Verify the error message doesn't contain serialized Pool
            detail_str = str(data["detail"])
            assert "Object of type Pool" not in detail_str
            # Should contain a safe error message
            assert "Authentication service temporarily unavailable" in detail_str

    def test_stats_endpoints_with_db_connection_error(self, authenticated_client):
        """Test stats endpoints handle database connection errors gracefully"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Simulate connection error
            import asyncpg

            mock_conn.fetch.side_effect = asyncpg.PostgresError("Connection failed")
            mock_pool.acquire = MagicMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/practices/stats/overview")

            # Should handle error gracefully (500 or 503, not crash)
            assert response.status_code in [500, 503]
            data = response.json()
            assert "detail" in data

    def _create_mock_pool_with_stats_data(self):
        """Helper to create mock pool with practice stats data"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Mock practice stats queries
        mock_conn.fetch = AsyncMock(
            side_effect=[
                [{"status": "in_progress", "count": 5}, {"status": "completed", "count": 10}],
                [{"code": "KITAS", "name": "KITAS", "count": 8}],
            ]
        )
        mock_conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "total_revenue": 10000.0,
                    "paid_revenue": 8000.0,
                    "outstanding_revenue": 2000.0,
                },
                {"count": 5},
            ]
        )

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn

    def _create_mock_pool_with_interaction_stats(self):
        """Helper to create mock pool with interaction stats data"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        # Mock interaction stats queries
        mock_conn.fetch = AsyncMock(
            side_effect=[
                [{"interaction_type": "whatsapp", "count": 10}, {"interaction_type": "email", "count": 5}],
                [{"sentiment": "positive", "count": 8}, {"sentiment": "neutral", "count": 7}],
                [{"team_member": "zero@balizero.com", "count": 12}],
            ]
        )
        mock_conn.fetchrow = AsyncMock(return_value={"count": 3})

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn

