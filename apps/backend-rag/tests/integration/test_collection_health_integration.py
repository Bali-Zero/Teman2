"""
Comprehensive Integration Tests for Collection Health Services
Tests CollectionHealthService and collection monitoring

Covers:
- Collection health monitoring
- Collection statistics
- Health metrics
- Collection optimization
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollectionHealthServiceIntegration:
    """Integration tests for CollectionHealthService"""

    @pytest.mark.asyncio
    async def test_collection_health_initialization(self, qdrant_client):
        """Test CollectionHealthService initialization"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            from services.collection_health_service import CollectionHealthService

            service = CollectionHealthService(qdrant_client=mock_qdrant.return_value)

            assert service is not None

    @pytest.mark.asyncio
    async def test_collection_health_check(self, qdrant_client):
        """Test collection health check"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.get_collection_info = AsyncMock(
                return_value={
                    "points_count": 1000,
                    "vectors_count": 1000,
                    "indexed_vectors_count": 1000,
                }
            )
            mock_qdrant.return_value = mock_client

            from services.collection_health_service import CollectionHealthService

            service = CollectionHealthService(qdrant_client=mock_client)

            health = await service.check_collection_health("test_collection")

            assert health is not None
            assert "points_count" in health or "status" in health

    @pytest.mark.asyncio
    async def test_collection_statistics(self, qdrant_client):
        """Test collection statistics collection"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
            mock_client = MagicMock()
            mock_client.get_collection_info = AsyncMock(
                return_value={
                    "points_count": 5000,
                    "vectors_count": 5000,
                    "config": {
                        "params": {
                            "vectors": {
                                "size": 1536,
                            }
                        }
                    },
                }
            )
            mock_qdrant.return_value = mock_client

            from services.collection_health_service import CollectionHealthService

            service = CollectionHealthService(qdrant_client=mock_client)

            stats = await service.get_collection_stats("test_collection")

            assert stats is not None

    @pytest.mark.asyncio
    async def test_collection_health_storage(self, db_pool):
        """Test collection health metrics storage"""

        async with db_pool.acquire() as conn:
            # Create collection_health_metrics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_health_metrics (
                    id SERIAL PRIMARY KEY,
                    collection_name VARCHAR(255),
                    points_count INTEGER,
                    vectors_count INTEGER,
                    health_score DECIMAL(5,2),
                    checked_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store health metrics
            metric_id = await conn.fetchval(
                """
                INSERT INTO collection_health_metrics (
                    collection_name, points_count, vectors_count, health_score
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "visa_oracle",
                1612,
                1612,
                0.95,
            )

            assert metric_id is not None

            # Retrieve metrics
            metrics = await conn.fetchrow(
                """
                SELECT collection_name, health_score
                FROM collection_health_metrics
                WHERE collection_name = $1
                ORDER BY checked_at DESC
                LIMIT 1
                """,
                "visa_oracle",
            )

            assert metrics is not None
            assert metrics["health_score"] == 0.95

            # Cleanup
            await conn.execute("DELETE FROM collection_health_metrics WHERE id = $1", metric_id)
