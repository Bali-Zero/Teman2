"""
Tests for AnalyticsAggregator service.

Covers all 8 public methods with mocked DB pool, httpx client, psutil, and app_state.
"""

import sys
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.analytics.analytics_aggregator import (
    AnalyticsAggregator,
    CRMStats,
    OverviewStats,
    RAGStats,
    SystemStats,
    TeamStats,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(conn: AsyncMock) -> MagicMock:
    """
    Build a MagicMock pool whose acquire() returns an async context manager
    yielding *conn*.  get_size / get_idle_size are plain sync calls.
    """

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    pool.get_size = MagicMock(return_value=10)
    pool.get_idle_size = MagicMock(return_value=7)
    return pool


# ---------------------------------------------------------------------------
# Stub classes for QdrantStats / FeedbackStats / AlertStats
# (lazily imported from backend.app.routers.analytics, which may not define
#  them in this branch — provide simple dataclass-like stubs)
# ---------------------------------------------------------------------------


class _QdrantStats:
    def __init__(self) -> None:
        self.total_documents: int = 0
        self.collections: list[dict] = []


class _FeedbackStats:
    def __init__(self) -> None:
        self.avg_rating: float = 0.0
        self.rating_distribution: dict[str, int] = {}
        self.total_ratings: int = 0
        self.negative_feedback_count: int = 0
        self.recent_negative_feedback: list[dict] = []
        self.quality_trend: list[dict] = []


class _AlertStats:
    def __init__(self) -> None:
        self.auth_failures_today: int = 0
        self.recent_errors: list[dict] = []
        self.active_alerts: list[dict] = []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_conn() -> AsyncMock:
    """Async mock for a DB connection (supports fetchval, fetchrow, fetch)."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def mock_pool(mock_conn: AsyncMock) -> MagicMock:
    """Pool mock whose acquire() yields mock_conn as an async ctx manager."""
    return _make_pool(mock_conn)


@pytest.fixture
def mock_app_state(mock_pool: MagicMock) -> MagicMock:
    """Mock FastAPI app.state with db_pool, health_monitor, boot_time."""
    state = MagicMock()
    state.db_pool = mock_pool
    state.boot_time = time.time() - 3600.0  # 1 hour uptime
    state.health_monitor = MagicMock()
    state.health_monitor._service_states = {
        "postgres": {"healthy": True, "last_check": "2026-04-14T00:00:00", "error": ""},
        "qdrant": {"healthy": True, "last_check": "2026-04-14T00:00:00", "error": ""},
        "redis": {"healthy": False, "last_check": "2026-04-14T00:00:00", "error": "timeout"},
    }
    state.health_monitor._active_alerts = [
        {"service": "redis", "message": "Connection timeout", "severity": "warning"},
    ]
    return state


@pytest.fixture
def aggregator(mock_app_state: MagicMock) -> AnalyticsAggregator:
    """AnalyticsAggregator instance with fully mocked app_state."""
    return AnalyticsAggregator(mock_app_state)


# ---------------------------------------------------------------------------
# get_overview_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_overview_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """Overview stats should aggregate conversations, users, revenue, uptime."""
    # fetchval is called 4 times:
    #   conversations_today, conversations_week, users_active, revenue_pipeline
    mock_conn.fetchval.side_effect = [15, 87, 42, 125000.50]

    result = await aggregator.get_overview_stats()

    assert isinstance(result, OverviewStats)
    assert result.conversations_today == 15
    assert result.conversations_week == 87
    assert result.users_active == 42
    assert result.revenue_pipeline == 125000.50
    assert result.uptime_seconds > 0
    # Services health from mocked health_monitor
    assert result.services_total == 3
    assert result.services_healthy == 2  # postgres + qdrant healthy, redis not


@pytest.mark.asyncio
async def test_get_overview_stats_no_pool(mock_app_state: MagicMock) -> None:
    """When db_pool is None, overview stats should return defaults without error."""
    mock_app_state.db_pool = None
    mock_app_state.memory_service = None
    agg = AnalyticsAggregator(mock_app_state)

    result = await agg.get_overview_stats()

    assert isinstance(result, OverviewStats)
    assert result.conversations_today == 0
    assert result.revenue_pipeline == 0.0


# ---------------------------------------------------------------------------
# get_rag_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_rag_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """RAG stats should aggregate query analytics and latency breakdown."""
    mock_conn.fetchrow.return_value = {
        "total": 250,
        "avg_latency": 320.5,
        "avg_embedding": 0.045,   # seconds
        "avg_search": 0.12,
        "avg_rerank": 0.08,
        "avg_llm": 0.55,
    }
    mock_conn.fetch.return_value = [
        {"query_text": "How to get a KITAS visa?", "count": 30},
        {"query_text": "Company setup cost", "count": 18},
    ]

    # Patch the lazy import of cache metrics to avoid ImportError
    mock_metrics = MagicMock()
    mock_metrics.cache_hits._value.get.return_value = 80
    mock_metrics.cache_misses._value.get.return_value = 20
    with patch.dict(sys.modules, {"backend.app.metrics": mock_metrics}):
        result = await aggregator.get_rag_stats()

    assert isinstance(result, RAGStats)
    assert result.queries_today == 250
    assert result.avg_latency_ms == 320.5
    # Seconds converted to ms (*1000)
    assert result.embedding_latency_ms == pytest.approx(45.0)
    assert result.search_latency_ms == pytest.approx(120.0)
    assert result.rerank_latency_ms == pytest.approx(80.0)
    assert result.llm_latency_ms == pytest.approx(550.0)
    assert len(result.top_queries) == 2
    assert result.top_queries[0]["query"] == "How to get a KITAS visa?"
    assert result.top_queries[0]["count"] == 30


@pytest.mark.asyncio
async def test_get_rag_stats_null_latencies(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """RAG stats should handle NULL latency values gracefully."""
    mock_conn.fetchrow.return_value = {
        "total": 0,
        "avg_latency": None,
        "avg_embedding": None,
        "avg_search": None,
        "avg_rerank": None,
        "avg_llm": None,
    }
    mock_conn.fetch.return_value = []

    result = await aggregator.get_rag_stats()

    assert isinstance(result, RAGStats)
    assert result.queries_today == 0
    assert result.avg_latency_ms == 0.0
    assert result.embedding_latency_ms == 0.0


# ---------------------------------------------------------------------------
# get_crm_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_crm_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """CRM stats should aggregate clients, practices, revenue, renewals, documents."""
    client_rows = [
        {"status": "active", "count": 200},
        {"status": "inactive", "count": 50},
        {"status": "lead", "count": 30},
    ]
    practice_rows = [
        {"status": "in_progress", "count": 45},
        {"status": "completed", "count": 120},
        {"status": "cancelled", "count": 10},
    ]
    # fetch called twice: clients, then practices
    mock_conn.fetch.side_effect = [client_rows, practice_rows]

    # fetchrow for revenue
    mock_conn.fetchrow.return_value = {"quoted": 500000.0, "paid": 320000.0}

    # fetchval called 4 times: renewals_30, renewals_60, renewals_90, documents_pending
    mock_conn.fetchval.side_effect = [5, 8, 12, 3]

    result = await aggregator.get_crm_stats()

    assert isinstance(result, CRMStats)
    assert result.clients_total == 280
    assert result.clients_active == 200
    assert result.clients_by_status == {"active": 200, "inactive": 50, "lead": 30}
    assert result.practices_total == 175
    assert result.practices_by_status == {
        "in_progress": 45,
        "completed": 120,
        "cancelled": 10,
    }
    assert result.revenue_quoted == 500000.0
    assert result.revenue_paid == 320000.0
    assert result.renewals_30_days == 5
    assert result.renewals_60_days == 8
    assert result.renewals_90_days == 12
    assert result.documents_pending == 3


# ---------------------------------------------------------------------------
# get_team_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_team_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """Team stats should aggregate work hours, agent conversations, sessions, action items."""
    # fetchval calls: hours_today, hours_week, active_sessions, action_items_open
    mock_conn.fetchval.side_effect = [4.5, 32.0, 3, 7]

    # fetch for agent conversations
    mock_conn.fetch.return_value = [
        {"team_member": "alice", "count": 15},
        {"team_member": "bob", "count": 22},
    ]

    result = await aggregator.get_team_stats()

    assert isinstance(result, TeamStats)
    assert result.hours_today == 4.5
    assert result.hours_week == 32.0
    assert result.conversations_by_agent == {"alice": 15, "bob": 22}
    assert result.active_sessions == 3
    assert result.action_items_open == 7


# ---------------------------------------------------------------------------
# get_system_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_system_stats(
    aggregator: AnalyticsAggregator,
) -> None:
    """System stats should report CPU, memory, DB connections, and service health."""
    mock_memory = MagicMock()
    mock_memory.used = 4 * 1024 * 1024 * 1024  # 4 GB
    mock_memory.percent = 62.5

    with patch("backend.services.analytics.analytics_aggregator.psutil") as mock_psutil:
        mock_psutil.cpu_percent.return_value = 35.2
        mock_psutil.virtual_memory.return_value = mock_memory

        result = await aggregator.get_system_stats()

    assert isinstance(result, SystemStats)
    assert result.cpu_percent == 35.2
    assert result.memory_percent == 62.5
    assert result.memory_mb == pytest.approx(4096.0)
    # Pool: size 10, idle 7 => active 3
    assert result.db_connections_active == 3
    assert result.db_connections_idle == 7
    # 3 services from health_monitor
    assert len(result.services) == 3
    names = {s["name"] for s in result.services}
    assert names == {"postgres", "qdrant", "redis"}
    # redis is unhealthy
    redis_svc = next(s for s in result.services if s["name"] == "redis")
    assert redis_svc["healthy"] is False
    assert redis_svc["error"] == "timeout"


# ---------------------------------------------------------------------------
# get_qdrant_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_qdrant_stats(aggregator: AnalyticsAggregator) -> None:
    """Qdrant stats should list collections with document counts."""
    mock_settings = MagicMock()
    mock_settings.qdrant_url = "http://localhost:6333"
    mock_settings.qdrant_api_key = "test-key"

    # Mock httpx responses
    collections_response = MagicMock()
    collections_response.raise_for_status = MagicMock()
    collections_response.json.return_value = {
        "result": {
            "collections": [
                {"name": "documents"},
                {"name": "kbli"},
            ],
        },
    }

    docs_response = MagicMock()
    docs_response.raise_for_status = MagicMock()
    docs_response.json.return_value = {
        "result": {"points_count": 50000, "status": "green"},
    }

    kbli_response = MagicMock()
    kbli_response.raise_for_status = MagicMock()
    kbli_response.json.return_value = {
        "result": {"points_count": 1563, "status": "green"},
    }

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.get = AsyncMock(
        side_effect=[collections_response, docs_response, kbli_response],
    )
    aggregator._client = mock_client

    # Inject stub QdrantStats into the analytics router module before the lazy import
    analytics_module = sys.modules.get("backend.app.routers.analytics")
    if analytics_module is None:
        # Module not imported yet -- create a minimal stub module
        import types
        analytics_module = types.ModuleType("backend.app.routers.analytics")
        sys.modules["backend.app.routers.analytics"] = analytics_module

    original_qdrant = getattr(analytics_module, "QdrantStats", None)
    analytics_module.QdrantStats = _QdrantStats  # type: ignore[attr-defined]

    try:
        with patch("backend.app.core.config.settings", mock_settings):
            result = await aggregator.get_qdrant_stats()

        assert result.total_documents == 51563
        assert len(result.collections) == 2
        # Sorted by documents DESC
        assert result.collections[0]["name"] == "documents"
        assert result.collections[0]["documents"] == 50000
        assert result.collections[1]["name"] == "kbli"
        assert result.collections[1]["documents"] == 1563
    finally:
        # Restore original attribute
        if original_qdrant is not None:
            analytics_module.QdrantStats = original_qdrant  # type: ignore[attr-defined]
        elif hasattr(analytics_module, "QdrantStats"):
            delattr(analytics_module, "QdrantStats")


# ---------------------------------------------------------------------------
# get_feedback_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_feedback_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """Feedback stats should aggregate ratings, distribution, negatives, trend."""
    # Inject stub FeedbackStats into the analytics router module
    analytics_module = sys.modules.get("backend.app.routers.analytics")
    if analytics_module is None:
        import types
        analytics_module = types.ModuleType("backend.app.routers.analytics")
        sys.modules["backend.app.routers.analytics"] = analytics_module

    original_feedback = getattr(analytics_module, "FeedbackStats", None)
    analytics_module.FeedbackStats = _FeedbackStats  # type: ignore[attr-defined]

    try:
        # fetchval: avg_rating, negative_feedback_count
        mock_conn.fetchval.side_effect = [4.35, 2]

        # fetch calls: rating_distribution, recent_negative, quality_trend
        dist_rows = [
            {"rating": 5, "count": 80},
            {"rating": 4, "count": 45},
            {"rating": 3, "count": 15},
            {"rating": 2, "count": 1},
            {"rating": 1, "count": 1},
        ]
        negative_rows = [
            {
                "session_id": "sess-001",
                "rating": 1,
                "feedback_text": "Response was not helpful at all",
                "created_at": datetime(2026, 4, 13, 10, 0, 0, tzinfo=timezone.utc),
            },
        ]
        trend_rows = [
            {"date": date(2026, 4, 12), "avg": 4.2},
            {"date": date(2026, 4, 13), "avg": 4.5},
        ]
        mock_conn.fetch.side_effect = [dist_rows, negative_rows, trend_rows]

        result = await aggregator.get_feedback_stats()

        assert result.avg_rating == 4.35
        assert result.total_ratings == 142  # 80+45+15+1+1
        assert result.rating_distribution == {
            "5": 80, "4": 45, "3": 15, "2": 1, "1": 1,
        }
        assert result.negative_feedback_count == 2
        assert len(result.recent_negative_feedback) == 1
        assert result.recent_negative_feedback[0]["rating"] == 1
        assert len(result.quality_trend) == 2
        assert result.quality_trend[0]["date"] == "2026-04-12"
        assert result.quality_trend[0]["rating"] == 4.2
    finally:
        if original_feedback is not None:
            analytics_module.FeedbackStats = original_feedback  # type: ignore[attr-defined]
        elif hasattr(analytics_module, "FeedbackStats"):
            delattr(analytics_module, "FeedbackStats")


# ---------------------------------------------------------------------------
# get_alert_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alert_stats(
    aggregator: AnalyticsAggregator,
    mock_conn: AsyncMock,
) -> None:
    """Alert stats should aggregate auth failures, errors, and active alerts."""
    # Inject stub AlertStats into the analytics router module
    analytics_module = sys.modules.get("backend.app.routers.analytics")
    if analytics_module is None:
        import types
        analytics_module = types.ModuleType("backend.app.routers.analytics")
        sys.modules["backend.app.routers.analytics"] = analytics_module

    original_alert = getattr(analytics_module, "AlertStats", None)
    analytics_module.AlertStats = _AlertStats  # type: ignore[attr-defined]

    try:
        # fetchval: auth_failures_today
        mock_conn.fetchval.return_value = 7

        # fetch: recent errors
        mock_conn.fetch.return_value = [
            {
                "action": "login",
                "email": "hacker@evil.com",
                "failure_reason": "Invalid password",
                "created_at": datetime(2026, 4, 14, 8, 30, 0, tzinfo=timezone.utc),
            },
            {
                "action": "login",
                "email": "user@test.com",
                "failure_reason": "Account locked",
                "created_at": datetime(2026, 4, 14, 9, 0, 0, tzinfo=timezone.utc),
            },
        ]

        result = await aggregator.get_alert_stats()

        assert result.auth_failures_today == 7
        assert len(result.recent_errors) == 2
        assert result.recent_errors[0]["action"] == "login"
        assert result.recent_errors[0]["email"] == "hacker@evil.com"
        # Active alerts from health_monitor
        assert len(result.active_alerts) == 1
        assert result.active_alerts[0]["service"] == "redis"
        assert result.active_alerts[0]["severity"] == "warning"
    finally:
        if original_alert is not None:
            analytics_module.AlertStats = original_alert  # type: ignore[attr-defined]
        elif hasattr(analytics_module, "AlertStats"):
            delattr(analytics_module, "AlertStats")


# ---------------------------------------------------------------------------
# Edge cases & lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_client(aggregator: AnalyticsAggregator) -> None:
    """close() should gracefully close the internal httpx client."""
    mock_client = AsyncMock()
    mock_client.is_closed = False
    aggregator._client = mock_client

    await aggregator.close()

    mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_when_no_client(aggregator: AnalyticsAggregator) -> None:
    """close() should not raise when no client has been created."""
    aggregator._client = None
    await aggregator.close()  # Should not raise


@pytest.mark.asyncio
async def test_get_db_pool_fallback_to_memory_service(
    mock_app_state: MagicMock,
) -> None:
    """_get_db_pool should fall back to memory_service.pool when db_pool is absent."""
    mock_app_state.db_pool = None
    mock_memory_pool = AsyncMock()
    mock_app_state.memory_service = MagicMock()
    mock_app_state.memory_service.pool = mock_memory_pool

    agg = AnalyticsAggregator(mock_app_state)
    pool = await agg._get_db_pool()

    assert pool is mock_memory_pool
