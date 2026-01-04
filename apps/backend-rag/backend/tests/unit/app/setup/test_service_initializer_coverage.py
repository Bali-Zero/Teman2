"""
Complete test coverage for service_initializer module
Target: 100% coverage
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from fastapi import FastAPI
from app.core.service_health import ServiceStatus

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.service_initializer import (
    _database_health_check_loop,
    _init_background_services,
    _is_transient_error,
    initialize_database_services,
    initialize_services,
    _init_critical_services,
    _init_tool_stack,
    _init_rag_components,
    _init_specialized_agents,
    initialize_crm_and_memory_services,
    initialize_intelligent_router
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
    with patch("app.setup.service_initializer.SearchService") as MockSearch, \
         patch("app.setup.service_initializer.ZantaraAIClient") as MockAI, \
         patch("app.setup.service_initializer.service_registry") as mock_registry, \
         patch("services.ingestion.collection_manager.CollectionManager"), \
         patch("services.routing.conflict_resolver.ConflictResolver"), \
         patch("services.routing.query_router_integration.QueryRouterIntegration"), \
         patch("core.embeddings.create_embeddings_generator"), \
         patch("services.misc.cultural_insights_service.CulturalInsightsService"):
        
        mock_registry.has_critical_failures.return_value = False
        search, ai = await _init_critical_services(mock_app)
        assert search is not None
        assert ai is not None
        mock_registry.register.assert_any_call("search", ServiceStatus.HEALTHY)
        mock_registry.register.assert_any_call("ai", ServiceStatus.HEALTHY)

@pytest.mark.asyncio
async def test_init_critical_services_search_failure_generic(mock_app):
    with patch("app.setup.service_initializer.SearchService", side_effect=RuntimeError("Unexpected")) as MockSearch, \
         patch("app.setup.service_initializer.ZantaraAIClient") as MockAI, \
         patch("app.setup.service_initializer.service_registry") as mock_registry, \
         patch("services.ingestion.collection_manager.CollectionManager"):
    
        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "Critical Error"
        
        with pytest.raises(RuntimeError):
            await _init_critical_services(mock_app)
            
        mock_registry.register.assert_any_call("search", ServiceStatus.UNAVAILABLE, error="Unexpected")

@pytest.mark.asyncio
async def test_init_critical_services_ai_failure_generic(mock_app):
    with patch("app.setup.service_initializer.SearchService"), \
         patch("app.setup.service_initializer.ZantaraAIClient", side_effect=RuntimeError("UnexpectedAI")) as MockAI, \
         patch("app.setup.service_initializer.service_registry") as mock_registry, \
         patch("services.ingestion.collection_manager.CollectionManager"), \
         patch("services.routing.conflict_resolver.ConflictResolver"), \
         patch("services.routing.query_router_integration.QueryRouterIntegration"), \
         patch("core.embeddings.create_embeddings_generator"), \
         patch("services.misc.cultural_insights_service.CulturalInsightsService"):
    
        mock_registry.has_critical_failures.return_value = True
        
        with pytest.raises(RuntimeError):
            await _init_critical_services(mock_app)
            
        mock_registry.register.assert_any_call("ai", ServiceStatus.UNAVAILABLE, error="UnexpectedAI")

# ============================================================================ 
# TESTS: _init_tool_stack
# ============================================================================ 
@pytest.mark.asyncio
async def test_init_tool_stack_mcp_success(mock_app):
    with patch("app.setup.service_initializer.ZantaraTools"), \
         patch("app.setup.service_initializer.initialize_mcp_client", new_callable=AsyncMock) as mock_mcp_init, \
         patch("app.setup.service_initializer.ToolExecutor") as MockExecutor, \
         patch("app.setup.service_initializer.service_registry") as mock_registry:
    
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
        
    with patch("app.setup.service_initializer.CulturalRAGService") as MockRAG, \
         patch("app.setup.service_initializer.QueryRouter"):
        
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
        patch("app.setup.service_initializer.AutonomousResearchService", side_effect=Exception("Fail1")),
        patch("app.setup.service_initializer.CrossOracleSynthesisService", side_effect=Exception("Fail2")),
        patch("app.setup.service_initializer.ClientJourneyOrchestrator", side_effect=Exception("Fail3"))
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
    with patch("app.setup.service_initializer.settings") as mock_settings, \
         patch("app.setup.service_initializer.service_registry") as mock_registry:
        mock_settings.database_url = None
        
        pool = await initialize_database_services(mock_app)
        assert pool is None
        mock_registry.register.assert_called_with("database", ServiceStatus.UNAVAILABLE, error="DATABASE_URL not configured", critical=False)

@pytest.mark.asyncio
async def test_initialize_database_services_retry_then_success(mock_app):
    with patch("app.setup.service_initializer.settings") as mock_settings, \
         patch("app.setup.service_initializer.asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool, \
         patch("app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("services.analytics.daily_checkin_notifier.init_daily_notifier"), \
         patch("services.analytics.team_timesheet_service.init_timesheet_service"), \
         patch("services.analytics.weekly_email_reporter.init_weekly_reporter"), \
         patch("app.setup.service_initializer.asyncio.create_task"):
         
        mock_settings.database_url = "postgres://..."
        
        # Simplify: Just verify create_pool is called twice.
        # We mock create_pool to raise then succeed.
        # But we need the success case to return a pool that works enough to pass the validation check.
        # Validation check: async with pool.acquire() as conn: await conn.fetchval(...)
        
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        
        # Make acquire return an async context manager cleanly
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        
        # IMPORTANT: acquire is called on the pool object returned by create_pool
        mock_pool.acquire.return_value = mock_cm
        
        # When awaited, create_pool return value is used.
        # AsyncMock side_effect with values: returns the value (wrapped in coroutine).
        mock_create_pool.side_effect = [
            ConnectionError("Connection timeout"), # Attempt 1
            mock_pool # Attempt 2
        ]
        
        pool = await initialize_database_services(mock_app)
        
        assert pool == mock_pool
        assert mock_create_pool.call_count == 2
        mock_sleep.assert_called_once()

# ...

@pytest.mark.asyncio
async def test_database_health_check_loop_exception_recovery():
    mock_pool = MagicMock()
    
    with patch("app.setup.service_initializer.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("app.setup.service_initializer.service_registry") as mock_registry:
         
        # Success CM
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        success_cm = MagicMock()
        success_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        success_cm.__aexit__ = AsyncMock(return_value=None)
        
        # Make acquire raise exception once then succeed
        mock_pool.acquire.side_effect = [
            Exception("Connection failed"), 
            success_cm,
            success_cm
        ]
        
        # We need to run the loop for a bit then cancel
        task = asyncio.create_task(_database_health_check_loop(mock_pool))
        
        # Allow loop to run
        await asyncio.sleep(0.01)
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        # Verify register was called with DEGRADED
        mock_registry.register.assert_any_call("database", ServiceStatus.DEGRADED, error="Connection failed")

# ============================================================================ 
# TESTS: initialize_services
# ============================================================================ 
@pytest.mark.asyncio
async def test_initialize_services_already_init(mock_app):
    mock_app.state.services_initialized = True
    with patch("app.setup.service_initializer.logger") as mock_logger:
        await initialize_services(mock_app)
        # Should return early
        mock_logger.info.assert_not_called()
