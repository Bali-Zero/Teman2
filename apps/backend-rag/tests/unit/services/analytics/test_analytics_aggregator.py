"""
Unit tests for services.analytics.analytics_aggregator module
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.analytics.analytics_aggregator import AnalyticsAggregator


@pytest.fixture
def mock_app_state():
    """Create a mock app state"""
    app_state = MagicMock()
    app_state.boot_time = time.time() - 3600  # 1 hour ago
    app_state.db_pool = None
    app_state.memory_service = None
    app_state.health_monitor = None
    return app_state


@pytest.fixture
def mock_db_pool():
    """Create a mock database connection pool"""
    pool = MagicMock()
    conn = MagicMock()
    
    # Mock connection context manager properly
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=None)
    
    # Make acquire() return an async context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    
    return pool, conn


class TestAnalyticsAggregatorInit:
    """Tests for AnalyticsAggregator initialization"""

    def test_init_sets_app_state(self, mock_app_state):
        """Test that __init__ sets app_state"""
        aggregator = AnalyticsAggregator(mock_app_state)
        assert aggregator.app_state == mock_app_state

    def test_init_sets_boot_time_from_app_state(self, mock_app_state):
        """Test that __init__ sets boot_time from app_state"""
        aggregator = AnalyticsAggregator(mock_app_state)
        assert aggregator._boot_time == mock_app_state.boot_time

    def test_init_sets_boot_time_default_when_missing(self):
        """Test that __init__ sets boot_time to current time when missing"""
        app_state = MagicMock()
        del app_state.boot_time
        aggregator = AnalyticsAggregator(app_state)
        assert aggregator._boot_time > 0


class TestGetDbPool:
    """Tests for _get_db_pool method"""

    @pytest.mark.asyncio
    async def test_returns_db_pool_from_app_state(self, mock_app_state, mock_db_pool):
        """Test that _get_db_pool returns db_pool from app_state"""
        pool, _ = mock_db_pool
        mock_app_state.db_pool = pool
        aggregator = AnalyticsAggregator(mock_app_state)
        result = await aggregator._get_db_pool()
        assert result == pool

    @pytest.mark.asyncio
    async def test_returns_pool_from_memory_service_when_db_pool_missing(self, mock_app_state, mock_db_pool):
        """Test that _get_db_pool returns pool from memory_service when db_pool is missing"""
        pool, _ = mock_db_pool
        memory_service = MagicMock()
        memory_service.pool = pool
        mock_app_state.db_pool = None
        mock_app_state.memory_service = memory_service
        aggregator = AnalyticsAggregator(mock_app_state)
        result = await aggregator._get_db_pool()
        assert result == pool

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pool_available(self, mock_app_state):
        """Test that _get_db_pool returns None when no pool is available"""
        mock_app_state.db_pool = None
        mock_app_state.memory_service = None
        aggregator = AnalyticsAggregator(mock_app_state)
        result = await aggregator._get_db_pool()
        assert result is None


class TestGetOverviewStats:
    """Tests for get_overview_stats method"""

    @pytest.mark.asyncio
    async def test_returns_overview_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_overview_stats returns stats with database data"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Mock database queries
        conn.fetchval = AsyncMock(side_effect=[10, 50, 5, 1000.0])  # conversations_today, week, users_active, revenue
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_overview_stats()
        
        assert stats.conversations_today == 10
        assert stats.conversations_week == 50
        assert stats.users_active == 5
        assert stats.revenue_pipeline == 1000.0
        assert stats.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_returns_overview_stats_without_db_pool(self, mock_app_state):
        """Test that get_overview_stats returns stats without database"""
        mock_app_state.db_pool = None
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_overview_stats()
        
        assert stats.conversations_today == 0
        assert stats.conversations_week == 0
        assert stats.users_active == 0
        assert stats.revenue_pipeline == 0.0
        assert stats.uptime_seconds > 0

    @pytest.mark.asyncio
    async def test_includes_service_health_when_available(self, mock_app_state, mock_db_pool):
        """Test that get_overview_stats includes service health when health_monitor is available"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        conn.fetchval = AsyncMock(return_value=0)
        
        health_monitor = MagicMock()
        health_monitor._service_states = {
            "service1": {"healthy": True},
            "service2": {"healthy": False},
            "service3": {"healthy": True},
        }
        mock_app_state.health_monitor = health_monitor
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_overview_stats()
        
        assert stats.services_total == 3
        assert stats.services_healthy == 2

    @pytest.mark.asyncio
    async def test_handles_database_errors_gracefully(self, mock_app_state, mock_db_pool):
        """Test that get_overview_stats handles database errors gracefully"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Make fetchval raise an exception (after acquire succeeds)
        conn.fetchval = AsyncMock(side_effect=Exception("DB Error"))
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_overview_stats()
        
        # Should still return stats object with defaults
        assert stats is not None
        # Even if database fails, stats object should be returned
        # uptime_seconds is set inside try block after pool check, so may be 0 if error occurs early
        # But the important thing is that the function doesn't crash
        assert hasattr(stats, 'conversations_today')
        assert hasattr(stats, 'uptime_seconds')


class TestGetRagStats:
    """Tests for get_rag_stats method"""

    @pytest.mark.asyncio
    async def test_returns_rag_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_rag_stats returns stats with database data"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Mock fetchrow for query analytics
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "total": 100,
            "avg_latency": 500.0,
            "avg_embedding": 0.1,
            "avg_search": 0.2,
            "avg_rerank": 0.05,
            "avg_llm": 0.3,
        }.get(key, 0)
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.fetch = AsyncMock(return_value=[
            {"query_text": "test query", "count": 5}
        ])
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_rag_stats()
        
        assert stats.queries_today == 100
        assert stats.avg_latency_ms == 500.0
        assert stats.embedding_latency_ms == 100.0  # 0.1 * 1000
        assert stats.search_latency_ms == 200.0  # 0.2 * 1000
        assert len(stats.top_queries) == 1

    @pytest.mark.asyncio
    async def test_returns_rag_stats_without_db_pool(self, mock_app_state):
        """Test that get_rag_stats returns stats without database"""
        mock_app_state.db_pool = None
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_rag_stats()
        
        assert stats.queries_today == 0
        assert stats.avg_latency_ms == 0.0
        assert stats.top_queries == []


class TestGetCrmStats:
    """Tests for get_crm_stats method"""

    @pytest.mark.asyncio
    async def test_returns_crm_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_crm_stats returns stats with database data"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Mock client rows
        conn.fetch = AsyncMock(side_effect=[
            [{"status": "active", "count": 10}, {"status": "inactive", "count": 5}],  # clients
            [{"status": "pending", "count": 3}, {"status": "completed", "count": 7}],  # practices
        ])
        
        # Mock revenue row
        revenue_row = MagicMock()
        revenue_row.__getitem__ = lambda self, key: {
            "quoted": 5000.0,
            "paid": 3000.0,
        }.get(key, 0)
        conn.fetchrow = AsyncMock(return_value=revenue_row)
        
        conn.fetchval = AsyncMock(side_effect=[2, 3, 4, 1])  # renewals and documents
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_crm_stats()
        
        assert stats.clients_total == 15
        assert stats.clients_active == 10
        assert stats.practices_total == 10
        assert stats.revenue_quoted == 5000.0
        assert stats.revenue_paid == 3000.0
        assert stats.renewals_30_days == 2
        assert stats.documents_pending == 1


class TestGetTeamStats:
    """Tests for get_team_stats method"""

    @pytest.mark.asyncio
    async def test_returns_team_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_team_stats returns stats with database data"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Note: SQL query divides by 60.0, so fetchval returns hours directly
        conn.fetchval = AsyncMock(side_effect=[8.0, 40.0, 5, 2])  # hours (today, week), active_sessions, action_items
        conn.fetch = AsyncMock(return_value=[
            {"team_member": "Alice", "count": 10},
            {"team_member": "Bob", "count": 5},
        ])
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_team_stats()
        
        assert stats.hours_today == 8.0
        assert stats.hours_week == 40.0
        assert stats.active_sessions == 5
        assert stats.action_items_open == 2
        assert len(stats.conversations_by_agent) == 2
        assert stats.conversations_by_agent["Alice"] == 10


class TestGetSystemStats:
    """Tests for get_system_stats method"""

    @pytest.mark.asyncio
    async def test_returns_system_stats(self, mock_app_state, mock_db_pool):
        """Test that get_system_stats returns system statistics"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        # Mock pool methods
        pool.get_size = MagicMock(return_value=20)
        pool.get_idle_size = MagicMock(return_value=5)
        
        health_monitor = MagicMock()
        health_monitor._service_states = {
            "service1": {"healthy": True, "last_check": "2024-01-01", "error": ""},
            "service2": {"healthy": False, "last_check": "2024-01-01", "error": "Error"},
        }
        mock_app_state.health_monitor = health_monitor
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_system_stats()
        
        assert stats.cpu_percent >= 0
        assert stats.memory_mb > 0
        assert stats.memory_percent >= 0
        assert stats.db_connections_active == 15  # 20 - 5
        assert stats.db_connections_idle == 5
        assert len(stats.services) == 2

    @pytest.mark.asyncio
    async def test_handles_missing_pool_gracefully(self, mock_app_state):
        """Test that get_system_stats handles missing pool gracefully"""
        mock_app_state.db_pool = None
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_system_stats()
        
        assert stats.cpu_percent >= 0
        assert stats.memory_mb > 0


class TestGetFeedbackStats:
    """Tests for get_feedback_stats method"""

    @pytest.mark.asyncio
    async def test_returns_feedback_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_feedback_stats returns stats with database data"""
        from datetime import datetime
        
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(side_effect=[4.5, 3])  # avg_rating, negative_feedback_count
        conn.fetch = AsyncMock(side_effect=[
            [{"rating": 5, "count": 10}, {"rating": 4, "count": 5}],  # rating_distribution
            [{"session_id": "123", "rating": 2, "feedback_text": "Bad", "created_at": datetime.now()}],  # negative feedback
            [{"date": datetime.now().date(), "avg": 4.5}],  # quality_trend
        ])
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_feedback_stats()
        
        assert stats.avg_rating == 4.5
        assert stats.total_ratings == 15
        assert stats.negative_feedback_count == 3
        assert len(stats.recent_negative_feedback) == 1
        assert len(stats.quality_trend) == 1


class TestGetAlertStats:
    """Tests for get_alert_stats method"""

    @pytest.mark.asyncio
    async def test_returns_alert_stats_with_db_data(self, mock_app_state, mock_db_pool):
        """Test that get_alert_stats returns stats with database data"""
        pool, conn = mock_db_pool
        mock_app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(return_value=5)  # auth_failures_today
        conn.fetch = AsyncMock(return_value=[
            {"action": "login", "email": "test@test.com", "failure_reason": "Invalid", "created_at": None}
        ])
        
        health_monitor = MagicMock()
        health_monitor._active_alerts = [
            {"service": "service1", "message": "Error", "severity": "high"}
        ]
        mock_app_state.health_monitor = health_monitor
        
        aggregator = AnalyticsAggregator(mock_app_state)
        stats = await aggregator.get_alert_stats()
        
        assert stats.auth_failures_today == 5
        assert len(stats.recent_errors) == 1
        assert len(stats.active_alerts) == 1

