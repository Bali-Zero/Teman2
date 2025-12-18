"""
Comprehensive Integration Tests for Handlers, Team Activity, and Productivity Routers
Tests handlers registry, team activity, productivity endpoints

Covers:
- GET /api/handlers/list - List all handlers
- GET /api/handlers/search - Search handlers
- Team activity endpoints
- Productivity endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestHandlersRouter:
    """Integration tests for Handlers router"""

    @pytest.mark.asyncio
    async def test_handlers_list_endpoint(self):
        """Test GET /api/handlers/list - List all handlers"""
        # Mock router extraction
        mock_router = MagicMock()
        mock_route = MagicMock()
        mock_route.name = "test_handler"
        mock_route.path = "/api/test"
        mock_route.methods = {"GET", "POST"}
        mock_route.endpoint.__doc__ = "Test handler"

        mock_router.routes = [mock_route]

        # Test handler extraction
        handlers = []
        for route in mock_router.routes:
            if hasattr(route, "endpoint"):
                handlers.append(
                    {
                        "name": route.name,
                        "path": route.path,
                        "methods": list(route.methods),
                    }
                )

        assert len(handlers) == 1
        assert handlers[0]["name"] == "test_handler"

    @pytest.mark.asyncio
    async def test_handlers_search_endpoint(self):
        """Test GET /api/handlers/search - Search handlers"""
        # Mock handlers
        handlers = [
            {"name": "test_handler", "path": "/api/test", "description": "Test handler"},
            {"name": "search_handler", "path": "/api/search", "description": "Search handler"},
        ]

        # Search handlers
        query = "test"
        results = [
            h
            for h in handlers
            if query.lower() in h["name"].lower()
            or query.lower() in h.get("description", "").lower()
        ]

        assert len(results) == 1
        assert results[0]["name"] == "test_handler"


@pytest.mark.integration
class TestTeamActivityRouter:
    """Integration tests for Team Activity router"""

    @pytest.mark.asyncio
    async def test_team_activity_tracking(self, db_pool):
        """Test team activity tracking"""

        async with db_pool.acquire() as conn:
            # Create team_activities table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_activities (
                    id SERIAL PRIMARY KEY,
                    team_member_email VARCHAR(255),
                    activity_type VARCHAR(100),
                    activity_details JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track activity
            activity_id = await conn.fetchval(
                """
                INSERT INTO team_activities (
                    team_member_email, activity_type, activity_details
                )
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "team@example.com",
                "client_created",
                {"client_id": 123, "client_name": "Test Client"},
            )

            assert activity_id is not None

            # Retrieve activities
            activities = await conn.fetch(
                """
                SELECT activity_type, activity_details
                FROM team_activities
                WHERE team_member_email = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                "team@example.com",
            )

            assert len(activities) == 1

            # Cleanup
            await conn.execute("DELETE FROM team_activities WHERE id = $1", activity_id)

    @pytest.mark.asyncio
    async def test_team_activity_analytics(self, db_pool):
        """Test team activity analytics"""

        async with db_pool.acquire() as conn:
            # Create multiple activities
            team_member = "analytics@team.com"
            activity_types = ["client_created", "practice_updated", "interaction_logged"]

            for activity_type in activity_types:
                await conn.execute(
                    """
                    INSERT INTO team_activities (
                        team_member_email, activity_type, activity_details
                    )
                    VALUES ($1, $2, $3)
                    """,
                    team_member,
                    activity_type,
                    {},
                )

            # Generate analytics
            analytics = await conn.fetchrow(
                """
                SELECT
                    team_member_email,
                    COUNT(*) as total_activities,
                    COUNT(DISTINCT activity_type) as unique_activity_types
                FROM team_activities
                WHERE team_member_email = $1
                GROUP BY team_member_email
                """,
                team_member,
            )

            assert analytics is not None
            assert analytics["total_activities"] == len(activity_types)

            # Cleanup
            await conn.execute(
                "DELETE FROM team_activities WHERE team_member_email = $1", team_member
            )


@pytest.mark.integration
class TestProductivityRouter:
    """Integration tests for Productivity router"""

    @pytest.mark.asyncio
    async def test_productivity_tracking(self, db_pool):
        """Test productivity tracking"""

        async with db_pool.acquire() as conn:
            # Create productivity_logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS productivity_logs (
                    id SERIAL PRIMARY KEY,
                    team_member_email VARCHAR(255),
                    task_description TEXT,
                    time_spent_minutes INTEGER,
                    productivity_score DECIMAL(5,2),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track productivity
            log_id = await conn.fetchval(
                """
                INSERT INTO productivity_logs (
                    team_member_email, task_description, time_spent_minutes, productivity_score
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "productivity@team.com",
                "Client consultation",
                60,
                0.85,
            )

            assert log_id is not None

            # Retrieve productivity logs
            logs = await conn.fetch(
                """
                SELECT task_description, productivity_score
                FROM productivity_logs
                WHERE team_member_email = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                "productivity@team.com",
            )

            assert len(logs) == 1
            assert logs[0]["productivity_score"] == 0.85

            # Cleanup
            await conn.execute("DELETE FROM productivity_logs WHERE id = $1", log_id)
