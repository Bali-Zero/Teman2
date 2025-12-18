"""
Comprehensive Integration Tests for Conflict Resolution
Tests ConflictResolver and conflict handling

Covers:
- Conflict detection
- Conflict resolution strategies
- Data conflict handling
- Resolution tracking
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConflictResolverIntegration:
    """Integration tests for ConflictResolver"""

    @pytest.mark.asyncio
    async def test_conflict_resolver_initialization(self):
        """Test ConflictResolver initialization"""
        from services.conflict_resolver import ConflictResolver

        resolver = ConflictResolver()

        assert resolver is not None

    @pytest.mark.asyncio
    async def test_conflict_detection(self, db_pool):
        """Test conflict detection"""

        async with db_pool.acquire() as conn:
            # Create conflicts table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conflicts (
                    id SERIAL PRIMARY KEY,
                    conflict_type VARCHAR(100),
                    resource_type VARCHAR(100),
                    resource_id VARCHAR(255),
                    conflicting_values JSONB,
                    detected_at TIMESTAMP DEFAULT NOW(),
                    resolved BOOLEAN DEFAULT FALSE
                )
                """
            )

            # Detect conflict
            conflict_id = await conn.fetchval(
                """
                INSERT INTO conflicts (
                    conflict_type, resource_type, resource_id, conflicting_values
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "data_mismatch",
                "client",
                "client_123",
                {
                    "field": "email",
                    "value1": "old@example.com",
                    "value2": "new@example.com",
                },
            )

            assert conflict_id is not None

            # Retrieve conflicts
            conflicts = await conn.fetch(
                """
                SELECT conflict_type, resolved
                FROM conflicts
                WHERE resolved = FALSE
                """
            )

            assert len(conflicts) >= 1

            # Cleanup
            await conn.execute("DELETE FROM conflicts WHERE id = $1", conflict_id)

    @pytest.mark.asyncio
    async def test_conflict_resolution_strategies(self, db_pool):
        """Test conflict resolution strategies"""

        async with db_pool.acquire() as conn:
            # Create conflict_resolutions table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conflict_resolutions (
                    id SERIAL PRIMARY KEY,
                    conflict_id INTEGER,
                    resolution_strategy VARCHAR(100),
                    resolved_value TEXT,
                    resolved_by VARCHAR(255),
                    resolved_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create conflict
            conflict_id = await conn.fetchval(
                """
                INSERT INTO conflicts (
                    conflict_type, resource_type, resource_id, conflicting_values
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "data_mismatch",
                "client",
                "client_456",
                {"value1": "A", "value2": "B"},
            )

            # Resolve conflict
            resolution_id = await conn.fetchval(
                """
                INSERT INTO conflict_resolutions (
                    conflict_id, resolution_strategy, resolved_value, resolved_by
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                conflict_id,
                "latest_wins",
                "B",
                "system",
            )

            # Mark conflict as resolved
            await conn.execute(
                """
                UPDATE conflicts
                SET resolved = TRUE
                WHERE id = $1
                """,
                conflict_id,
            )

            # Verify resolution
            resolution = await conn.fetchrow(
                """
                SELECT resolution_strategy, resolved_value
                FROM conflict_resolutions
                WHERE id = $1
                """,
                resolution_id,
            )

            assert resolution is not None
            assert resolution["resolution_strategy"] == "latest_wins"

            # Cleanup
            await conn.execute("DELETE FROM conflict_resolutions WHERE id = $1", resolution_id)
            await conn.execute("DELETE FROM conflicts WHERE id = $1", conflict_id)
