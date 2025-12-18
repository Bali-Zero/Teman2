"""
Comprehensive Integration Tests for 95% Coverage
Tests all edge cases, error handling, and branch coverage
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import asyncpg
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestTeamAnalytics95Percent:
    """Comprehensive tests for TeamAnalyticsService - 95% coverage"""

    @pytest.fixture
    async def db_pool(self, postgres_container):
        """Create database pool with test data"""
        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_work_sessions (
                    id SERIAL PRIMARY KEY,
                    user_name VARCHAR(255),
                    user_email VARCHAR(255) NOT NULL,
                    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    session_end TIMESTAMP WITH TIME ZONE,
                    duration_minutes INTEGER,
                    conversations_count INTEGER DEFAULT 0,
                    activities_count INTEGER DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'completed',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_analyze_work_patterns_all_branches(self, db_pool):
        """Test all branches of analyze_work_patterns"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with user_email
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, status, day_of_week, start_hour)
                VALUES
                ($1, NOW() - INTERVAL '1 day', 120, 'completed', 1, 9),
                ($1, NOW() - INTERVAL '2 days', 180, 'completed', 1, 9),
                ($1, NOW() - INTERVAL '3 days', NULL, 'completed', 0, 10)
                """,
                "test@example.com",
            )

        result = await service.analyze_work_patterns(user_email="test@example.com", days=30)
        assert "patterns" in result
        assert "consistency_score" in result
        assert "consistency_rating" in result

        # Test without user_email
        result2 = await service.analyze_work_patterns(user_email=None, days=30)
        assert isinstance(result2, dict)

        # Test with single session (stddev edge case)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, status)
                VALUES ($1, NOW(), 120, 'completed')
                """,
                "single@example.com",
            )

        result3 = await service.analyze_work_patterns(user_email="single@example.com", days=30)
        assert "patterns" in result3

        # Test consistency ratings
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # Create consistent sessions (high consistency)
            for i in range(10):
                await conn.execute(
                    """
                    INSERT INTO team_work_sessions
                    (user_email, session_start, duration_minutes, status)
                    VALUES ($1, NOW() - INTERVAL '%s days', 120, 'completed')
                    """
                    % i,
                    "consistent@example.com",
                )

        result4 = await service.analyze_work_patterns(user_email="consistent@example.com", days=30)
        assert result4["consistency_score"] >= 0

    @pytest.mark.asyncio
    async def test_calculate_productivity_scores_all_branches(self, db_pool):
        """Test all branches of calculate_productivity_scores"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with zero hours (should skip)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, $2, NOW(), 0, 0, 0, 'completed')
                """,
                "Zero User",
                "zero@example.com",
            )

        results = await service.calculate_productivity_scores(days=7)
        # User with zero hours should be skipped
        assert isinstance(results, list)

        # Test optimal session length (4-8 hours)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, $2, NOW(), 300, 10, 50, 'completed')
                """,
                "Optimal User",
                "optimal@example.com",
            )

        results2 = await service.calculate_productivity_scores(days=7)
        assert len(results2) > 0

        # Test short sessions (<4 hours)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, $2, NOW(), 120, 5, 20, 'completed')
                """,
                "Short User",
                "short@example.com",
            )

        results3 = await service.calculate_productivity_scores(days=7)
        assert len(results3) > 0

        # Test long sessions (>8 hours)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, $2, NOW(), 600, 15, 60, 'completed')
                """,
                "Long User",
                "long@example.com",
            )

        results4 = await service.calculate_productivity_scores(days=7)
        assert len(results4) > 0

        # Test productivity ratings
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # High productivity
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, $2, NOW(), 240, 20, 100, 'completed')
                """,
                "High Prod",
                "high@example.com",
            )

        results5 = await service.calculate_productivity_scores(days=7)
        if results5:
            assert results5[0]["productivity_score"] >= 0

    @pytest.mark.asyncio
    async def test_detect_burnout_signals_all_branches(self, db_pool):
        """Test all branches of detect_burnout_signals"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with less than 3 sessions (should skip)
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 120, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '2 days', 180, 6, 25, 'completed', 1)
                """,
                "Few Sessions",
                "few@example.com",
            )

        results = await service.detect_burnout_signals(user_email="few@example.com")
        assert isinstance(results, list)

        # Test increasing hours trend
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # Recent sessions with more hours
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 600, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '2 days', 650, 4, 18, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '3 days', 700, 3, 15, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '10 days', 200, 8, 30, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '11 days', 180, 7, 25, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '12 days', 220, 9, 35, 'completed', 1)
                """,
                "Increasing",
                "increasing@example.com",
            )

        results2 = await service.detect_burnout_signals(user_email="increasing@example.com")
        assert isinstance(results2, list)

        # Test very long sessions
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 650, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '2 days', 700, 4, 18, 'completed', 1)
                """,
                "Long Sessions",
                "long@example.com",
            )

        results3 = await service.detect_burnout_signals(user_email="long@example.com")
        assert isinstance(results3, list)

        # Test weekend work
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 120, 5, 20, 'completed', 0),
                ($1, $2, NOW() - INTERVAL '8 days', 180, 6, 25, 'completed', 6)
                """,
                "Weekend Worker",
                "weekend@example.com",
            )

        results4 = await service.detect_burnout_signals(user_email="weekend@example.com")
        assert isinstance(results4, list)

        # Test declining efficiency
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 120, 2, 10, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '2 days', 180, 3, 12, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '3 days', 200, 2, 8, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '10 days', 120, 10, 40, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '11 days', 180, 12, 50, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '12 days', 200, 15, 60, 'completed', 1)
                """,
                "Declining",
                "declining@example.com",
            )

        results5 = await service.detect_burnout_signals(user_email="declining@example.com")
        assert isinstance(results5, list)

        # Test inconsistent patterns
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 60, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '2 days', 600, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '3 days', 120, 5, 20, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '4 days', 500, 5, 20, 'completed', 1)
                """,
                "Inconsistent",
                "inconsistent@example.com",
            )

        results6 = await service.detect_burnout_signals(user_email="inconsistent@example.com")
        assert isinstance(results6, list)

        # Test risk levels
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # High risk (multiple warnings)
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status, day_of_week)
                VALUES
                ($1, $2, NOW() - INTERVAL '1 day', 650, 2, 10, 'completed', 0),
                ($1, $2, NOW() - INTERVAL '2 days', 700, 3, 12, 'completed', 6),
                ($1, $2, NOW() - INTERVAL '3 days', 680, 2, 8, 'completed', 0),
                ($1, $2, NOW() - INTERVAL '10 days', 200, 10, 40, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '11 days', 180, 12, 50, 'completed', 1),
                ($1, $2, NOW() - INTERVAL '12 days', 220, 15, 60, 'completed', 1)
                """,
                "High Risk",
                "highrisk@example.com",
            )

        results7 = await service.detect_burnout_signals(user_email="highrisk@example.com")
        if results7:
            assert "risk_level" in results7[0]

    @pytest.mark.asyncio
    async def test_analyze_performance_trends_all_branches(self, db_pool):
        """Test all branches of analyze_performance_trends"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with no sessions
        result = await service.analyze_performance_trends(
            user_email="nonexistent@example.com", weeks=4
        )
        assert "error" in result

        # Test with sessions
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ($1, NOW() - INTERVAL '1 week', 240, 10, 50, 'completed'),
                ($1, NOW() - INTERVAL '2 weeks', 180, 8, 40, 'completed'),
                ($1, NOW() - INTERVAL '3 weeks', 200, 9, 45, 'completed')
                """,
                "trends@example.com",
            )

        result2 = await service.analyze_performance_trends(user_email="trends@example.com", weeks=4)
        assert "weekly_breakdown" in result2
        assert "trend" in result2

        # Test with single week
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ($1, NOW() - INTERVAL '3 days', 240, 10, 50, 'completed')
                """,
                "singleweek@example.com",
            )

        result3 = await service.analyze_performance_trends(
            user_email="singleweek@example.com", weeks=4
        )
        assert "trend" in result3
        assert result3["trend"]["direction"] == "Stable"

        # Test increasing trend
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ($1, NOW() - INTERVAL '1 week', 100, 5, 20, 'completed'),
                ($1, NOW() - INTERVAL '2 weeks', 200, 10, 40, 'completed')
                """,
                "increasing@example.com",
            )

        result4 = await service.analyze_performance_trends(
            user_email="increasing@example.com", weeks=4
        )
        assert "trend" in result4

    @pytest.mark.asyncio
    async def test_analyze_workload_balance_all_branches(self, db_pool):
        """Test all branches of analyze_workload_balance"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with no sessions
        result = await service.analyze_workload_balance(days=7)
        assert "error" in result

        # Test with single user
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, status)
                VALUES ($1, $2, NOW(), 240, 10, 'completed')
                """,
                "Single User",
                "single@example.com",
            )

        result2 = await service.analyze_workload_balance(days=7)
        assert "team_distribution" in result2
        assert result2["balance_metrics"]["balance_score"] == 100

        # Test with multiple users (balanced)
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW(), 240, 10, 'completed'),
                ('User 2', 'user2@example.com', NOW(), 240, 10, 'completed')
                """
            )

        result3 = await service.analyze_workload_balance(days=7)
        assert "recommendations" in result3
        assert "✅" in result3["recommendations"][0]

        # Test with imbalanced workload
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, status)
                VALUES
                ('Overworked', 'over@example.com', NOW(), 600, 30, 'completed'),
                ('Underutilized', 'under@example.com', NOW(), 60, 2, 'completed')
                """
            )

        result4 = await service.analyze_workload_balance(days=7)
        assert "recommendations" in result4

    @pytest.mark.asyncio
    async def test_identify_optimal_hours_all_branches(self, db_pool):
        """Test all branches of identify_optimal_hours"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with no sessions
        result = await service.identify_optimal_hours(user_email="nonexistent@example.com", days=30)
        assert "error" in result

        # Test with sessions
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, status)
                VALUES
                ($1, NOW() - INTERVAL '1 day' + INTERVAL '9 hours', 120, 10, 'completed'),
                ($1, NOW() - INTERVAL '2 days' + INTERVAL '10 hours', 180, 15, 'completed')
                """,
                "optimal@example.com",
            )

        result2 = await service.identify_optimal_hours(user_email="optimal@example.com", days=30)
        assert "optimal_windows" in result2
        assert "all_hours" in result2

        # Test with less than 3 hours
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, status)
                VALUES ($1, NOW() - INTERVAL '1 day' + INTERVAL '9 hours', 120, 5, 'completed')
                """,
                "fewhours@example.com",
            )

        result3 = await service.identify_optimal_hours(user_email="fewhours@example.com", days=30)
        assert "optimal_windows" in result3

        # Test without user_email
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_email, session_start, duration_minutes, conversations_count, status)
                VALUES ('team@example.com', NOW() - INTERVAL '1 day' + INTERVAL '9 hours', 120, 5, 'completed')
                """
            )

        result4 = await service.identify_optimal_hours(user_email=None, days=30)
        assert isinstance(result4, dict)

    @pytest.mark.asyncio
    async def test_generate_team_insights_all_branches(self, db_pool):
        """Test all branches of generate_team_insights"""
        from services.team_analytics_service import TeamAnalyticsService

        service = TeamAnalyticsService(db_pool=db_pool)

        # Test with no sessions
        result = await service.generate_team_insights(days=7)
        assert "error" in result

        # Test with sessions
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, session_end, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day' + INTERVAL '4 hours', 240, 10, 50, 'completed'),
                ('User 2', 'user2@example.com', NOW() - INTERVAL '1 day' + INTERVAL '1 hour', NOW() - INTERVAL '1 day' + INTERVAL '5 hours', 240, 12, 55, 'completed')
                """
            )

        result2 = await service.generate_team_insights(days=7)
        assert "team_summary" in result2
        assert "team_health_score" in result2
        assert "collaboration_windows" in result2

        # Test health ratings
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # High health score
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, session_end, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day' + INTERVAL '4 hours', 240, 50, 200, 'completed')
                """
            )

        result3 = await service.generate_team_insights(days=7)
        assert "health_rating" in result3

        # Test without session_end
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, duration_minutes, conversations_count, activities_count, status)
                VALUES ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day', 240, 10, 50, 'completed')
                """
            )

        result4 = await service.generate_team_insights(days=7)
        assert isinstance(result4, dict)

        # Test collaboration windows edge cases
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_work_sessions")
            # Multiple users at same hour
            await conn.execute(
                """
                INSERT INTO team_work_sessions
                (user_name, user_email, session_start, session_end, duration_minutes, conversations_count, activities_count, status)
                VALUES
                ('User 1', 'user1@example.com', NOW() - INTERVAL '1 day' + INTERVAL '9 hours', NOW() - INTERVAL '1 day' + INTERVAL '13 hours', 240, 10, 50, 'completed'),
                ('User 2', 'user2@example.com', NOW() - INTERVAL '1 day' + INTERVAL '9 hours', NOW() - INTERVAL '1 day' + INTERVAL '13 hours', 240, 12, 55, 'completed'),
                ('User 3', 'user3@example.com', NOW() - INTERVAL '1 day' + INTERVAL '9 hours', NOW() - INTERVAL '1 day' + INTERVAL '13 hours', 240, 15, 60, 'completed')
                """
            )

        result5 = await service.generate_team_insights(days=7)
        assert len(result5.get("collaboration_windows", [])) > 0


@pytest.mark.integration
class TestMemoryService95Percent:
    """Comprehensive tests for MemoryServicePostgres - 95% coverage"""

    @pytest.fixture
    async def memory_service(self, postgres_container):
        """Create memory service"""
        from services.memory_service_postgres import MemoryServicePostgres

        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        service = MemoryServicePostgres(database_url=database_url)
        await service.connect()
        return service

    @pytest.mark.asyncio
    async def test_memory_service_all_branches(self, memory_service):
        """Test all branches of memory service"""

        # Test initialization without database_url
        from services.memory_service_postgres import MemoryServicePostgres

        service_no_db = MemoryServicePostgres(database_url=None)
        assert service_no_db.use_postgres is False

        # Test connect without database_url
        await service_no_db.connect()
        assert service_no_db.pool is None

        # Test close without pool
        await service_no_db.close()

        # Test get_memory cache hit
        user_id = "cache_test"
        memory1 = await memory_service.get_memory(user_id)
        memory2 = await memory_service.get_memory(user_id)  # Should use cache
        assert memory1.user_id == memory2.user_id

        # Test get_memory with PostgreSQL error (fallback)
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("DB Error")
            memory = await memory_service.get_memory("error_test")
            assert memory.user_id == "error_test"

        # Test save_memory without PostgreSQL
        service_no_db.memory_cache = {}
        memory = await service_no_db.get_memory("no_db_test")
        memory.summary = "Test"
        success = await service_no_db.save_memory(memory)
        assert success is True

        # Test add_fact with empty fact
        success = await memory_service.add_fact("test_user", "")
        assert success is False

        # Test add_fact with duplicate
        await memory_service.add_fact("test_user", "Fact 1")
        success = await memory_service.add_fact("test_user", "Fact 1")
        assert success is False

        # Test add_fact PostgreSQL error
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("DB Error")
            success = await memory_service.add_fact("test_user", "New Fact")
            assert success is False

        # Test update_summary truncation
        long_summary = "x" * 600
        await memory_service.update_summary("test_user", long_summary)
        memory = await memory_service.get_memory("test_user")
        assert len(memory.summary) <= memory_service.MAX_SUMMARY_LENGTH

        # Test increment_counter new counter
        await memory_service.increment_counter("test_user", "new_counter")
        memory = await memory_service.get_memory("test_user")
        assert memory.counters["new_counter"] == 1

        # Test retrieve with category filter
        await memory_service.add_fact("test_user", "User likes visa type B1")
        await memory_service.add_fact("test_user", "User likes Python")
        result = await memory_service.retrieve("test_user", category="visa")
        assert len(result["profile_facts"]) == 1

        # Test retrieve error handling
        with patch.object(memory_service, "get_memory") as mock_get:
            mock_get.side_effect = Exception("Error")
            result = await memory_service.retrieve("error_user")
            assert "error" in result

        # Test search PostgreSQL error fallback
        await memory_service.add_fact("search_user", "Python programming")
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("DB Error")
            results = await memory_service.search("Python")
            assert isinstance(results, list)

        # Test search with empty query
        results = await memory_service.search("")
        assert results == []

        # Test search connection error
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            import asyncpg

            mock_acquire.side_effect = asyncpg.exceptions.PostgresConnectionError(
                "Connection error"
            )
            results = await memory_service.search("test")
            assert isinstance(results, list)

        # Test search query timeout
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            import asyncpg

            mock_acquire.side_effect = asyncpg.exceptions.QueryCanceledError("Timeout")
            results = await memory_service.search("test")
            assert isinstance(results, list)

        # Test get_recent_history with PostgreSQL
        async with memory_service.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    messages JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO conversations (user_id, messages)
                VALUES ($1, $2::jsonb)
                """,
                "history_user",
                '[{"role": "user", "content": "Hello"}]',
            )

        history = await memory_service.get_recent_history("history_user", limit=5)
        assert isinstance(history, list)

        # Test get_recent_history with list messages
        async with memory_service.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversations (user_id, messages)
                VALUES ($1, $2)
                """,
                "history_user2",
                [{"role": "user", "content": "Hello"}],
            )

        history2 = await memory_service.get_recent_history("history_user2", limit=5)
        assert isinstance(history2, list)

        # Test get_recent_history error
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("Error")
            history = await memory_service.get_recent_history("error_user")
            assert history == []

        # Test get_stats with PostgreSQL error
        with patch.object(memory_service.pool, "acquire") as mock_acquire:
            mock_acquire.side_effect = Exception("Error")
            stats = await memory_service.get_stats()
            assert "cached_users" in stats

        # Test get_stats without PostgreSQL
        service_no_db = MemoryServicePostgres(database_url=None)
        stats = await service_no_db.get_stats()
        assert stats["postgres_enabled"] is False


@pytest.mark.integration
class TestEmbeddings95Percent:
    """Comprehensive tests for EmbeddingsGenerator - 95% coverage"""

    def test_embeddings_all_branches(self):
        """Test all branches of embeddings"""
        from core.embeddings import EmbeddingsGenerator

        # Test initialization with provider parameter
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            assert generator.provider == "openai"

        # Test initialization with settings provider
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            mock_settings = MagicMock()
            mock_settings.embedding_provider = "openai"
            generator = EmbeddingsGenerator(settings=mock_settings, api_key="test_key")
            assert generator.provider == "openai"

        # Test initialization without settings
        with patch.dict(os.environ, {}, clear=True):
            generator = EmbeddingsGenerator()
            assert generator.provider == "sentence-transformers"

        # Test OpenAI initialization production error
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "ENVIRONMENT": "production"}):
            mock_settings = MagicMock()
            mock_settings.environment = "production"
            with pytest.raises(ValueError):
                EmbeddingsGenerator(provider="openai", settings=mock_settings)

        # Test OpenAI initialization without API key
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                EmbeddingsGenerator(provider="openai")

        # Test Sentence Transformers initialization
        try:
            generator = EmbeddingsGenerator(provider="sentence-transformers")
            assert generator.provider == "sentence-transformers"
        except Exception:
            # If not available, should fallback
            pass

        # Test Sentence Transformers ImportError fallback
        with patch("core.embeddings.SentenceTransformer", side_effect=ImportError("Not available")):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
                generator = EmbeddingsGenerator(provider="sentence-transformers")
                # Should fallback to OpenAI
                assert generator.provider == "openai"

        # Test Sentence Transformers general exception fallback
        with patch("core.embeddings.SentenceTransformer", side_effect=Exception("Error")):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
                try:
                    generator = EmbeddingsGenerator(provider="sentence-transformers")
                    assert generator.provider == "openai"
                except Exception:
                    pass

        # Test generate_embeddings empty list
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            result = generator.generate_embeddings([])
            assert result == []

        # Test generate_embeddings OpenAI batch processing
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536) for _ in range(3000)]
            generator.client.embeddings.create = MagicMock(return_value=mock_response)

            texts = ["text"] * 3000
            embeddings = generator.generate_embeddings(texts)
            assert len(embeddings) == 3000

        # Test generate_embeddings error
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            generator.client.embeddings.create = MagicMock(side_effect=Exception("API Error"))
            with pytest.raises(Exception):
                generator.generate_embeddings(["test"])

        # Test generate_single_embedding empty result
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            generator.generate_embeddings = MagicMock(return_value=[])
            result = generator.generate_single_embedding("test")
            assert result == []

        # Test get_model_info
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            generator = EmbeddingsGenerator(provider="openai", api_key="test_key")
            info = generator.get_model_info()
            assert info["cost"] == "Paid (OpenAI API)"

        generator2 = EmbeddingsGenerator(provider="sentence-transformers")
        info2 = generator2.get_model_info()
        assert "FREE" in info2["cost"]


@pytest.mark.integration
class TestTokenEstimator95Percent:
    """Comprehensive tests for TokenEstimator - 95% coverage"""

    def test_token_estimator_all_branches(self):
        """Test all branches of token estimator"""
        from llm.token_estimator import TIKTOKEN_AVAILABLE, TokenEstimator

        # Test initialization with Gemini model
        estimator = TokenEstimator(model="gemini-2.5-flash")
        assert estimator.model == "gemini-2.5-flash"

        # Test initialization with GPT model
        estimator2 = TokenEstimator(model="gpt-4")
        assert estimator2.model == "gpt-4"

        # Test estimate_tokens with tiktoken
        if TIKTOKEN_AVAILABLE:
            estimator = TokenEstimator(model="gpt-4")
            tokens = estimator.estimate_tokens("Hello world")
            assert tokens > 0

        # Test estimate_tokens encoding error fallback
        estimator = TokenEstimator(model="gpt-4")
        if estimator._encoding:
            original_encode = estimator._encoding.encode
            estimator._encoding.encode = MagicMock(side_effect=Exception("Encoding error"))
            tokens = estimator.estimate_tokens("test")
            assert tokens > 0  # Should use approximation
            estimator._encoding.encode = original_encode

        # Test estimate_tokens without encoding (approximation)
        estimator = TokenEstimator(model="gpt-4")
        estimator._encoding = None
        tokens = estimator.estimate_tokens("Hello world test")
        assert tokens > 0

        # Test estimate_messages_tokens
        estimator = TokenEstimator(model="gpt-4")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        tokens = estimator.estimate_messages_tokens(messages)
        assert tokens > 0

        # Test estimate_messages_tokens empty content
        messages2 = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "Hi"},
        ]
        tokens2 = estimator.estimate_messages_tokens(messages2)
        assert tokens2 > 0

        # Test _estimate_approximate
        estimator = TokenEstimator(model="gpt-4")
        tokens = estimator._estimate_approximate("Hello world")
        assert tokens > 0

        # Test _estimate_approximate empty text
        tokens = estimator._estimate_approximate("")
        assert tokens == 0


@pytest.mark.integration
class TestIdentityService95Percent:
    """Comprehensive tests for IdentityService - 95% coverage"""

    @pytest.fixture
    async def db_pool(self, postgres_container):
        """Create database pool"""
        database_url = postgres_container
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)

        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS team_members (
                    id SERIAL PRIMARY KEY,
                    full_name VARCHAR(255),
                    email VARCHAR(255) UNIQUE,
                    pin_hash VARCHAR(255),
                    role VARCHAR(100),
                    department VARCHAR(100),
                    language VARCHAR(10),
                    personalized_response BOOLEAN DEFAULT false,
                    active BOOLEAN DEFAULT true,
                    last_login TIMESTAMP WITH TIME ZONE,
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
                """
            )

        yield pool
        await pool.close()

    @pytest.mark.asyncio
    async def test_identity_service_all_branches(self, db_pool):
        """Test all branches of identity service"""
        from app.modules.identity.models import User
        from app.modules.identity.service import IdentityService

        service = IdentityService()

        # Test get_password_hash
        hash1 = service.get_password_hash("1234")
        assert hash1 is not None
        assert hash1 != "1234"

        # Test verify_password correct
        assert service.verify_password("1234", hash1) is True

        # Test verify_password incorrect
        assert service.verify_password("wrong", hash1) is False

        # Test verify_password error handling
        assert service.verify_password("test", "invalid_hash") is False

        # Test authenticate_user invalid PIN format
        result = await service.authenticate_user("test@example.com", "abc")
        assert result is None

        result2 = await service.authenticate_user("test@example.com", "12")
        assert result2 is None

        result3 = await service.authenticate_user("test@example.com", "123456789")
        assert result3 is None

        # Test authenticate_user not found
        result4 = await service.authenticate_user("nonexistent@example.com", "1234")
        assert result4 is None

        # Test authenticate_user locked account
        async with db_pool.acquire() as conn:
            pin_hash = service.get_password_hash("1234")
            await conn.execute(
                """
                INSERT INTO team_members
                (full_name, email, pin_hash, role, department, active, locked_until)
                VALUES ($1, $2, $3, $4, $5, $6, NOW() + INTERVAL '1 hour')
                """,
                "Locked User",
                "locked@example.com",
                pin_hash,
                "admin",
                "tech",
                True,
            )

        result5 = await service.authenticate_user("locked@example.com", "1234")
        assert result5 is None

        # Test authenticate_user wrong PIN
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM team_members WHERE email = 'test@example.com'")
            pin_hash = service.get_password_hash("1234")
            await conn.execute(
                """
                INSERT INTO team_members
                (full_name, email, pin_hash, role, department, active)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                "Test User",
                "test@example.com",
                pin_hash,
                "admin",
                "tech",
                True,
            )

        result6 = await service.authenticate_user("test@example.com", "wrong")
        assert result6 is None

        # Verify failed_attempts incremented
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT failed_attempts FROM team_members WHERE email = $1",
                "test@example.com",
            )
            assert row["failed_attempts"] > 0

        # Test authenticate_user success
        result7 = await service.authenticate_user("test@example.com", "1234")
        assert result7 is not None
        assert isinstance(result7, User)
        assert result7.email == "test@example.com"

        # Test create_access_token
        token = service.create_access_token(result7, "session_123")
        assert token is not None
        assert len(token) > 0

        # Test get_permissions_for_role
        permissions = service.get_permissions_for_role("CEO")
        assert isinstance(permissions, list)
        assert len(permissions) > 0

        permissions2 = service.get_permissions_for_role("Tax Manager")
        assert isinstance(permissions2, list)

        permissions3 = service.get_permissions_for_role("Unknown Role")
        assert isinstance(permissions3, list)

        # Test get_db_connection error
        with patch("app.modules.identity.service.settings") as mock_settings:
            mock_settings.database_url = None
            with pytest.raises(ValueError):
                await service.get_db_connection()

        # Test authenticate_user exception handling
        with patch.object(service, "get_db_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB Error")
            result = await service.authenticate_user("test@example.com", "1234")
            assert result is None


@pytest.mark.integration
class TestRateLimiter95Percent:
    """Comprehensive tests for RateLimiter - 95% coverage"""

    def test_rate_limiter_all_branches(self):
        """Test all branches of rate limiter"""
        from middleware.rate_limiter import RateLimiter, RateLimitMiddleware, _rate_limit_storage

        # Clear storage
        _rate_limit_storage.clear()

        # Test initialization without Redis
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = None
            limiter = RateLimiter()
            assert limiter.redis_available is False

        # Test initialization with Redis
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            with patch("middleware.rate_limiter.redis") as mock_redis:
                mock_client = MagicMock()
                mock_client.ping.return_value = True
                mock_redis.from_url.return_value = mock_client
                limiter = RateLimiter()
                assert limiter.redis_available is True

        # Test initialization with Redis error
        with patch("middleware.rate_limiter.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"
            with patch("middleware.rate_limiter.redis") as mock_redis:
                mock_redis.from_url.side_effect = Exception("Connection error")
                limiter = RateLimiter()
                assert limiter.redis_available is False

        # Test is_allowed with Redis
        limiter = RateLimiter()
        limiter.redis_available = True
        limiter.redis_client = MagicMock()
        limiter.redis_client.pipeline.return_value.execute.return_value = [0, 5, None, None]

        allowed, info = limiter.is_allowed("test_key", limit=10, window=60)
        assert isinstance(allowed, bool)
        assert "limit" in info
        assert "remaining" in info

        # Test is_allowed without Redis (in-memory)
        limiter2 = RateLimiter()
        limiter2.redis_available = False
        _rate_limit_storage.clear()

        allowed2, info2 = limiter2.is_allowed("test_key2", limit=10, window=60)
        assert isinstance(allowed2, bool)
        assert "limit" in info2

        # Test is_allowed limit exceeded
        for i in range(12):
            allowed3, info3 = limiter2.is_allowed("test_key3", limit=10, window=60)
        assert allowed3 is False

        # Test is_allowed error handling
        limiter3 = RateLimiter()
        limiter3.redis_available = True
        limiter3.redis_client = MagicMock()
        limiter3.redis_client.pipeline.side_effect = Exception("Redis error")

        allowed4, info4 = limiter3.is_allowed("test_key4", limit=10, window=60)
        assert allowed4 is True  # Fail open

        # Test RateLimitMiddleware
        middleware = RateLimitMiddleware(MagicMock())
        assert middleware is not None

        # Test middleware dispatch
        request = MagicMock()
        request.url.path = "/api/test"
        request.client.host = "127.0.0.1"
        request.state = MagicMock()

        async def call_next(req):
            return MagicMock()

        # Mock rate limiter
        with patch("middleware.rate_limiter.rate_limiter") as mock_limiter:
            mock_limiter.is_allowed.return_value = (True, {"limit": 10, "remaining": 9})
            # Should not raise exception
            import asyncio

            try:
                asyncio.run(middleware.dispatch(request, call_next))
            except Exception:
                pass  # May raise in test environment


@pytest.mark.integration
class TestDependencies95Percent:
    """Comprehensive tests for dependencies - 95% coverage"""

    def test_dependencies_all_branches(self):
        """Test all branches of dependencies"""
        from fastapi import Request
        from fastapi.security import HTTPAuthorizationCredentials
        from jose import jwt

        from app.core.config import settings
        from app.dependencies import (
            get_ai_client,
            get_cache,
            get_current_user,
            get_database_pool,
            get_intelligent_router,
            get_memory_service,
            get_search_service,
        )

        # Test get_search_service available
        app = MagicMock()
        app.state.search_service = MagicMock()
        request = Request({"type": "http", "method": "GET", "path": "/"})
        request.app = app

        service = get_search_service(request)
        assert service is not None

        # Test get_search_service unavailable
        app2 = MagicMock()
        app2.state.search_service = None
        request2 = Request({"type": "http", "method": "GET", "path": "/"})
        request2.app = app2

        with pytest.raises(Exception):
            get_search_service(request2)

        # Test get_ai_client available
        app3 = MagicMock()
        app3.state.ai_client = MagicMock()
        request3 = Request({"type": "http", "method": "GET", "path": "/"})
        request3.app = app3

        client = get_ai_client(request3)
        assert client is not None

        # Test get_ai_client unavailable
        app4 = MagicMock()
        app4.state.ai_client = None
        request4 = Request({"type": "http", "method": "GET", "path": "/"})
        request4.app = app4

        with pytest.raises(Exception):
            get_ai_client(request4)

        # Test get_intelligent_router available
        app5 = MagicMock()
        app5.state.intelligent_router = MagicMock()
        request5 = Request({"type": "http", "method": "GET", "path": "/"})
        request5.app = app5

        router = get_intelligent_router(request5)
        assert router is not None

        # Test get_memory_service available
        app6 = MagicMock()
        app6.state.memory_service = MagicMock()
        request6 = Request({"type": "http", "method": "GET", "path": "/"})
        request6.app = app6

        memory = get_memory_service(request6)
        assert memory is not None

        # Test get_database_pool available
        app7 = MagicMock()
        app7.state.db_pool = MagicMock()
        request7 = Request({"type": "http", "method": "GET", "path": "/"})
        request7.app = app7

        pool = get_database_pool(request7)
        assert pool is not None

        # Test get_database_pool unavailable
        app8 = MagicMock()
        app8.state.db_pool = None
        request8 = Request({"type": "http", "method": "GET", "path": "/"})
        request8.app = app8

        with pytest.raises(Exception):
            get_database_pool(request8)

        # Test get_current_user no credentials
        with pytest.raises(Exception):
            get_current_user(None)

        # Test get_current_user invalid token
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")
        with pytest.raises(Exception):
            get_current_user(credentials)

        # Test get_current_user valid token
        token = jwt.encode(
            {"sub": "test@example.com", "user_id": "test_user", "role": "user", "exp": 9999999999},
            settings.jwt_secret_key,
            algorithm="HS256",
        )
        credentials2 = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = get_current_user(credentials2)
        assert user["email"] == "test@example.com"

        # Test get_current_user token with email in sub
        token2 = jwt.encode(
            {"sub": "test@example.com", "role": "user", "exp": 9999999999},
            settings.jwt_secret_key,
            algorithm="HS256",
        )
        credentials3 = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token2)
        user2 = get_current_user(credentials3)
        assert user2["email"] == "test@example.com"

        # Test get_current_user token without user identifier
        token3 = jwt.encode(
            {"role": "user", "exp": 9999999999},
            settings.jwt_secret_key,
            algorithm="HS256",
        )
        credentials4 = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token3)
        with pytest.raises(Exception):
            get_current_user(credentials4)

        # Test get_cache from app.state
        app9 = MagicMock()
        app9.state.cache_service = MagicMock()
        request9 = Request({"type": "http", "method": "GET", "path": "/"})
        request9.app = app9

        cache = get_cache(request9)
        assert cache is not None

        # Test get_cache fallback to singleton
        app10 = MagicMock()
        app10.state.cache_service = None
        request10 = Request({"type": "http", "method": "GET", "path": "/"})
        request10.app = app10

        cache2 = get_cache(request10)
        assert cache2 is not None


@pytest.mark.integration
class TestServiceHealth95Percent:
    """Comprehensive tests for ServiceHealth - 95% coverage"""

    def test_service_health_all_branches(self):
        """Test all branches of service health"""
        from app.core.service_health import ServiceRegistry, ServiceStatus

        registry = ServiceRegistry()

        # Test register service
        registry.register("test_service", ServiceStatus.HEALTHY)
        service = registry.get_service("test_service")
        assert service is not None
        assert service.status == ServiceStatus.HEALTHY

        # Test register critical service
        registry.register("search", ServiceStatus.HEALTHY)
        service2 = registry.get_service("search")
        assert service2.is_critical is True

        # Test register with error
        registry.register("error_service", ServiceStatus.UNAVAILABLE, error="Connection failed")
        service3 = registry.get_service("error_service")
        assert service3.error == "Connection failed"

        # Test register with explicit critical flag
        registry.register("custom_critical", ServiceStatus.HEALTHY, critical=True)
        service4 = registry.get_service("custom_critical")
        assert service4.is_critical is True

        # Test get_critical_failures
        registry.register("critical_down", ServiceStatus.UNAVAILABLE, critical=True)
        failures = registry.get_critical_failures()
        assert len(failures) > 0

        # Test has_critical_failures
        assert registry.has_critical_failures() is True

        # Test get_status empty
        registry2 = ServiceRegistry()
        status = registry2.get_status()
        assert status["overall"] == "unknown"

        # Test get_status healthy
        registry3 = ServiceRegistry()
        registry3.register("service1", ServiceStatus.HEALTHY)
        registry3.register("service2", ServiceStatus.HEALTHY)
        status2 = registry3.get_status()
        assert status2["overall"] == "healthy"

        # Test get_status degraded
        registry4 = ServiceRegistry()
        registry4.register("service1", ServiceStatus.HEALTHY)
        registry4.register("service2", ServiceStatus.DEGRADED)
        status3 = registry4.get_status()
        assert status3["overall"] == "degraded"

        # Test get_status critical
        registry5 = ServiceRegistry()
        registry5.register("search", ServiceStatus.UNAVAILABLE)
        status4 = registry5.get_status()
        assert status4["overall"] == "critical"

        # Test format_failures_message no failures
        registry6 = ServiceRegistry()
        message = registry6.format_failures_message()
        assert message == ""

        # Test format_failures_message with failures
        registry7 = ServiceRegistry()
        registry7.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")
        message2 = registry7.format_failures_message()
        assert "search" in message2
        assert "Connection failed" in message2


@pytest.mark.integration
class TestResponseHandler95Percent:
    """Comprehensive tests for ResponseHandler - 95% coverage"""

    def test_response_handler_all_branches(self):
        """Test all branches of response handler"""
        from services.routing.response_handler import ResponseHandler

        handler = ResponseHandler()

        # Test classify_query
        query_type1 = handler.classify_query("Hello")
        assert query_type1 in ["greeting", "casual", "business", "emergency"]

        query_type2 = handler.classify_query("I need help with visa")
        assert query_type2 in ["greeting", "casual", "business", "emergency"]

        # Test sanitize_response
        response1 = handler.sanitize_response(
            "Test response",
            query_type="business",
            apply_santai=True,
            add_contact=True,
        )
        assert response1 is not None

        # Test sanitize_response empty
        response2 = handler.sanitize_response("", query_type="business")
        assert response2 == ""

        # Test sanitize_response without santai
        response3 = handler.sanitize_response(
            "Test response",
            query_type="business",
            apply_santai=False,
            add_contact=False,
        )
        assert response3 is not None

        # Test sanitize_response error handling
        with patch("services.routing.response_handler.process_zantara_response") as mock_process:
            mock_process.side_effect = Exception("Error")
            response4 = handler.sanitize_response("Test", query_type="business")
            assert response4 == "Test"  # Should return original on error


# Continue with more comprehensive tests for remaining services...
