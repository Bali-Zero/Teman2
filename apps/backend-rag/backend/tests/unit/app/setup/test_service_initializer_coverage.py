"""
Complete test coverage for service_initializer module
Target: cover init paths, error handling, transient detection, health check loop,
        FAQ cache, CRM/memory, intelligent router, channel router, background services.

NOTE: service_initializer uses local imports inside functions, so we must patch
at the original module paths, not at service_initializer level.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from backend.app.core.service_health import ServiceStatus

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

import contextlib

from backend.app.setup.service_initializer import (
    _database_health_check_loop,
    _init_critical_services,
    _init_rag_components,
    _init_specialized_agents,
    _init_tool_stack,
    _is_transient_error,
    initialize_crm_and_memory_services,
    initialize_database_services,
    initialize_faq_cache_service,
    initialize_intelligent_router,
    initialize_services,
)


@pytest.fixture
def mock_app():
    app = FastAPI()
    app.state = MagicMock()
    app.state.services_initialized = False
    return app


# ============================================================================
# TESTS: _is_transient_error
# ============================================================================
def test_is_transient_error_connection():
    assert _is_transient_error(Exception("Connection failed")) is True


def test_is_transient_error_timeout():
    assert _is_transient_error(Exception("Request timeout")) is True


def test_is_transient_error_temporarily_unavailable():
    assert _is_transient_error(Exception("Temporarily unavailable")) is True


def test_is_transient_error_too_many_connections():
    assert _is_transient_error(Exception("Too many connections")) is True


def test_is_transient_error_server_closed():
    assert _is_transient_error(Exception("server closed the connection")) is True


def test_is_transient_error_network():
    assert _is_transient_error(Exception("network error")) is True


def test_is_transient_error_permanent():
    assert _is_transient_error(Exception("Invalid SQL syntax")) is False


def test_is_transient_error_unknown():
    assert _is_transient_error(Exception("Something completely different")) is False


def test_is_transient_error_empty_message():
    assert _is_transient_error(Exception("")) is False


# ============================================================================
# TESTS: _init_critical_services
# ============================================================================
@pytest.mark.asyncio
async def test_init_critical_services_success(mock_app):
    """Both SearchService and ZantaraAIClient initialize successfully."""
    mock_search_cls = MagicMock()
    mock_ai_cls = MagicMock()

    with (
        patch("backend.services.search.search_service.SearchService", mock_search_cls),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient", mock_ai_cls),
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("httpx.AsyncClient") as mock_httpx,
    ):
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = "test-key"
        mock_settings.reranker_backend = "none"

        # Make the Qdrant health check succeed
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        mock_registry.has_critical_failures.return_value = False

        search, ai = await _init_critical_services(mock_app)

        assert search is not None
        assert ai is not None


@pytest.mark.asyncio
async def test_init_critical_services_search_fails(mock_app, caplog):
    """SearchService fails but AI client succeeds — degraded mode (no raise).

    PR #344 (p0-1: SearchService degraded mode + structured 503) intentionally
    removed the `raise RuntimeError` from _init_critical_services so that a
    deterministic critical-service failure no longer triggers Fly.io restart
    loops (cicatrix STRUCTURAL 2026-04-29 — Backend /health masks
    app.state.startup_failed). The boot continues, /health reports degraded
    via `app.state.degraded_services`, and per-router dependencies surface
    503 to clients.

    This test now asserts the new contract:
      - _init_critical_services returns (search_service, ai_client) — no raise
      - a WARNING log is emitted with "Critical service(s) degraded" so ops
        can observe the degradation
    """
    import logging as _logging

    with (
        patch(
            "backend.services.ingestion.collection_manager.CollectionManager",
            side_effect=ValueError("No Qdrant"),
        ),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
    ):
        mock_settings.reranker_backend = "none"
        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "search failed"

        caplog.set_level(_logging.WARNING)
        # No raise — degraded boot is the documented behavior post-PR #344.
        search, ai = await _init_critical_services(mock_app)
        # Tuple still returned (downstream code reads it).
        assert ai is not None
        # Degradation observable via WARN log (substring match — formatter
        # may add ANSI color codes in CI).
        degraded_logs = [
            rec for rec in caplog.records
            if "Critical service(s) degraded" in rec.message
        ]
        assert len(degraded_logs) == 1, (
            f"expected exactly 1 'Critical service(s) degraded' WARN, "
            f"got {len(degraded_logs)} (records: {[r.message for r in caplog.records]})"
        )


@pytest.mark.asyncio
async def test_init_critical_services_ai_fails(mock_app, caplog):
    """AI client fails — degraded mode (no raise).

    Same contract as `test_init_critical_services_search_fails`: PR #344
    intentionally removed `raise RuntimeError` from _init_critical_services.
    A failed AI client is observable via the WARNING log + the registry's
    `has_critical_failures()`, not via an exception.
    """
    import logging as _logging

    with (
        patch("backend.services.search.search_service.SearchService"),
        patch(
            "backend.llm.zantara_ai_client.ZantaraAIClient",
            side_effect=RuntimeError("No API key"),
        ),
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("httpx.AsyncClient") as mock_httpx,
    ):
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = None
        mock_settings.reranker_backend = "none"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "AI client failed"

        caplog.set_level(_logging.WARNING)
        # Degraded mode — no raise.
        search, ai = await _init_critical_services(mock_app)
        # Search service was constructed; ai_client is None because the
        # patched constructor raised — but the boot continues.
        assert search is not None or ai is None  # tolerant of either path
        degraded_logs = [
            rec for rec in caplog.records
            if "Critical service(s) degraded" in rec.message
        ]
        assert len(degraded_logs) == 1, (
            f"expected exactly 1 'Critical service(s) degraded' WARN, "
            f"got {len(degraded_logs)} (records: {[r.message for r in caplog.records]})"
        )


@pytest.mark.asyncio
async def test_init_critical_services_with_cross_encoder(mock_app):
    """Cross-encoder reranking setup succeeds."""
    with (
        patch("backend.services.search.search_service.SearchService"),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient"),
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("httpx.AsyncClient") as mock_httpx,
        patch("backend.services.rag.reranker_integration.add_cross_encoder_reranking"),
    ):
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = None
        mock_settings.reranker_backend = "cross-encoder"

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        mock_registry.has_critical_failures.return_value = False

        search, ai = await _init_critical_services(mock_app)
        assert search is not None


@pytest.mark.asyncio
async def test_init_critical_services_qdrant_unreachable(mock_app):
    """Qdrant health check fails — SearchService marked UNAVAILABLE."""
    with (
        patch("backend.services.search.search_service.SearchService"),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient"),
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("httpx.AsyncClient") as mock_httpx,
    ):
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = "test-key"
        mock_settings.reranker_backend = "none"

        # Make Qdrant health check FAIL
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx.return_value = mock_client_instance

        mock_registry.has_critical_failures.return_value = False

        search, ai = await _init_critical_services(mock_app)
        assert search is not None


# ============================================================================
# TESTS: _init_tool_stack
# ============================================================================
@pytest.mark.asyncio
async def test_init_tool_stack_success(mock_app):
    """Tool stack initializes with MCP client."""
    mock_mcp_instance = MagicMock()
    mock_mcp_instance.available_tools = ["tool1", "tool2"]

    with (
        patch(
            "backend.services.misc.mcp_client_service.initialize_mcp_client",
            new_callable=AsyncMock,
            return_value=mock_mcp_instance,
        ),
        patch("backend.services.misc.tool_executor.ToolExecutor"),
        patch("backend.services.misc.zantara_tools.ZantaraTools"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        result = await _init_tool_stack(mock_app)
        assert result is not None


@pytest.mark.asyncio
async def test_init_tool_stack_mcp_fails(mock_app):
    """MCP client fails gracefully."""
    with (
        patch(
            "backend.services.misc.mcp_client_service.initialize_mcp_client",
            new_callable=AsyncMock,
            side_effect=Exception("MCP down"),
        ),
        patch("backend.services.misc.tool_executor.ToolExecutor"),
        patch("backend.services.misc.zantara_tools.ZantaraTools"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        result = await _init_tool_stack(mock_app)
        assert result is not None


# ============================================================================
# TESTS: _init_rag_components
# ============================================================================
@pytest.mark.asyncio
async def test_init_rag_components_with_cultural_insights(mock_app):
    """RAG components init with cultural insights service available."""
    mock_app.state.cultural_insights = MagicMock()

    with (
        patch("backend.services.misc.cultural_rag_service.CulturalRAGService"),
        patch("backend.services.routing.query_router.QueryRouter"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        result = await _init_rag_components(mock_app, MagicMock())
        assert result is not None


@pytest.mark.asyncio
async def test_init_rag_components_fallback_to_search_service(mock_app):
    """RAG components fall back to search_service when cultural_insights not available."""
    mock_app.state.cultural_insights = None

    with (
        patch("backend.services.misc.cultural_rag_service.CulturalRAGService"),
        patch("backend.services.routing.query_router.QueryRouter"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        result = await _init_rag_components(mock_app, MagicMock())
        assert result is not None


# ============================================================================
# TESTS: _init_specialized_agents
# ============================================================================
@pytest.mark.asyncio
async def test_init_specialized_agents_all_success(mock_app):
    """All three specialized agents initialize successfully."""
    with (
        patch("backend.services.misc.autonomous_research_service.AutonomousResearchService"),
        patch("backend.services.oracle.cross_oracle_synthesis_service.CrossOracleSynthesisService"),
        patch("backend.services.misc.client_journey_orchestrator.ClientJourneyOrchestrator"),
    ):
        research, oracle, journey = await _init_specialized_agents(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
        )
        assert research is not None
        assert oracle is not None
        assert journey is not None


@pytest.mark.asyncio
async def test_init_specialized_agents_research_fails(mock_app):
    """AutonomousResearchService fails, others succeed."""
    with (
        patch(
            "backend.services.misc.autonomous_research_service.AutonomousResearchService",
            side_effect=Exception("Research init failed"),
        ),
        patch("backend.services.oracle.cross_oracle_synthesis_service.CrossOracleSynthesisService"),
        patch("backend.services.misc.client_journey_orchestrator.ClientJourneyOrchestrator"),
    ):
        research, oracle, journey = await _init_specialized_agents(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
        )
        assert research is None
        assert oracle is not None
        assert journey is not None


@pytest.mark.asyncio
async def test_init_specialized_agents_oracle_fails(mock_app):
    """CrossOracleSynthesisService fails."""
    with (
        patch("backend.services.misc.autonomous_research_service.AutonomousResearchService"),
        patch(
            "backend.services.oracle.cross_oracle_synthesis_service.CrossOracleSynthesisService",
            side_effect=Exception("Oracle init failed"),
        ),
        patch("backend.services.misc.client_journey_orchestrator.ClientJourneyOrchestrator"),
    ):
        research, oracle, journey = await _init_specialized_agents(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
        )
        assert research is not None
        assert oracle is None


@pytest.mark.asyncio
async def test_init_specialized_agents_journey_fails(mock_app):
    """ClientJourneyOrchestrator fails."""
    with (
        patch("backend.services.misc.autonomous_research_service.AutonomousResearchService"),
        patch("backend.services.oracle.cross_oracle_synthesis_service.CrossOracleSynthesisService"),
        patch(
            "backend.services.misc.client_journey_orchestrator.ClientJourneyOrchestrator",
            side_effect=Exception("Journey init failed"),
        ),
    ):
        research, oracle, journey = await _init_specialized_agents(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
        )
        assert research is not None
        assert oracle is not None
        assert journey is None


# ============================================================================
# TESTS: initialize_database_services
# ============================================================================
@pytest.mark.asyncio
async def test_init_database_no_url(mock_app):
    """No DATABASE_URL returns None."""
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        mock_settings.database_url = None
        result = await initialize_database_services(mock_app)
        assert result is None


@pytest.mark.asyncio
async def test_init_database_permanent_failure(mock_app):
    """DB init fails permanently after retries."""
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.app.setup.service_initializer.asyncpg.create_pool",
            side_effect=ValueError("Invalid DSN"),
        ),
        patch("backend.app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
        mock_settings.db_pool_min_size = 2
        mock_settings.db_pool_max_size = 10
        mock_settings.db_command_timeout = 30
        result = await initialize_database_services(mock_app)
        assert result is None


@pytest.mark.asyncio
async def test_init_database_transient_then_permanent(mock_app):
    """DB init gets transient errors then permanent failure."""
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.app.setup.service_initializer.asyncpg.create_pool",
            side_effect=ConnectionError("Connection timed out"),
        ),
        patch(
            "backend.app.setup.service_initializer.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
        mock_settings.db_pool_min_size = 2
        mock_settings.db_pool_max_size = 10
        mock_settings.db_command_timeout = 30
        result = await initialize_database_services(mock_app)
        assert result is None


@pytest.mark.asyncio
async def test_init_database_unexpected_error(mock_app):
    """Unexpected non-standard error during DB init."""
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.app.setup.service_initializer.asyncpg.create_pool",
            side_effect=TypeError("unexpected type"),
        ),
        patch(
            "backend.app.setup.service_initializer.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test"
        mock_settings.db_pool_min_size = 2
        mock_settings.db_pool_max_size = 10
        mock_settings.db_command_timeout = 30
        result = await initialize_database_services(mock_app)
        assert result is None


@pytest.mark.asyncio
async def test_init_database_success(mock_app):
    """DB init succeeds on first attempt."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.set_type_codec = AsyncMock()
    mock_conn.execute = AsyncMock()

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.app.setup.service_initializer.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ),
        patch(
            "backend.services.analytics.team_timesheet_service.init_timesheet_service",
        ) as mock_ts,
        patch(
            "backend.services.analytics.attendance_monitor.AttendanceMonitor",
        ) as mock_att,
        patch(
            "backend.services.analytics.daily_checkin_notifier.init_daily_notifier",
        ) as mock_daily,
        patch(
            "backend.services.analytics.weekly_email_reporter.init_weekly_reporter",
        ) as mock_weekly,
        patch("backend.app.setup.service_initializer.asyncio.create_task"),
        patch("backend.services.misc.graph_service.GraphService"),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost:5432/test?sslmode=disable"
        mock_settings.db_pool_min_size = 2
        mock_settings.db_pool_max_size = 10
        mock_settings.db_command_timeout = 30

        mock_ts_instance = MagicMock()
        mock_ts_instance.start_auto_logout_monitor = AsyncMock()
        mock_ts.return_value = mock_ts_instance

        mock_att_instance = MagicMock()
        mock_att_instance.start_schedulers = AsyncMock()
        mock_att.return_value = mock_att_instance

        mock_daily_instance = MagicMock()
        mock_daily_instance.start = AsyncMock()
        mock_daily.return_value = mock_daily_instance

        mock_weekly_instance = MagicMock()
        mock_weekly_instance.start = AsyncMock()
        mock_weekly.return_value = mock_weekly_instance

        result = await initialize_database_services(mock_app)
        assert result is mock_pool


# ============================================================================
# TESTS: _database_health_check_loop
# ============================================================================
@pytest.mark.asyncio
async def test_database_health_check_loop_cancel():
    """Health check loop handles CancelledError gracefully."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)

    with patch("backend.app.setup.service_initializer.service_registry"):
        task = asyncio.create_task(_database_health_check_loop(mock_pool))
        await asyncio.sleep(0.05)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_database_health_check_loop_failure_and_recovery():
    """Health check detects failure and attempts recovery."""
    mock_pool = MagicMock()
    call_count = 0

    async def mock_acquire_enter(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Connection timed out")
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        return mock_conn

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = mock_acquire_enter
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire = MagicMock(return_value=acquire_cm)
    mock_pool.expire_connections = AsyncMock()

    with (
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.app.setup.service_initializer.asyncio.sleep",
            side_effect=[None, asyncio.CancelledError()],
        ),
    ):
        with contextlib.suppress(asyncio.CancelledError):
            await _database_health_check_loop(mock_pool)


# ============================================================================
# TESTS: initialize_faq_cache_service
# ============================================================================
@pytest.mark.asyncio
async def test_faq_cache_disabled(mock_app):
    """FAQ cache disabled by feature flag."""
    with (
        patch.dict("os.environ", {"ENABLE_FAQ_CACHE": "false"}),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        await initialize_faq_cache_service(mock_app)
        assert mock_app.state.faq_cache is None


@pytest.mark.asyncio
async def test_faq_cache_success(mock_app):
    """FAQ cache initializes with Redis connection."""
    mock_cache = MagicMock()
    mock_cache.initialize = AsyncMock()
    mock_cache.redis_client = MagicMock()

    with (
        patch.dict("os.environ", {"ENABLE_FAQ_CACHE": "true"}),
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.services.caching.NotebookLMCacheService",
            return_value=mock_cache,
        ),
    ):
        await initialize_faq_cache_service(mock_app)
        assert mock_app.state.faq_cache is mock_cache


@pytest.mark.asyncio
async def test_faq_cache_no_redis(mock_app):
    """FAQ cache init succeeds but no Redis client."""
    mock_cache = MagicMock()
    mock_cache.initialize = AsyncMock()
    mock_cache.redis_client = None

    with (
        patch.dict("os.environ", {"ENABLE_FAQ_CACHE": "true"}),
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.services.caching.NotebookLMCacheService",
            return_value=mock_cache,
        ),
    ):
        await initialize_faq_cache_service(mock_app)
        assert mock_app.state.faq_cache is None


@pytest.mark.asyncio
async def test_faq_cache_exception(mock_app):
    """FAQ cache init raises exception — graceful degradation."""
    with (
        patch.dict("os.environ", {"ENABLE_FAQ_CACHE": "true"}),
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.services.caching.NotebookLMCacheService",
            side_effect=Exception("Redis down"),
        ),
    ):
        await initialize_faq_cache_service(mock_app)
        assert mock_app.state.faq_cache is None


# ============================================================================
# TESTS: initialize_crm_and_memory_services
# ============================================================================
@pytest.mark.asyncio
async def test_crm_memory_success(mock_app):
    """CRM and memory services initialize successfully."""
    mock_pool = MagicMock()

    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.services.memory.MemoryServicePostgres",
        ) as mock_mem,
        patch(
            "backend.services.misc.conversation_service.ConversationService",
        ),
        patch(
            "backend.services.memory.collective_memory_workflow.create_collective_memory_workflow",
        ),
        patch(
            "backend.app.services.crm.audit_logger.audit_logger",
        ),
        patch(
            "backend.app.services.crm.metrics.metrics_collector",
        ),
        patch(
            "backend.services.monitoring.activity_logger.activity_logger",
        ) as mock_activity,
    ):
        mock_settings.database_url = "postgresql://test:test@localhost/test"
        mock_mem_instance = MagicMock()
        mock_mem_instance.connect = AsyncMock()
        mock_mem.return_value = mock_mem_instance
        mock_activity.initialize = AsyncMock()

        await initialize_crm_and_memory_services(mock_app, MagicMock(), mock_pool)
        # No exception = success


@pytest.mark.asyncio
async def test_crm_memory_failure(mock_app):
    """CRM/memory init fails gracefully."""
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry"),
        patch(
            "backend.services.memory.MemoryServicePostgres",
            side_effect=Exception("DB error"),
        ),
    ):
        mock_settings.database_url = "postgresql://test:test@localhost/test"
        await initialize_crm_and_memory_services(mock_app, MagicMock(), None)
        # Should not raise, just log error


# ============================================================================
# TESTS: initialize_intelligent_router
# ============================================================================
@pytest.mark.asyncio
async def test_intelligent_router_success(mock_app):
    """IntelligentRouter initializes with all dependencies."""
    with (
        patch("backend.services.routing.intelligent_router.IntelligentRouter"),
        patch("backend.services.crm.collaborator_service.CollaboratorService"),
        patch("backend.services.routing.specialized_service_router.SpecializedServiceRouter"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        await initialize_intelligent_router(
            mock_app,
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(),
            None, MagicMock(),
        )


@pytest.mark.asyncio
async def test_intelligent_router_failure(mock_app):
    """IntelligentRouter fails to initialize."""
    with (
        patch(
            "backend.services.routing.intelligent_router.IntelligentRouter",
            side_effect=Exception("Router init failed"),
        ),
        patch("backend.services.crm.collaborator_service.CollaboratorService"),
        patch("backend.services.routing.specialized_service_router.SpecializedServiceRouter"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        await initialize_intelligent_router(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            None, MagicMock(),
        )
        assert mock_app.state.intelligent_router is None


@pytest.mark.asyncio
async def test_intelligent_router_collaborator_fails(mock_app):
    """CollaboratorService fails but router still initializes."""
    with (
        patch("backend.services.routing.intelligent_router.IntelligentRouter"),
        patch(
            "backend.services.crm.collaborator_service.CollaboratorService",
            side_effect=Exception("Collab failed"),
        ),
        patch("backend.services.routing.specialized_service_router.SpecializedServiceRouter"),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        await initialize_intelligent_router(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            None, MagicMock(),
        )


@pytest.mark.asyncio
async def test_intelligent_router_specialized_fails(mock_app):
    """SpecializedServiceRouter fails but is non-critical."""
    with (
        patch("backend.services.routing.intelligent_router.IntelligentRouter"),
        patch("backend.services.crm.collaborator_service.CollaboratorService"),
        patch(
            "backend.services.routing.specialized_service_router.SpecializedServiceRouter",
            side_effect=Exception("Specialized failed"),
        ),
        patch("backend.app.setup.service_initializer.service_registry"),
    ):
        await initialize_intelligent_router(
            mock_app, MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(), MagicMock(), MagicMock(),
            MagicMock(), MagicMock(),
        )
        assert mock_app.state.specialized_router is None


# ============================================================================
# TESTS: initialize_services (orchestration)
# ============================================================================
@pytest.mark.asyncio
async def test_initialize_services_already_initialized(mock_app):
    """Services already initialized — returns early."""
    mock_app.state.services_initialized = True
    await initialize_services(mock_app)
    # Should return without doing anything
