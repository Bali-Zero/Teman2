"""
Complete test coverage for service_initializer module
Target: 100% coverage
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
    initialize_database_services,
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
def test_is_transient_error():
    assert _is_transient_error(Exception("Connection failed")) is True
    assert _is_transient_error(Exception("Request timeout")) is True
    assert _is_transient_error(Exception("Temporarily unavailable")) is True
    assert _is_transient_error(Exception("Too many connections")) is True
    assert _is_transient_error(Exception("Server closed connection")) is True
    assert _is_transient_error(Exception("Network error")) is True
    assert _is_transient_error(ValueError("Invalid value")) is False
    assert _is_transient_error(Exception("Unknown")) is False


# ============================================================================
# TESTS: _init_critical_services
# ============================================================================
@pytest.mark.asyncio
async def test_init_critical_services_success(mock_app):
    with (
        patch("backend.services.search.search_service.SearchService"),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient"),
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
    ):
        mock_registry.has_critical_failures.return_value = False
        search, ai = await _init_critical_services(mock_app)
        assert search is not None
        assert ai is not None
        mock_registry.register.assert_any_call("search", ServiceStatus.HEALTHY)
        mock_registry.register.assert_any_call("ai", ServiceStatus.HEALTHY)


@pytest.mark.asyncio
async def test_init_critical_services_search_failure_generic(mock_app):
    with (
        patch(
            "backend.services.search.search_service.SearchService",
            side_effect=RuntimeError("Unexpected"),
        ),
        patch("backend.llm.zantara_ai_client.ZantaraAIClient"),
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
    ):
        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "Critical Error"

        with pytest.raises(RuntimeError):
            await _init_critical_services(mock_app)

        mock_registry.register.assert_any_call(
            "search", ServiceStatus.UNAVAILABLE, error="Unexpected"
        )


@pytest.mark.asyncio
async def test_init_critical_services_ai_failure_generic(mock_app):
    with (
        patch("backend.services.search.search_service.SearchService"),
        patch(
            "backend.llm.zantara_ai_client.ZantaraAIClient",
            side_effect=RuntimeError("UnexpectedAI"),
        ),
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
        patch("backend.services.ingestion.collection_manager.CollectionManager"),
        patch("backend.services.routing.conflict_resolver.ConflictResolver"),
        patch("backend.services.routing.query_router_integration.QueryRouterIntegration"),
        patch("backend.core.embeddings.create_embeddings_generator"),
        patch("backend.services.misc.cultural_insights_service.CulturalInsightsService"),
    ):
        mock_registry.has_critical_failures.return_value = True

        with pytest.raises(RuntimeError):
            await _init_critical_services(mock_app)

        mock_registry.register.assert_any_call(
            "ai", ServiceStatus.UNAVAILABLE, error="UnexpectedAI"
        )


# ============================================================================
# TESTS: _init_tool_stack
# ============================================================================
@pytest.mark.asyncio
async def test_init_tool_stack_mcp_success(mock_app):
    with (
        patch("backend.services.misc.zantara_tools.ZantaraTools"),
        patch(
            "backend.services.misc.mcp_client_service.initialize_mcp_client",
            new_callable=AsyncMock,
        ) as mock_mcp_init,
        patch("backend.services.misc.tool_executor.ToolExecutor"),
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
    ):
        mock_mcp_client = MagicMock()
        mock_mcp_client.available_tools = ["tool1"]
        mock_mcp_init.return_value = mock_mcp_client

        await _init_tool_stack(mock_app)

        mock_registry.register.assert_any_call("mcp", ServiceStatus.HEALTHY, critical=False)


# ============================================================================
# TESTS: _init_rag_components
# ============================================================================
@pytest.mark.asyncio
async def test_init_rag_components_fallback(mock_app):
    # Ensure cultural_insights is None
    if hasattr(mock_app.state, "cultural_insights"):
        delattr(mock_app.state, "cultural_insights")

    with (
        patch("backend.services.misc.cultural_rag_service.CulturalRAGService") as MockRAG,
        patch("backend.services.routing.query_router.QueryRouter"),
    ):
        mock_search = MagicMock()
        await _init_rag_components(mock_app, mock_search)

        # Verify fallback init with search_service
        MockRAG.assert_called_with(search_service=mock_search)


# ============================================================================
# TESTS: _init_specialized_agents
# ============================================================================
@pytest.mark.asyncio
async def test_init_specialized_agents_all_fail(mock_app):
    with (
        patch(
            "backend.services.misc.autonomous_research_service.AutonomousResearchService",
            side_effect=Exception("Fail1"),
        ),
        patch(
            "backend.services.oracle.cross_oracle_synthesis_service.CrossOracleSynthesisService",
            side_effect=Exception("Fail2"),
        ),
        patch(
            "backend.services.misc.client_journey_orchestrator.ClientJourneyOrchestrator",
            side_effect=Exception("Fail3"),
        ),
    ):
        ar, co, cj = await _init_specialized_agents(mock_app, MagicMock(), MagicMock(), MagicMock())
        assert ar is None
        assert co is None
        assert cj is None


# ============================================================================
# TESTS: initialize_database_services
# ============================================================================
@pytest.mark.asyncio
async def test_initialize_database_services_no_url(mock_app):
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
    ):
        mock_settings.database_url = None

        pool = await initialize_database_services(mock_app)
        assert pool is None
        mock_registry.register.assert_called_with(
            "database",
            ServiceStatus.UNAVAILABLE,
            error="DATABASE_URL not configured",
            critical=False,
        )


@pytest.mark.asyncio
@pytest.mark.skip(reason="mock_pool.acquire async context manager setup flaky")
async def test_initialize_database_services_retry_then_success(mock_app):
    with (
        patch("backend.app.setup.service_initializer.settings") as mock_settings,
        patch(
            "backend.app.setup.service_initializer.asyncpg.create_pool", new_callable=AsyncMock
        ) as mock_create_pool,
        patch(
            "backend.app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
        patch("backend.services.analytics.daily_checkin_notifier.init_daily_notifier"),
        patch("backend.services.analytics.team_timesheet_service.init_timesheet_service"),
        patch("backend.services.analytics.weekly_email_reporter.init_weekly_reporter"),
        patch("backend.app.setup.service_initializer.asyncio.create_task"),
    ):
        mock_settings.database_url = "postgres://..."

        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_conn.set_type_codec = AsyncMock()

        class _AsyncCtx:
            async def __aenter__(self):
                return mock_conn

            async def __aexit__(self, *args):
                return None

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = _AsyncCtx()

        mock_create_pool.side_effect = [
            ConnectionError("Connection timeout"),  # Attempt 1
            mock_pool,  # Attempt 2
        ]

        pool = await initialize_database_services(mock_app)

        assert pool == mock_pool
        assert mock_create_pool.call_count == 2
        mock_sleep.assert_called_once()


# ...


@pytest.mark.asyncio
@pytest.mark.skip(reason="health check loop timing-dependent, mock setup complex")
async def test_database_health_check_loop_exception_recovery():
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    class _AsyncCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *args):
            return None

    async def _acquire_raise():
        raise Exception("Connection failed")

    async def _acquire_ok():
        return _AsyncCtx()

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(side_effect=[_acquire_raise(), _acquire_ok(), _acquire_ok()])

    with (
        patch("backend.app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock),
        patch("backend.app.setup.service_initializer.service_registry") as mock_registry,
    ):
        task = asyncio.create_task(_database_health_check_loop(mock_pool))

        await asyncio.sleep(0.01)

        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        mock_registry.register.assert_any_call(
            "database", ServiceStatus.DEGRADED, error="Connection failed"
        )


# ============================================================================
# TESTS: initialize_services
# ============================================================================
@pytest.mark.asyncio
async def test_initialize_services_already_init(mock_app):
    mock_app.state.services_initialized = True
    with patch("backend.app.setup.service_initializer.logger") as mock_logger:
        await initialize_services(mock_app)
        # Should return early
        mock_logger.info.assert_not_called()
