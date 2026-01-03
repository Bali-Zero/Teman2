"""
Unit tests for app/setup/service_initializer.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.setup.service_initializer import (
    _init_background_services,
    _init_critical_services,
    _init_crm_memory,
    _init_database_services,
    _init_intelligent_router,
    _init_rag_components,
    _init_specialized_agents,
    _init_tool_stack,
    _is_transient_error,
    initialize_services,
)


class TestServiceInitializer:
    """Tests for service_initializer.py"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app"""
        app = MagicMock()
        app.state = MagicMock()
        return app

    @pytest.mark.asyncio
    async def test_init_critical_services_success(self, mock_app):
        """Test successful initialization of critical services"""
        with patch("app.setup.service_initializer.SearchService") as mock_search, \
             patch("app.setup.service_initializer.ZantaraAIClient") as mock_ai, \
             patch("app.setup.service_initializer.CollectionManager") as mock_cm, \
             patch("app.setup.service_initializer.create_embeddings_generator") as mock_emb, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_search_instance = MagicMock()
            mock_search.return_value = mock_search_instance
            mock_ai_instance = MagicMock()
            mock_ai.return_value = mock_ai_instance
            mock_cm_instance = MagicMock()
            mock_cm.return_value = mock_cm_instance
            mock_emb.return_value = MagicMock()
            mock_registry.has_critical_failures.return_value = False

            search_service, ai_client = await _init_critical_services(mock_app)

            assert search_service is not None
            assert ai_client is not None
            assert mock_app.state.search_service == mock_search_instance
            assert mock_app.state.ai_client == mock_ai_instance

    @pytest.mark.asyncio
    async def test_init_critical_services_failure(self, mock_app):
        """Test failure of critical services raises RuntimeError"""
        with patch("app.setup.service_initializer.SearchService") as mock_search, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_search.side_effect = RuntimeError("Search service failed")
            mock_registry.has_critical_failures.return_value = True
            mock_registry.format_failures_message.return_value = "Critical services failed"

            with pytest.raises(RuntimeError):
                await _init_critical_services(mock_app)

    @pytest.mark.asyncio
    async def test_init_tool_stack_success(self, mock_app):
        """Test successful initialization of tool stack"""
        with patch("app.setup.service_initializer.ZantaraTools") as mock_tools, \
             patch("app.setup.service_initializer.initialize_mcp_client") as mock_mcp, \
             patch("app.setup.service_initializer.ToolExecutor") as mock_executor, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_tools_instance = MagicMock()
            mock_tools.return_value = mock_tools_instance
            mock_mcp_instance = MagicMock()
            mock_mcp_instance.available_tools = []
            mock_mcp.return_value = mock_mcp_instance
            mock_executor_instance = MagicMock()
            mock_executor.return_value = mock_executor_instance

            result = await _init_tool_stack(mock_app)

            assert result == mock_executor_instance
            assert mock_app.state.tool_executor == mock_executor_instance

    @pytest.mark.asyncio
    async def test_init_tool_stack_mcp_failure(self, mock_app):
        """Test tool stack initialization with MCP failure"""
        with patch("app.setup.service_initializer.ZantaraTools") as mock_tools, \
             patch("app.setup.service_initializer.initialize_mcp_client") as mock_mcp, \
             patch("app.setup.service_initializer.ToolExecutor") as mock_executor, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_tools_instance = MagicMock()
            mock_tools.return_value = mock_tools_instance
            mock_mcp.side_effect = Exception("MCP failed")
            mock_executor_instance = MagicMock()
            mock_executor.return_value = mock_executor_instance

            result = await _init_tool_stack(mock_app)

            assert result == mock_executor_instance
            assert mock_app.state.mcp_client is None

    @pytest.mark.asyncio
    async def test_init_rag_components(self, mock_app):
        """Test initialization of RAG components"""
        mock_search_service = MagicMock()
        mock_cultural_insights = MagicMock()
        mock_app.state.cultural_insights = mock_cultural_insights

        with patch("app.setup.service_initializer.CulturalRAGService") as mock_crag, \
             patch("app.setup.service_initializer.QueryRouter") as mock_qr, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_crag_instance = MagicMock()
            mock_crag.return_value = mock_crag_instance
            mock_qr_instance = MagicMock()
            mock_qr.return_value = mock_qr_instance

            result = await _init_rag_components(mock_app, mock_search_service)

            assert result == mock_qr_instance
            mock_crag.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_specialized_agents(self, mock_app):
        """Test initialization of specialized agents"""
        mock_search = MagicMock()
        mock_ai = MagicMock()
        mock_qr = MagicMock()

        with patch("app.setup.service_initializer.AutonomousResearchService") as mock_ar, \
             patch("app.setup.service_initializer.CrossOracleSynthesisService") as mock_co, \
             patch("app.setup.service_initializer.ClientJourneyOrchestrator") as mock_cj:

            mock_ar_instance = MagicMock()
            mock_ar.return_value = mock_ar_instance
            mock_co_instance = MagicMock()
            mock_co.return_value = mock_co_instance
            mock_cj_instance = MagicMock()
            mock_cj.return_value = mock_cj_instance

            ar, co, cj = await _init_specialized_agents(mock_app, mock_search, mock_ai, mock_qr)

            assert ar == mock_ar_instance
            assert co == mock_co_instance
            assert cj == mock_cj_instance

    @pytest.mark.asyncio
    async def test_init_database_services_no_url(self, mock_app):
        """Test database initialization without DATABASE_URL"""
        with patch("app.setup.service_initializer.settings") as mock_settings, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_settings.database_url = None

            result = await _init_database_services(mock_app)

            assert result is None
            assert mock_app.state.ts_service is None

    @pytest.mark.asyncio
    async def test_init_database_services_success(self, mock_app):
        """Test successful database initialization"""
        with patch("app.setup.service_initializer.settings") as mock_settings, \
             patch("app.setup.service_initializer.asyncpg") as mock_asyncpg, \
             patch("app.setup.service_initializer.init_timesheet_service") as mock_ts, \
             patch("app.setup.service_initializer.service_registry") as mock_registry, \
             patch("app.setup.service_initializer._database_health_check_loop") as mock_health:

            mock_settings.database_url = "postgresql://test"
            mock_settings.db_pool_min_size = 5
            mock_settings.db_pool_max_size = 20
            mock_settings.db_command_timeout = 60

            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.execute = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_pool.acquire = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            mock_ts_service = MagicMock()
            mock_ts_service.start_auto_logout_monitor = AsyncMock()
            mock_ts.return_value = mock_ts_service

            result = await _init_database_services(mock_app)

            assert result == mock_pool
            assert mock_app.state.ts_service == mock_ts_service

    @pytest.mark.asyncio
    async def test_init_database_services_retry(self, mock_app):
        """Test database initialization with retry on transient error"""
        with patch("app.setup.service_initializer.settings") as mock_settings, \
             patch("app.setup.service_initializer.asyncpg") as mock_asyncpg, \
             patch("app.setup.service_initializer.service_registry") as mock_registry, \
             patch("asyncio.sleep") as mock_sleep:

            mock_settings.database_url = "postgresql://test"

            # First attempt fails with transient error, second succeeds
            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=1)
            mock_pool.acquire = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

            connection_error = ConnectionError("Connection timeout")
            mock_asyncpg.create_pool = AsyncMock(side_effect=[connection_error, mock_pool])

            with patch("app.setup.service_initializer.init_timesheet_service") as mock_ts:
                mock_ts_service = MagicMock()
                mock_ts_service.start_auto_logout_monitor = AsyncMock()
                mock_ts.return_value = mock_ts_service

                result = await _init_database_services(mock_app)

                assert result == mock_pool
                mock_sleep.assert_called()

    def test_is_transient_error(self):
        """Test transient error detection"""
        assert _is_transient_error(ConnectionError("connection failed")) is True
        assert _is_transient_error(TimeoutError("timeout")) is True
        assert _is_transient_error(ValueError("invalid value")) is False
        assert _is_transient_error(Exception("permanent error")) is False

    @pytest.mark.asyncio
    async def test_init_crm_memory_success(self, mock_app):
        """Test successful CRM and memory initialization"""
        mock_ai = MagicMock()
        mock_pool = AsyncMock()

        with patch("app.setup.service_initializer.get_auto_crm_service") as mock_crm, \
             patch("app.setup.service_initializer.MemoryServicePostgres") as mock_mem, \
             patch("app.setup.service_initializer.ConversationService") as mock_conv, \
             patch("app.setup.service_initializer.create_collective_memory_workflow") as mock_cmw, \
             patch("app.setup.service_initializer.service_registry") as mock_registry, \
             patch("app.setup.service_initializer.settings") as mock_settings:

            mock_crm_service = MagicMock()
            mock_crm_service.connect = AsyncMock()
            mock_crm.return_value = mock_crm_service

            mock_mem_service = MagicMock()
            mock_mem_service.connect = AsyncMock()
            mock_mem.return_value = mock_mem_service

            mock_conv_service = MagicMock()
            mock_conv.return_value = mock_conv_service

            mock_cmw_instance = MagicMock()
            mock_cmw.return_value = mock_cmw_instance

            mock_settings.database_url = "postgresql://test"
            mock_app.state.db_pool = mock_pool

            await _init_crm_memory(mock_app, mock_ai, mock_pool)

            assert mock_app.state.auto_crm_service == mock_crm_service
            assert mock_app.state.memory_service == mock_mem_service
            assert mock_app.state.conversation_service == mock_conv_service

    @pytest.mark.asyncio
    async def test_init_intelligent_router(self, mock_app):
        """Test initialization of IntelligentRouter"""
        mock_ai = MagicMock()
        mock_search = MagicMock()
        mock_tools = MagicMock()
        mock_crag = MagicMock()
        mock_pool = AsyncMock()

        with patch("app.setup.service_initializer.CollaboratorService") as mock_collab, \
             patch("app.setup.service_initializer.IntelligentRouter") as mock_ir, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_collab_instance = MagicMock()
            mock_collab.return_value = mock_collab_instance

            mock_ir_instance = MagicMock()
            mock_ir.return_value = mock_ir_instance

            await _init_intelligent_router(
                mock_app, mock_ai, mock_search, mock_tools, mock_crag,
                None, None, None, None, mock_pool
            )

            assert mock_app.state.intelligent_router == mock_ir_instance

    @pytest.mark.asyncio
    async def test_init_background_services(self, mock_app):
        """Test initialization of background services"""
        mock_search = MagicMock()
        mock_ai = MagicMock()
        mock_pool = AsyncMock()

        with patch("app.setup.service_initializer.AlertService") as mock_alert, \
             patch("app.setup.service_initializer.HealthMonitor") as mock_health, \
             patch("app.setup.service_initializer.redis_listener") as mock_redis, \
             patch("app.setup.service_initializer.ProactiveComplianceMonitor") as mock_comp, \
             patch("app.setup.service_initializer.create_and_start_scheduler") as mock_sched, \
             patch("app.setup.service_initializer.service_registry") as mock_registry, \
             patch("asyncio.create_task") as mock_task:

            mock_alert_service = MagicMock()
            mock_app.state.alert_service = mock_alert_service

            mock_health_instance = MagicMock()
            mock_health_instance.start = AsyncMock()
            mock_health_instance.set_services = MagicMock()
            mock_health.return_value = mock_health_instance

            mock_redis_task = MagicMock()
            mock_task.return_value = mock_redis_task

            mock_comp_instance = MagicMock()
            mock_comp_instance.start = AsyncMock()
            mock_comp.return_value = mock_comp_instance

            mock_sched_instance = MagicMock()
            mock_sched.return_value = mock_sched_instance

            await _init_background_services(mock_app, mock_search, mock_ai, mock_pool)

            assert mock_app.state.health_monitor == mock_health_instance
            assert mock_app.state.compliance_monitor == mock_comp_instance
            assert mock_app.state.autonomous_scheduler == mock_sched_instance

    @pytest.mark.asyncio
    async def test_initialize_services_already_initialized(self, mock_app):
        """Test that initialize_services skips if already initialized"""
        mock_app.state.services_initialized = True

        await initialize_services(mock_app)

        # Should return early without initializing

    @pytest.mark.asyncio
    async def test_initialize_services_full_flow(self, mock_app):
        """Test full service initialization flow"""
        mock_app.state.services_initialized = False

        with patch("app.setup.service_initializer._init_critical_services") as mock_crit, \
             patch("app.setup.service_initializer._init_tool_stack") as mock_tools, \
             patch("app.setup.service_initializer._init_rag_components") as mock_rag, \
             patch("app.setup.service_initializer._init_specialized_agents") as mock_agents, \
             patch("app.setup.service_initializer._init_database_services") as mock_db, \
             patch("app.setup.service_initializer._init_crm_memory") as mock_crm, \
             patch("app.setup.service_initializer._init_intelligent_router") as mock_ir, \
             patch("app.setup.service_initializer._init_background_services") as mock_bg, \
             patch("app.setup.service_initializer.CollaboratorService") as mock_collab, \
             patch("app.setup.service_initializer.CulturalRAGService") as mock_crag, \
             patch("app.setup.service_initializer.service_registry") as mock_registry:

            mock_search = MagicMock()
            mock_ai = MagicMock()
            mock_crit.return_value = (mock_search, mock_ai)
            mock_tools.return_value = MagicMock()
            mock_rag.return_value = MagicMock()
            mock_agents.return_value = (None, None, None)
            mock_db.return_value = AsyncMock()
            mock_collab.return_value = MagicMock()
            mock_app.state.cultural_insights = MagicMock()

            await initialize_services(mock_app)

            assert mock_app.state.services_initialized is True
            mock_crit.assert_called_once()
            mock_tools.assert_called_once()
            mock_rag.assert_called_once()
            mock_agents.assert_called_once()
            mock_db.assert_called_once()
            mock_crm.assert_called_once()
            mock_ir.assert_called_once()
            mock_bg.assert_called_once()




