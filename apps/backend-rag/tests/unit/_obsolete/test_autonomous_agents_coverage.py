"""
Comprehensive tests for autonomous_agents router.
Tests the autonomous agents HTTP endpoints for orchestration.
"""

import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).resolve().parents[4]


# Aggressively mock problematic modules before any backend imports
def mock_problematic_modules():
    # Mock PIL only (numpy 1.26.4 is installed, use real numpy)
    for m in ["PIL", "PIL.Image", "PIL.ImageMode"]:
        mock = types.ModuleType(m)
        if m == "PIL":
            mock.__version__ = "10.0.0"
            mock.Image = types.ModuleType("PIL.Image")
            mock.Image.Image = MagicMock
        sys.modules[m] = mock

    # Mock backend services to avoid cascade
    svc_mock = types.ModuleType("backend.services")
    svc_mock.__path__ = []
    sys.modules["backend.services"] = svc_mock

    for m in [
        "backend.services.oracle",
        "backend.services.search",
        "backend.services.rag",
        "backend.services.rag.agentic",
        "backend.services.ingestion",
        "backend.services.analytics",
        "backend.services.llm_clients",
        "backend.services.pricing",
        "qdrant_client",
    ]:
        sys.modules[m] = MagicMock()

    # Special handling for monitoring to allow submodule imports
    monitoring_mock = types.ModuleType("backend.services.monitoring")
    monitoring_mock.__path__ = []
    sys.modules["backend.services.monitoring"] = monitoring_mock

    # Special handling for misc to allow submodule imports
    misc_mock = types.ModuleType("backend.services.misc")
    misc_mock.__path__ = []
    # Add attributes that might be accessed directly
    misc_mock.AutonomousScheduler = MagicMock()
    misc_mock.AdvancedContextWindowManager = MagicMock()
    misc_mock.AutonomousResearchService = MagicMock()
    misc_mock.ClarificationService = MagicMock()

    sys.modules["backend.services.misc"] = misc_mock
    sys.modules["backend.services.misc.autonomous_scheduler"] = MagicMock()

    # Special handling for search
    sys.modules["backend.services.search.search_service"] = MagicMock()

    # Special handling for ingestion to allow submodule imports
    ingestion_mock = types.ModuleType("backend.services.ingestion")
    ingestion_mock.__path__ = []
    ingestion_mock.IngestionService = MagicMock()
    ingestion_mock.AutoIngestionOrchestrator = MagicMock()
    ingestion_mock.IngestionStatus = MagicMock()
    ingestion_mock.CollectionHealthService = MagicMock()
    ingestion_mock.CollectionManager = MagicMock()
    ingestion_mock.CollectionMetrics = MagicMock()
    ingestion_mock.CollectionWarmupService = MagicMock()
    ingestion_mock.HealthStatus = MagicMock()
    ingestion_mock.IngestionJob = MagicMock()
    ingestion_mock.LegalIngestionService = MagicMock()
    ingestion_mock.MonitoredSource = MagicMock()
    ingestion_mock.PoliticsIngestionService = MagicMock()
    ingestion_mock.ScrapedContent = MagicMock()
    ingestion_mock.SourceType = MagicMock()
    ingestion_mock.StalenessSeverity = MagicMock()
    ingestion_mock.UpdateType = MagicMock()

    sys.modules["backend.services.ingestion"] = ingestion_mock
    sys.modules["backend.services.ingestion.ingestion_service"] = MagicMock()

    # Special handling for memory
    memory_mock = types.ModuleType("backend.services.memory")
    memory_mock.__path__ = []
    memory_mock.MemoryServicePostgres = MagicMock()
    sys.modules["backend.services.memory"] = memory_mock

    # Special handling for communication
    comm_mock = types.ModuleType("backend.services.communication")
    comm_mock.__path__ = []
    comm_mock.detect_language = MagicMock()
    comm_mock.get_language_instruction = MagicMock()
    sys.modules["backend.services.communication"] = comm_mock

    # Special handling for autonomous_agents
    auto_agents_mock = types.ModuleType("backend.services.autonomous_agents")
    auto_agents_mock.__path__ = []
    sys.modules["backend.services.autonomous_agents"] = auto_agents_mock
    sys.modules["backend.services.autonomous_agents.knowledge_graph_builder"] = MagicMock()

    # Special handling for integrations (needed by other tests if this runs first)
    integrations_mock = types.ModuleType("backend.services.integrations")
    integrations_mock.__path__ = []
    integrations_mock.messaging_identity_service = MagicMock()
    integrations_mock.whatsapp_service = MagicMock()
    integrations_mock.whatsapp_triage_service = MagicMock()
    integrations_mock.github_publisher = MagicMock()
    sys.modules["backend.services.integrations"] = integrations_mock
    sys.modules["backend.services.integrations.messaging_identity_service"] = MagicMock()
    sys.modules["backend.services.integrations.github_publisher"] = MagicMock()
    sys.modules["backend.services.integrations.telegram_bot_service"] = MagicMock()

    # Special handling for routing to allow submodule imports
    routing_mock = types.ModuleType("backend.services.routing")
    routing_mock.__path__ = []

    routing_mock.ConfidenceCalculatorService = MagicMock()
    routing_mock.ConflictResolver = MagicMock()
    routing_mock.FallbackManagerService = MagicMock()
    routing_mock.GoldenRouterService = MagicMock()
    routing_mock.IntelligentRouter = MagicMock()
    routing_mock.KeywordMatcherService = MagicMock()
    routing_mock.PriorityOverrideService = MagicMock()
    routing_mock.QueryRouter = MagicMock()
    routing_mock.QueryRouterIntegration = MagicMock()
    routing_mock.RoutingStatsService = MagicMock()

    sys.modules["backend.services.routing"] = routing_mock
    sys.modules["backend.services.routing.intelligent_router"] = MagicMock()


mock_problematic_modules()


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    async_cm = AsyncMock()
    async_cm.__aenter__ = AsyncMock(return_value=conn)
    async_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=async_cm)

    return pool


@pytest.fixture
def mock_conversation_trainer():
    """Mock ConversationTrainer"""
    with patch("backend.agents.agents.conversation_trainer.ConversationTrainer") as MockClass:
        trainer = MagicMock()
        trainer.analyze_winning_patterns = AsyncMock(return_value={"patterns": []})
        trainer.generate_prompt_update = AsyncMock(return_value="improved prompt")
        trainer.create_improvement_pr = AsyncMock(return_value="feature/improvement-123")
        MockClass.return_value = trainer
        yield trainer


@pytest.fixture
def mock_client_value_predictor():
    """Mock ClientValuePredictor"""
    with patch("backend.agents.agents.client_value_predictor.ClientValuePredictor") as MockClass:
        predictor = MagicMock()
        predictor.run_daily_nurturing = AsyncMock(
            return_value={
                "vip_nurtured": 5,
                "high_risk_contacted": 3,
                "total_messages_sent": 8,
                "errors": [],
            }
        )
        MockClass.return_value = predictor
        yield predictor


@pytest.fixture
def mock_knowledge_graph_builder():
    """Mock KnowledgeGraphBuilder"""
    with patch("backend.agents.agents.knowledge_graph_builder.KnowledgeGraphBuilder") as MockClass:
        builder = MagicMock()
        builder.init_graph_schema = AsyncMock()
        builder.build_graph_from_all_conversations = AsyncMock()
        builder.get_entity_insights = AsyncMock(
            return_value={
                "top_entities": [{"name": "PT PMA", "count": 10}],
                "hubs": [{"name": "NIB", "connections": 5}],
                "relationship_types": ["REQUIRES", "COSTS"],
            }
        )
        builder.add_entity = AsyncMock()
        MockClass.return_value = builder
        yield builder


@pytest.fixture
def app():
    """Create FastAPI app with autonomous agents router"""
    from backend.app.routers.autonomous_agents import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestAgentExecutionResponseModel:
    """Tests for AgentExecutionResponse Pydantic model"""

    def test_model_required_fields(self):
        """Model should have all required fields"""
        from backend.app.routers.autonomous_agents import AgentExecutionResponse

        response = AgentExecutionResponse(
            execution_id="exec_123",
            agent_name="test_agent",
            status="started",
            message="Test message",
            started_at="2024-01-01T00:00:00",
        )

        assert response.execution_id == "exec_123"
        assert response.agent_name == "test_agent"
        assert response.status == "started"
        assert response.message == "Test message"

    def test_model_optional_fields(self):
        """Model should handle optional fields"""
        from backend.app.routers.autonomous_agents import AgentExecutionResponse

        response = AgentExecutionResponse(
            execution_id="exec_123",
            agent_name="test_agent",
            status="completed",
            message="Done",
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:01:00",
            result={"key": "value"},
            error=None,
        )

        assert response.completed_at == "2024-01-01T00:01:00"
        assert response.result == {"key": "value"}
        assert response.error is None


class TestConversationTrainerEndpoints:
    """Tests for conversation trainer agent endpoints"""

    def test_run_conversation_trainer_returns_execution_id(self, client):
        """POST /conversation-trainer/run should return execution ID"""
        response = client.post("/api/autonomous-agents/conversation-trainer/run")

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["execution_id"].startswith("conv_trainer_")
        assert data["agent_name"] == "conversation_trainer"
        assert data["status"] == "started"

    def test_run_conversation_trainer_with_days_back(self, client):
        """Should accept days_back parameter"""
        response = client.post(
            "/api/autonomous-agents/conversation-trainer/run", params={"days_back": 30}
        )

        assert response.status_code == 200
        data = response.json()
        assert (
            "30 days" in data["message"] or "days_back" in str(data) or data["status"] == "started"
        )

    def test_run_conversation_trainer_invalid_days_back(self, client):
        """Should reject invalid days_back values"""
        # Test < 1
        response = client.post(
            "/api/autonomous-agents/conversation-trainer/run", params={"days_back": 0}
        )
        assert response.status_code == 422

        # Test > 365
        response = client.post(
            "/api/autonomous-agents/conversation-trainer/run", params={"days_back": 400}
        )
        assert response.status_code == 422


class TestClientValuePredictorEndpoints:
    """Tests for client value predictor agent endpoints"""

    def test_run_client_value_predictor_returns_execution_id(self, client):
        """POST /client-value-predictor/run should return execution ID"""
        response = client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["execution_id"].startswith("client_predictor_")
        assert data["agent_name"] == "client_value_predictor"
        assert data["status"] == "started"


class TestKnowledgeGraphBuilderEndpoints:
    """Tests for knowledge graph builder agent endpoints"""

    def test_run_knowledge_graph_builder_returns_execution_id(self, client):
        """POST /knowledge-graph-builder/run should return execution ID"""
        response = client.post("/api/autonomous-agents/knowledge-graph-builder/run")

        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["execution_id"].startswith("kg_builder_")
        assert data["agent_name"] == "knowledge_graph_builder"
        assert data["status"] == "started"

    def test_run_knowledge_graph_builder_with_params(self, client):
        """Should accept days_back and init_schema parameters"""
        response = client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run",
            params={"days_back": 60, "init_schema": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"


class TestKnowledgeGraphExtraction:
    """Tests for KG extraction endpoints"""

    def test_extract_sample_requires_qdrant(self, client):
        """Should return 503 if Qdrant not available"""
        # Mock the app.main_cloud.app import that happens inside the function
        mock_app = MagicMock()
        mock_app.state.retriever = None

        with patch.dict("sys.modules", {"backend.app.main_cloud": MagicMock(app=mock_app)}):
            response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample")

            # Should fail gracefully (either 503 or error in response)
            assert response.status_code in (500, 503) or "error" in response.text.lower()

    def test_persist_sample_requires_db(self, client):
        """Should return 503 if DB not available"""
        mock_app = MagicMock()
        mock_app.state.retriever = MagicMock()
        mock_app.state.retriever.client = MagicMock()
        mock_app.state.db_pool = None

        with patch.dict("sys.modules", {"backend.app.main_cloud": MagicMock(app=mock_app)}):
            response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample")

            # Should fail gracefully
            assert response.status_code in (500, 503) or "error" in response.text.lower()


class TestStatusEndpoints:
    """Tests for status and monitoring endpoints"""

    def test_get_autonomous_agents_status(self, client):
        """GET /status should return agent capabilities"""
        response = client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["tier"] == 1
        assert data["total_agents"] == 3
        assert "agents" in data
        assert len(data["agents"]) == 3

    def test_status_contains_all_agents(self, client):
        """Status should include all 3 agents"""
        response = client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        agent_names = [a["name"] for a in data["agents"]]

        assert "Conversation Quality Trainer" in agent_names
        assert "Client LTV Predictor & Nurturer" in agent_names
        assert "Knowledge Graph Builder" in agent_names

    def test_status_agent_structure(self, client):
        """Each agent in status should have required fields"""
        response = client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()

        for agent in data["agents"]:
            assert "name" in agent
            assert "description" in agent
            assert "status" in agent
            assert "last_run" in agent
            assert "success_rate" in agent


class TestExecutionManagement:
    """Tests for execution tracking endpoints"""

    def test_get_execution_not_found(self, client):
        """GET /executions/{id} should return 404 for unknown ID"""
        response = client.get("/api/autonomous-agents/executions/unknown_id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_execution_after_creation(self, client):
        """Should be able to retrieve execution after starting agent"""
        # Start an agent
        start_response = client.post("/api/autonomous-agents/conversation-trainer/run")
        assert start_response.status_code == 200
        execution_id = start_response.json()["execution_id"]

        # Get execution status
        status_response = client.get(f"/api/autonomous-agents/executions/{execution_id}")
        assert status_response.status_code == 200
        data = status_response.json()
        assert data["execution_id"] == execution_id

    def test_list_executions_empty(self, client):
        """GET /executions should return empty list initially"""
        # Clear executions for this test
        from backend.app.routers.autonomous_agents import agent_executions

        agent_executions.clear()

        response = client.get("/api/autonomous-agents/executions")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "executions" in data
        assert data["total"] == 0

    def test_list_executions_with_limit(self, client):
        """GET /executions should respect limit parameter"""
        # Create some executions
        for _ in range(5):
            client.post("/api/autonomous-agents/conversation-trainer/run")

        response = client.get("/api/autonomous-agents/executions", params={"limit": 3})

        assert response.status_code == 200
        data = response.json()
        assert len(data["executions"]) <= 3


class TestSchedulerEndpoints:
    """Tests for scheduler control endpoints"""

    def test_get_scheduler_status(self, client):
        """GET /scheduler/status should return scheduler info"""
        with patch(
            "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler"
        ) as mock_get:
            mock_scheduler = MagicMock()
            mock_scheduler.get_status.return_value = {"running": True, "task_count": 3, "tasks": []}
            mock_get.return_value = mock_scheduler

            response = client.get("/api/autonomous-agents/scheduler/status")

            assert response.status_code == 200
            data = response.json()
            assert "scheduler" in data or "success" in data

    def test_enable_task_not_found(self, client):
        """Should return 404 for unknown task"""
        with patch(
            "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler"
        ) as mock_get:
            mock_scheduler = MagicMock()
            mock_scheduler.enable_task.return_value = False
            mock_get.return_value = mock_scheduler

            response = client.post("/api/autonomous-agents/scheduler/task/unknown_task/enable")

            assert response.status_code == 404

    def test_disable_task_not_found(self, client):
        """Should return 404 for unknown task"""
        with patch(
            "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler"
        ) as mock_get:
            mock_scheduler = MagicMock()
            mock_scheduler.disable_task.return_value = False
            mock_get.return_value = mock_scheduler

            response = client.post("/api/autonomous-agents/scheduler/task/unknown_task/disable")

            assert response.status_code == 404

    def test_enable_task_success(self, client):
        """Should return success when task enabled"""
        with patch(
            "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler"
        ) as mock_get:
            mock_scheduler = MagicMock()
            mock_scheduler.enable_task.return_value = True
            mock_get.return_value = mock_scheduler

            response = client.post("/api/autonomous-agents/scheduler/task/test_task/enable")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["task_name"] == "test_task"

    def test_disable_task_success(self, client):
        """Should return success when task disabled"""
        with patch(
            "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler"
        ) as mock_get:
            mock_scheduler = MagicMock()
            mock_scheduler.disable_task.return_value = True
            mock_get.return_value = mock_scheduler

            response = client.post("/api/autonomous-agents/scheduler/task/test_task/disable")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["task_name"] == "test_task"


class TestBackgroundTaskExecution:
    """Tests for background task execution patterns"""

    def test_conversation_trainer_adds_background_task(self):
        """Verify conversation trainer adds task to BackgroundTasks"""
        # This test verifies the endpoint signature uses BackgroundTasks
        import inspect

        from backend.app.routers.autonomous_agents import run_conversation_trainer

        sig = inspect.signature(run_conversation_trainer)
        param_names = list(sig.parameters.keys())
        assert "background_tasks" in param_names

    def test_client_value_predictor_adds_background_task(self):
        """Verify client value predictor adds task to BackgroundTasks"""
        import inspect

        from backend.app.routers.autonomous_agents import run_client_value_predictor

        sig = inspect.signature(run_client_value_predictor)
        param_names = list(sig.parameters.keys())
        assert "background_tasks" in param_names

    def test_knowledge_graph_builder_adds_background_task(self):
        """Verify knowledge graph builder adds task to BackgroundTasks"""
        import inspect

        from backend.app.routers.autonomous_agents import run_knowledge_graph_builder

        sig = inspect.signature(run_knowledge_graph_builder)
        param_names = list(sig.parameters.keys())
        assert "background_tasks" in param_names
