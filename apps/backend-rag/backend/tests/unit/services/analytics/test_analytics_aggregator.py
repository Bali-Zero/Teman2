"""
Tests for AnalyticsAggregator
"""
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.analytics.analytics_aggregator import AnalyticsAggregator


@pytest.fixture
def mock_app_state():
    """Mock app state"""
    app_state = MagicMock()
    app_state.boot_time = time.time()
    app_state.db_pool = None
    app_state.memory_service = None
    app_state.health_monitor = None
    return app_state


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()
    
    @asynccontextmanager
    async def acquire():
        yield conn
    
    pool.acquire = acquire
    pool.get_size = MagicMock(return_value=10)
    pool.get_idle_size = MagicMock(return_value=5)
    return pool, conn


@pytest.fixture
def aggregator(mock_app_state):
    """Create AnalyticsAggregator instance"""
    return AnalyticsAggregator(mock_app_state)


class TestAnalyticsAggregator:
    """Tests for AnalyticsAggregator"""

    def test_init(self, mock_app_state):
        """Test initialization"""
        aggregator = AnalyticsAggregator(mock_app_state)
        
        assert aggregator.app_state == mock_app_state
        assert aggregator._boot_time == mock_app_state.boot_time

    def test_init_without_boot_time(self):
        """Test initialization without boot_time"""
        app_state = MagicMock()
        del app_state.boot_time
        
        aggregator = AnalyticsAggregator(app_state)
        
        assert aggregator._boot_time is not None

    @pytest.mark.asyncio
    async def test_get_db_pool_from_app_state(self, aggregator, mock_db_pool):
        """Test getting db pool from app state"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        result = await aggregator._get_db_pool()
        
        assert result == pool

    @pytest.mark.asyncio
    async def test_get_db_pool_from_memory_service(self, aggregator, mock_db_pool):
        """Test getting db pool from memory service"""
        pool, conn = mock_db_pool
        memory_service = MagicMock()
        memory_service.pool = pool
        aggregator.app_state.db_pool = None
        aggregator.app_state.memory_service = memory_service
        
        result = await aggregator._get_db_pool()
        
        assert result == pool

    @pytest.mark.asyncio
    async def test_get_db_pool_none(self, aggregator):
        """Test getting db pool when not available"""
        aggregator.app_state.db_pool = None
        aggregator.app_state.memory_service = None
        
        result = await aggregator._get_db_pool()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_overview_stats_success(self, aggregator, mock_db_pool):
        """Test getting overview stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(side_effect=[10, 50, 5, 1000.0])
        
        stats = await aggregator.get_overview_stats()
        
        assert stats.conversations_today == 10
        assert stats.conversations_week == 50
        assert stats.users_active == 5
        assert stats.revenue_pipeline == 1000.0
        assert stats.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_get_overview_stats_with_health_monitor(self, aggregator, mock_db_pool):
        """Test getting overview stats with health monitor"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        health_monitor = MagicMock()
        health_monitor._service_states = {
            "service1": {"healthy": True},
            "service2": {"healthy": False},
            "service3": {"healthy": True},
        }
        aggregator.app_state.health_monitor = health_monitor
        
        conn.fetchval = AsyncMock(side_effect=[10, 50, 5, 1000.0])
        
        stats = await aggregator.get_overview_stats()
        
        assert stats.services_total == 3
        assert stats.services_healthy == 2

    @pytest.mark.asyncio
    async def test_get_overview_stats_no_db(self, aggregator):
        """Test getting overview stats without database"""
        aggregator.app_state.db_pool = None
        
        stats = await aggregator.get_overview_stats()
        
        assert stats.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_get_overview_stats_error(self, aggregator, mock_db_pool):
        """Test getting overview stats with error"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(side_effect=Exception("Database error"))
        
        stats = await aggregator.get_overview_stats()
        
        assert stats.uptime_seconds >= 0

    @pytest.mark.asyncio
    async def test_get_rag_stats_success(self, aggregator, mock_db_pool):
        """Test getting RAG stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "total": 100,
            "avg_latency": 50.0,
            "avg_embedding": 0.01,
            "avg_search": 0.02,
            "avg_rerank": 0.03,
            "avg_llm": 0.04,
        }[key]
        
        conn.fetchrow = AsyncMock(return_value=mock_row)
        conn.fetch = AsyncMock(return_value=[
            MagicMock(__getitem__=lambda self, key: {"query_text": "test", "count": 5}[key])
        ])
        
        stats = await aggregator.get_rag_stats()
        
        assert stats.queries_today == 100
        assert stats.avg_latency_ms == 50.0
        assert len(stats.top_queries) == 1

    @pytest.mark.asyncio
    async def test_get_crm_stats_success(self, aggregator, mock_db_pool):
        """Test getting CRM stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        conn.fetch = AsyncMock(side_effect=[
            [MagicMock(__getitem__=lambda self, key: {"status": "active", "count": 10}[key])],
            [MagicMock(__getitem__=lambda self, key: {"status": "in_progress", "count": 5}[key])],
        ])
        
        mock_revenue_row = MagicMock()
        mock_revenue_row.__getitem__ = lambda self, key: {"quoted": 1000.0, "paid": 500.0}[key]
        conn.fetchrow = AsyncMock(return_value=mock_revenue_row)
        conn.fetchval = AsyncMock(return_value=3)
        
        stats = await aggregator.get_crm_stats()
        
        assert stats.clients_total == 10
        assert stats.practices_total == 5
        assert stats.revenue_quoted == 1000.0
        assert stats.revenue_paid == 500.0

    @pytest.mark.asyncio
    async def test_get_team_stats_success(self, aggregator, mock_db_pool):
        """Test getting team stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        # fetchval returns the result of SUM(duration_minutes) / 60.0, so already in hours
        conn.fetchval = AsyncMock(side_effect=[2.0, 10.0, 5, 2])
        conn.fetch = AsyncMock(return_value=[
            MagicMock(__getitem__=lambda self, key: {"team_member": "john@example.com", "count": 10}[key])
        ])
        
        stats = await aggregator.get_team_stats()
        
        assert stats.hours_today == 2.0
        assert stats.hours_week == 10.0
        assert stats.active_sessions == 5
        assert stats.action_items_open == 2

    @pytest.mark.asyncio
    @patch("services.analytics.analytics_aggregator.psutil")
    async def test_get_system_stats_success(self, mock_psutil, aggregator, mock_db_pool):
        """Test getting system stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        mock_psutil.cpu_percent.return_value = 50.0
        mock_memory = MagicMock()
        mock_memory.used = 1024 * 1024 * 1024  # 1GB
        mock_memory.percent = 50.0
        mock_psutil.virtual_memory.return_value = mock_memory
        
        stats = await aggregator.get_system_stats()
        
        assert stats.cpu_percent == 50.0
        assert stats.memory_mb > 0
        assert stats.memory_percent == 50.0
        assert stats.db_connections_active == 5
        assert stats.db_connections_idle == 5

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient")
    async def test_get_qdrant_stats_success(self, mock_async_client, aggregator):
        """Test getting Qdrant stats successfully"""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "collections": [
                    {"name": "collection1"},
                    {"name": "collection2"},
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_collection_response = MagicMock()
        mock_collection_response.json.return_value = {
            "result": {
                "points_count": 100,
                "status": "green",
            }
        }
        mock_collection_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(side_effect=[mock_response, mock_collection_response, mock_collection_response])
        
        mock_async_client.return_value.__aenter__.return_value = mock_client
        mock_async_client.return_value.__aexit__.return_value = None
        
        stats = await aggregator.get_qdrant_stats()
        
        assert stats.total_documents == 200
        assert len(stats.collections) == 2

    @pytest.mark.asyncio
    async def test_get_feedback_stats_success(self, aggregator, mock_db_pool):
        """Test getting feedback stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(side_effect=[4.5, 5])
        conn.fetch = AsyncMock(side_effect=[
            [MagicMock(__getitem__=lambda self, key: {"rating": 5, "count": 10}[key])],
            [MagicMock(__getitem__=lambda self, key: {
                "session_id": "123",
                "rating": 2,
                "feedback_text": "Bad",
                "created_at": None,
            }[key])],
            [MagicMock(__getitem__=lambda self, key: {
                "date": None,
                "avg": 4.5,
            }[key])],
        ])
        
        stats = await aggregator.get_feedback_stats()
        
        assert stats.avg_rating == 4.5
        assert stats.total_ratings == 10
        assert stats.negative_feedback_count == 5

    @pytest.mark.asyncio
    async def test_get_alert_stats_success(self, aggregator, mock_db_pool):
        """Test getting alert stats successfully"""
        pool, conn = mock_db_pool
        aggregator.app_state.db_pool = pool
        
        conn.fetchval = AsyncMock(return_value=3)
        conn.fetch = AsyncMock(return_value=[
            MagicMock(__getitem__=lambda self, key: {
                "action": "login",
                "email": "test@example.com",
                "failure_reason": "Invalid password",
                "created_at": None,
            }[key])
        ])
        
        health_monitor = MagicMock()
        health_monitor._active_alerts = [
            {"service": "db", "message": "Connection failed", "severity": "high"}
        ]
        aggregator.app_state.health_monitor = health_monitor
        
        stats = await aggregator.get_alert_stats()
        
        assert stats.auth_failures_today == 3
        assert len(stats.recent_errors) == 1
        assert len(stats.active_alerts) == 1

