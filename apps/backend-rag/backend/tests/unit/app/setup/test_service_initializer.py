"""
Tests for service_initializer module
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from backend.app.setup.service_initializer import (
    _init_critical_services,
    _init_rag_components,
    _init_specialized_agents,
    _init_tool_stack,
    _is_transient_error,
    initialize_crm_and_memory_services,
    initialize_database_services,
    initialize_intelligent_router,
)


class TestIsTransientError:
    """Test _is_transient_error function"""

    def test_connection_error(self):
        """Test connection error is transient"""
        error = ConnectionError("Connection failed")
        assert _is_transient_error(error) is True

    def test_timeout_error(self):
        """Test timeout error is transient"""
        error = Exception("Timeout occurred")
        assert _is_transient_error(error) is True

    def test_temporarily_unavailable(self):
        """Test temporarily unavailable error is transient"""
        error = Exception("Service temporarily unavailable")
        assert _is_transient_error(error) is True

    def test_too_many_connections(self):
        """Test too many connections error is transient"""
        error = Exception("Too many connections")
        assert _is_transient_error(error) is True

    def test_server_closed(self):
        """Test server closed error is transient"""
        error = Exception("Server closed connection")
        assert _is_transient_error(error) is True

    def test_network_error(self):
        """Test network error is transient"""
        error = Exception("Network error occurred")
        assert _is_transient_error(error) is True

    def test_permanent_error(self):
        """Test permanent error is not transient"""
        error = ValueError("Invalid value")
        assert _is_transient_error(error) is False

    def test_unknown_error(self):
        """Test unknown error is not transient"""
        error = Exception("Unknown error")
        assert _is_transient_error(error) is False


class TestInitCriticalServices:
    """Test _init_critical_services function"""

    @pytest.mark.asyncio
    @patch("backend.services.misc.cultural_insights_service.CulturalInsightsService")
    @patch("backend.services.routing.query_router_integration.QueryRouterIntegration")
    @patch("backend.services.routing.conflict_resolver.ConflictResolver")
    @patch("backend.services.ingestion.collection_manager.CollectionManager")
    @patch("backend.core.embeddings.create_embeddings_generator")
    @patch("backend.app.setup.service_initializer.ZantaraAIClient")
    @patch("backend.app.setup.service_initializer.SearchService")
    @patch("backend.app.setup.service_initializer.service_registry")
    async def test_init_critical_services_success(
        self,
        mock_registry,
        mock_search_service,
        mock_ai_client,
        mock_embedder,
        mock_collection_manager,
        mock_conflict_resolver,
        mock_query_router,
        mock_cultural_insights,
    ):
        """Test successful initialization of critical services"""
        app = FastAPI()
        app.state = MagicMock()

        mock_registry.has_critical_failures.return_value = False

        mock_search = MagicMock()
        mock_search_service.return_value = mock_search
        mock_ai = MagicMock()
        mock_ai_client.return_value = mock_ai

        search_service, ai_client = await _init_critical_services(app)

        assert search_service is not None
        assert ai_client is not None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.service_registry")
    @patch("backend.app.setup.service_initializer.SearchService")
    async def test_init_critical_services_search_failure(self, mock_search_service, mock_registry):
        """Test SearchService initialization failure"""
        app = FastAPI()
        app.state = MagicMock()

        mock_search_service.side_effect = ConnectionError("Qdrant connection failed")
        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "Critical services failed"

        with pytest.raises(RuntimeError):
            await _init_critical_services(app)

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.service_registry")
    @patch("backend.app.setup.service_initializer.ZantaraAIClient")
    @patch("backend.app.setup.service_initializer.SearchService")
    async def test_init_critical_services_ai_failure(
        self, mock_search_service, mock_ai_client, mock_registry
    ):
        """Test ZantaraAIClient initialization failure"""
        app = FastAPI()
        app.state = MagicMock()

        mock_search_service.return_value = MagicMock()
        mock_ai_client.side_effect = ValueError("AI client init failed")
        mock_registry.has_critical_failures.return_value = True
        mock_registry.format_failures_message.return_value = "Critical services failed"

        with pytest.raises(RuntimeError):
            await _init_critical_services(app)


class TestInitToolStack:
    """Test _init_tool_stack function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.initialize_mcp_client")
    @patch("backend.app.setup.service_initializer.ZantaraTools")
    @patch("backend.app.setup.service_initializer.ToolExecutor")
    async def test_init_tool_stack_success(
        self, mock_tool_executor, mock_zantara_tools, mock_mcp_client
    ):
        """Test successful tool stack initialization"""
        app = FastAPI()
        app.state = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.available_tools = [MagicMock(), MagicMock()]
        mock_mcp_client.return_value = mock_mcp

        mock_executor = MagicMock()
        mock_tool_executor.return_value = mock_executor

        result = await _init_tool_stack(app)

        assert result is not None
        mock_tool_executor.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.initialize_mcp_client")
    @patch("backend.app.setup.service_initializer.ZantaraTools")
    @patch("backend.app.setup.service_initializer.ToolExecutor")
    async def test_init_tool_stack_mcp_failure(
        self, mock_tool_executor, mock_zantara_tools, mock_mcp_client
    ):
        """Test tool stack initialization with MCP failure"""
        app = FastAPI()
        app.state = MagicMock()

        mock_mcp_client.side_effect = Exception("MCP init failed")
        mock_executor = MagicMock()
        mock_tool_executor.return_value = mock_executor

        result = await _init_tool_stack(app)

        # Should still succeed even if MCP fails
        assert result is not None


class TestInitRAGComponents:
    """Test _init_rag_components function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.CulturalRAGService")
    @patch("backend.app.setup.service_initializer.QueryRouter")
    async def test_init_rag_components_with_cultural_insights(
        self, mock_query_router, mock_cultural_rag
    ):
        """Test RAG components initialization with cultural insights"""
        app = FastAPI()
        app.state = MagicMock()
        app.state.cultural_insights = MagicMock()

        mock_search = MagicMock()
        mock_router = MagicMock()
        mock_query_router.return_value = mock_router

        result = await _init_rag_components(app, mock_search)

        assert result is not None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.CulturalRAGService")
    @patch("backend.app.setup.service_initializer.QueryRouter")
    async def test_init_rag_components_without_cultural_insights(
        self, mock_query_router, mock_cultural_rag
    ):
        """Test RAG components initialization without cultural insights"""
        app = FastAPI()
        app.state = MagicMock()
        app.state.cultural_insights = None

        mock_search = MagicMock()
        mock_router = MagicMock()
        mock_query_router.return_value = mock_router

        result = await _init_rag_components(app, mock_search)

        assert result is not None


class TestInitSpecializedAgents:
    """Test _init_specialized_agents function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.AutonomousResearchService")
    @patch("backend.app.setup.service_initializer.CrossOracleSynthesisService")
    @patch("backend.app.setup.service_initializer.ClientJourneyOrchestrator")
    async def test_init_specialized_agents_success(
        self, mock_client_journey, mock_cross_oracle, mock_autonomous_research
    ):
        """Test successful specialized agents initialization"""
        app = FastAPI()
        app.state = MagicMock()

        mock_search = MagicMock()
        mock_ai = MagicMock()
        mock_router = MagicMock()

        mock_autonomous_research.return_value = MagicMock()
        mock_cross_oracle.return_value = MagicMock()
        mock_client_journey.return_value = MagicMock()

        result = await _init_specialized_agents(app, mock_search, mock_ai, mock_router)

        assert len(result) == 3
        assert all(r is not None for r in result)

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.AutonomousResearchService")
    @patch("backend.app.setup.service_initializer.CrossOracleSynthesisService")
    @patch("backend.app.setup.service_initializer.ClientJourneyOrchestrator")
    async def test_init_specialized_agents_partial_failure(
        self, mock_client_journey, mock_cross_oracle, mock_autonomous_research
    ):
        """Test specialized agents initialization with partial failures"""
        app = FastAPI()
        app.state = MagicMock()

        mock_search = MagicMock()
        mock_ai = MagicMock()
        mock_router = MagicMock()

        mock_autonomous_research.side_effect = Exception("Init failed")
        mock_cross_oracle.return_value = MagicMock()
        mock_client_journey.return_value = MagicMock()

        result = await _init_specialized_agents(app, mock_search, mock_ai, mock_router)

        # Should return None for failed service
        assert result[0] is None
        assert result[1] is not None
        assert result[2] is not None


class TestInitializeDatabaseServices:
    """Test initialize_database_services function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.settings")
    @patch("backend.app.setup.service_initializer.asyncpg")
    async def test_initialize_database_services_no_url(self, mock_asyncpg, mock_settings):
        """Test database initialization without DATABASE_URL"""
        app = FastAPI()
        app.state = MagicMock()

        mock_settings.database_url = None

        result = await initialize_database_services(app)

        assert result is None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.asyncio.create_task")
    @patch("backend.services.analytics.daily_checkin_notifier.init_daily_notifier")
    @patch("backend.services.analytics.team_timesheet_service.init_timesheet_service")
    @patch("backend.app.setup.service_initializer.settings")
    @patch("backend.app.setup.service_initializer.asyncpg")
    async def test_initialize_database_services_success(
        self, mock_asyncpg, mock_settings, mock_timesheet, mock_daily_notifier, mock_create_task
    ):
        """Test successful database initialization"""
        app = FastAPI()
        app.state = MagicMock()

        mock_settings.database_url = "postgresql://test:test@localhost/test"
        mock_settings.db_pool_min_size = 5
        mock_settings.db_pool_max_size = 20
        mock_settings.db_command_timeout = 60

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

        mock_ts_service = MagicMock()
        mock_ts_service.start_auto_logout_monitor = AsyncMock()
        mock_timesheet.return_value = mock_ts_service

        mock_notifier = MagicMock()
        mock_notifier.start = AsyncMock()
        mock_daily_notifier.return_value = mock_notifier

        result = await initialize_database_services(app)

        assert result is not None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.asyncio.sleep")
    @patch("backend.app.setup.service_initializer.settings")
    @patch("backend.app.setup.service_initializer.asyncpg")
    async def test_initialize_database_services_connection_error(
        self, mock_asyncpg, mock_settings, mock_sleep
    ):
        """Test database initialization with connection error"""
        app = FastAPI()
        app.state = MagicMock()

        mock_settings.database_url = "postgresql://test:test@localhost/test"
        mock_asyncpg.create_pool = AsyncMock(side_effect=ConnectionError("Connection failed"))

        result = await initialize_database_services(app)

        # Should return None after retries
        assert result is None


class TestInitializeCRMAndMemoryServices:
    """Test initialize_crm_and_memory_services function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.get_auto_crm_service")
    @patch("backend.app.setup.service_initializer.MemoryServicePostgres")
    @patch("backend.app.setup.service_initializer.ConversationService")
    @patch("backend.app.setup.service_initializer.create_collective_memory_workflow")
    @patch("backend.app.setup.service_initializer.settings")
    async def test_initialize_crm_and_memory_services_success(
        self,
        mock_settings,
        mock_collective_memory,
        mock_conversation,
        mock_memory,
        mock_auto_crm,
    ):
        """Test successful CRM and memory services initialization"""
        app = FastAPI()
        app.state = MagicMock()

        mock_settings.database_url = "postgresql://test:test@localhost/test"

        mock_crm = MagicMock()
        mock_crm.connect = AsyncMock()
        mock_auto_crm.return_value = mock_crm

        mock_memory_service = MagicMock()
        mock_memory_service.connect = AsyncMock()
        mock_memory.return_value = mock_memory_service

        mock_conversation_service = MagicMock()
        mock_conversation.return_value = mock_conversation_service

        mock_workflow = MagicMock()
        mock_collective_memory.return_value = mock_workflow

        mock_db_pool = MagicMock()
        mock_ai = MagicMock()

        await initialize_crm_and_memory_services(app, mock_ai, mock_db_pool)

        assert app.state.auto_crm_service is not None
        assert app.state.memory_service is not None
        assert app.state.conversation_service is not None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.get_auto_crm_service")
    @patch("backend.app.setup.service_initializer.settings")
    async def test_initialize_crm_and_memory_services_no_db_pool(
        self, mock_settings, mock_auto_crm
    ):
        """Test CRM and memory services initialization without db_pool"""
        app = FastAPI()
        app.state = MagicMock()

        mock_settings.database_url = "postgresql://test:test@localhost/test"

        mock_crm = MagicMock()
        mock_crm.connect = AsyncMock()
        mock_auto_crm.return_value = mock_crm

        mock_ai = MagicMock()

        await initialize_crm_and_memory_services(app, mock_ai, None)

        # Should still initialize with dependency injection
        assert app.state.auto_crm_service is not None


class TestInitializeIntelligentRouter:
    """Test initialize_intelligent_router function"""

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.IntelligentRouter")
    @patch("backend.app.setup.service_initializer.CollaboratorService")
    async def test_initialize_intelligent_router_success(
        self, mock_collaborator, mock_intelligent_router
    ):
        """Test successful intelligent router initialization"""
        app = FastAPI()
        app.state = MagicMock()

        mock_router = MagicMock()
        mock_intelligent_router.return_value = mock_router

        mock_collaborator_service = MagicMock()
        mock_collaborator.return_value = mock_collaborator_service

        mock_ai = MagicMock()
        mock_search = MagicMock()
        mock_tool_executor = MagicMock()
        mock_cultural_rag = MagicMock()

        await initialize_intelligent_router(
            app,
            mock_ai,
            mock_search,
            mock_tool_executor,
            mock_cultural_rag,
            None,
            None,
            None,
            None,
            None,
        )

        assert app.state.intelligent_router is not None

    @pytest.mark.asyncio
    @patch("backend.app.setup.service_initializer.IntelligentRouter")
    @patch("backend.app.setup.service_initializer.CollaboratorService")
    async def test_initialize_intelligent_router_collaborator_failure(
        self, mock_collaborator, mock_intelligent_router
    ):
        """Test intelligent router initialization with collaborator failure"""
        app = FastAPI()
        app.state = MagicMock()

        mock_router = MagicMock()
        mock_intelligent_router.return_value = mock_router

        mock_collaborator.side_effect = Exception("Collaborator init failed")

        mock_ai = MagicMock()
        mock_search = MagicMock()
        mock_tool_executor = MagicMock()
        mock_cultural_rag = MagicMock()

        await initialize_intelligent_router(
            app,
            mock_ai,
            mock_search,
            mock_tool_executor,
            mock_cultural_rag,
            None,
            None,
            None,
            None,
            None,
        )

        # Should still initialize router even if collaborator fails
        assert app.state.intelligent_router is not None
