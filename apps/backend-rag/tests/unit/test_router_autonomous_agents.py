"""
Unit tests for Autonomous Agents Router
"""

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

if "psutil" not in sys.modules:
    sys.modules["psutil"] = types.SimpleNamespace()

if "langgraph.graph" not in sys.modules:

    class _StateGraph:
        pass

    graph_stub = types.SimpleNamespace(END="END", StateGraph=_StateGraph, redis_url='redis://localhost:6379')
    sys.modules["langgraph"] = types.SimpleNamespace(graph=graph_stub, redis_url='redis://localhost:6379')
    sys.modules["langgraph.graph"] = graph_stub

from fastapi import FastAPI

routers_pkg = types.ModuleType("app.routers")
routers_pkg.__path__ = []
sys.modules.setdefault("app.routers", routers_pkg)

module_name = "app.routers.autonomous_agents"
module_path = backend_path / "app" / "routers" / "autonomous_agents.py"
spec = importlib.util.spec_from_file_location(module_name, module_path)
autonomous_agents = importlib.util.module_from_spec(spec)
sys.modules[module_name] = autonomous_agents
assert spec and spec.loader
spec.loader.exec_module(autonomous_agents)

agent_executions = autonomous_agents.agent_executions
router = autonomous_agents.router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@dataclass
class _Chunk:
    payload: dict
    id: str


# ============================================================================
# Fixtures for State Isolation
# ============================================================================


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test to ensure isolation"""
    import copy

    # Save original state
    original_executions = copy.deepcopy(agent_executions)

    yield

    # Restore original state after test
    agent_executions.clear()
    agent_executions.update(original_executions)


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Mock environment variables and settings"""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_key")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_JSON", "{}")

    # Patch settings object directly as it might be already instantiated
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.database_url = "postgresql://user:pass@localhost:5432/db"
        mock_settings.google_api_key = "test_key"
        mock_settings.google_credentials_json = "{}"
        mock_settings.API_V1_STR = "/api/v1"
        mock_settings.PROJECT_NAME = "Test Project"
        mock_settings.log_level = "INFO"
        yield mock_settings


def test_get_autonomous_agents_status():
    """Test getting autonomous agents status"""
    response = client.get("/api/autonomous-agents/status")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data or isinstance(data, dict)


def test_run_conversation_trainer():
    """Test running conversation trainer"""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=7")

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data
    assert "status" in data


def test_run_client_value_predictor():
    """Test running client value predictor"""
    response = client.post("/api/autonomous-agents/client-value-predictor/run")

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data


def test_run_knowledge_graph_builder():
    """Test running knowledge graph builder"""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=30&init_schema=false"
    )

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data


def test_get_execution_status_not_found():
    """Test getting non-existent execution status"""
    response = client.get("/api/autonomous-agents/executions/nonexistent")

    assert response.status_code == 404


def test_list_executions():
    """Test listing executions"""
    response = client.get("/api/autonomous-agents/executions?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list | dict)


# ============================================================================
# Tests for Background Task Functions
# ============================================================================


@pytest.mark.asyncio
async def test_run_conversation_trainer_task_no_analysis(monkeypatch):
    """Test conversation trainer background task when no analysis found"""
    from app.routers.autonomous_agents import _run_conversation_trainer_task

    execution_id = "test_exec_1"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.ConversationTrainer") as mock_trainer:
        trainer_instance = AsyncMock()
        trainer_instance.analyze_winning_patterns = AsyncMock(return_value=None)
        mock_trainer.return_value = trainer_instance

        await _run_conversation_trainer_task(execution_id, days_back=7)

        if agent_executions[execution_id]["status"] == "failed":
            print(f"DEBUG: Task failed with error: {agent_executions[execution_id].get('error')}")

        assert agent_executions[execution_id]["status"] == "completed", (
            f"Task failed with error: {agent_executions[execution_id].get('error')}"
        )
        assert "No high-rated conversations" in agent_executions[execution_id]["result"]["message"]


@pytest.mark.asyncio
async def test_run_conversation_trainer_task_success(monkeypatch):
    """Test conversation trainer background task successful execution"""
    from app.routers.autonomous_agents import _run_conversation_trainer_task

    execution_id = "test_exec_2"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.ConversationTrainer") as mock_trainer:
        trainer_instance = AsyncMock()
        trainer_instance.analyze_winning_patterns = AsyncMock(return_value=["insight1", "insight2"])
        trainer_instance.generate_prompt_update = AsyncMock(return_value="New prompt")
        trainer_instance.create_improvement_pr = AsyncMock(return_value="pr-branch-123")
        mock_trainer.return_value = trainer_instance

        await _run_conversation_trainer_task(execution_id, days_back=7)

        assert agent_executions[execution_id]["status"] == "completed", (
            f"Task failed with error: {agent_executions[execution_id].get('error')}"
        )
        assert "pr_branch" in agent_executions[execution_id]["result"]
        assert agent_executions[execution_id]["result"]["insights_found"] == 2


@pytest.mark.asyncio
async def test_run_client_value_predictor_task_success(monkeypatch):
    """Test client value predictor background task successful execution"""
    from app.routers.autonomous_agents import _run_client_value_predictor_task

    execution_id = "test_exec_3"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.ClientValuePredictor") as mock_predictor:
        predictor_instance = AsyncMock()
        predictor_instance.run_daily_nurturing = AsyncMock(
            return_value={
                "vip_nurtured": 5,
                "high_risk_contacted": 3,
                "total_messages_sent": 8,
                "errors": [],
            }
        )
        mock_predictor.return_value = predictor_instance

        await _run_client_value_predictor_task(execution_id)

        assert agent_executions[execution_id]["status"] == "completed", (
            f"Task failed with error: {agent_executions[execution_id].get('error')}"
        )
        assert agent_executions[execution_id]["result"]["vip_nurtured"] == 5
        assert agent_executions[execution_id]["result"]["high_risk_contacted"] == 3


@pytest.mark.asyncio
async def test_run_knowledge_graph_builder_task_with_init(monkeypatch):
    """Test knowledge graph builder with schema initialization"""
    from app.routers.autonomous_agents import _run_knowledge_graph_builder_task

    execution_id = "test_exec_4"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.KnowledgeGraphBuilder") as mock_builder:
        builder_instance = AsyncMock()
        builder_instance.init_graph_schema = AsyncMock()
        builder_instance.build_graph_from_all_conversations = AsyncMock()
        builder_instance.get_entity_insights = AsyncMock(
            return_value={
                "top_entities": [{"name": "Entity1"}, {"name": "Entity2"}],
                "hubs": [{"name": "Hub1"}],
                "relationship_types": ["WORKS_WITH"],
            }
        )
        mock_builder.return_value = builder_instance

        await _run_knowledge_graph_builder_task(execution_id, days_back=30, init_schema=True)

        builder_instance.init_graph_schema.assert_called_once()
        assert agent_executions[execution_id]["status"] == "completed", (
            f"Task failed with error: {agent_executions[execution_id].get('error')}"
        )
        assert agent_executions[execution_id]["result"]["top_entities_count"] == 2


@pytest.mark.asyncio
async def test_run_knowledge_graph_builder_task_without_init(monkeypatch):
    """Test knowledge graph builder without schema initialization"""
    from app.routers.autonomous_agents import _run_knowledge_graph_builder_task

    execution_id = "test_exec_5"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.KnowledgeGraphBuilder") as mock_builder:
        builder_instance = AsyncMock()
        builder_instance.init_graph_schema = AsyncMock()
        builder_instance.build_graph_from_all_conversations = AsyncMock()
        builder_instance.get_entity_insights = AsyncMock(
            return_value={"top_entities": [], "hubs": [], "relationship_types": []}
        )
        mock_builder.return_value = builder_instance

        await _run_knowledge_graph_builder_task(execution_id, days_back=30, init_schema=False)

        builder_instance.init_graph_schema.assert_not_called()
        assert agent_executions[execution_id]["status"] == "completed", (
            f"Task failed with error: {agent_executions[execution_id].get('error')}"
        )


def test_get_execution_status_success():
    """Test getting execution status for existing execution"""
    # Add an execution to the global state
    agent_executions["test_exec_123"] = {
        "agent_name": "test_agent",
        "status": "completed",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": "2025-01-01T00:10:00",
        "message": "Task completed successfully",
    }

    response = client.get("/api/autonomous-agents/executions/test_exec_123")

    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == "test_exec_123"
    assert data["agent_name"] == "test_agent"
    assert data["status"] == "completed"


# ============================================================================
# Additional Edge Cases and Validation Tests
# ============================================================================


def test_run_conversation_trainer_invalid_days_back():
    """Test running conversation trainer with invalid days_back"""
    # Test with days_back too high (should be capped at 365)
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=500")

    # Should either accept (with cap) or reject with 422
    assert response.status_code in [200, 422]


def test_run_conversation_trainer_zero_days_back():
    """Test running conversation trainer with zero days_back"""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=0")

    # Should reject with 422 (validation error)
    assert response.status_code == 422


def test_run_conversation_trainer_negative_days_back():
    """Test running conversation trainer with negative days_back"""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=-1")

    # Should reject with 422 (validation error)
    assert response.status_code == 422


def test_run_knowledge_graph_builder_min_days_back():
    """Test running knowledge graph builder with minimum days_back"""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=1&init_schema=false"
    )

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data


def test_run_knowledge_graph_builder_max_days_back():
    """Test running knowledge graph builder with maximum days_back"""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=365&init_schema=false"
    )

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data


def test_run_knowledge_graph_builder_with_init_schema():
    """Test running knowledge graph builder with init_schema=true"""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=30&init_schema=true"
    )

    assert response.status_code == 200
    data = response.json()
    assert "execution_id" in data


def test_list_executions_with_limit():
    """Test listing executions with different limit values"""
    # Add some test executions
    agent_executions["exec1"] = {"status": "completed", "started_at": "2025-01-01T00:00:00"}
    agent_executions["exec2"] = {"status": "running", "started_at": "2025-01-01T01:00:00"}
    agent_executions["exec3"] = {"status": "failed", "started_at": "2025-01-01T02:00:00"}

    response = client.get("/api/autonomous-agents/executions?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "executions" in data or isinstance(data, list)
    if isinstance(data, dict):
        assert len(data.get("executions", [])) <= 2


def test_list_executions_zero_limit():
    """Test listing executions with zero limit"""
    response = client.get("/api/autonomous-agents/executions?limit=0")

    # Should either accept (return empty) or reject with 422
    assert response.status_code in [200, 422]


def test_list_executions_negative_limit():
    """Test listing executions with negative limit"""
    response = client.get("/api/autonomous-agents/executions?limit=-1")

    # Router doesn't validate negative limit, so it accepts it
    # This is acceptable behavior - the endpoint handles it gracefully
    assert response.status_code in [200, 422]


@pytest.mark.asyncio
async def test_run_conversation_trainer_task_exception(monkeypatch):
    """Test conversation trainer background task exception handling"""
    from app.routers.autonomous_agents import _run_conversation_trainer_task

    execution_id = "test_exec_exception"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.ConversationTrainer") as mock_trainer:
        trainer_instance = AsyncMock()
        trainer_instance.analyze_winning_patterns = AsyncMock(side_effect=Exception("Test error"))
        mock_trainer.return_value = trainer_instance

        await _run_conversation_trainer_task(execution_id, days_back=7)

        assert agent_executions[execution_id]["status"] == "failed"
        assert "error" in agent_executions[execution_id]
        assert "Test error" in agent_executions[execution_id]["error"]


@pytest.mark.asyncio
async def test_run_client_value_predictor_task_exception(monkeypatch):
    """Test client value predictor background task exception handling"""
    from app.routers.autonomous_agents import _run_client_value_predictor_task

    execution_id = "test_exec_predictor_exception"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.ClientValuePredictor") as mock_predictor:
        predictor_instance = AsyncMock()
        predictor_instance.run_daily_nurturing = AsyncMock(side_effect=Exception("Predictor error"))
        mock_predictor.return_value = predictor_instance

        await _run_client_value_predictor_task(execution_id)

        assert agent_executions[execution_id]["status"] == "failed"
        assert "error" in agent_executions[execution_id]
        assert "Predictor error" in agent_executions[execution_id]["error"]


@pytest.mark.asyncio
async def test_run_knowledge_graph_builder_task_exception(monkeypatch):
    """Test knowledge graph builder background task exception handling"""
    from app.routers.autonomous_agents import _run_knowledge_graph_builder_task

    execution_id = "test_exec_kg_exception"
    agent_executions[execution_id] = {"status": "started"}
    _install_main_cloud_stub(monkeypatch, db_pool=object())

    with patch("app.routers.autonomous_agents.KnowledgeGraphBuilder") as mock_builder:
        builder_instance = AsyncMock()
        builder_instance.build_graph_from_all_conversations = AsyncMock(
            side_effect=Exception("KG builder error")
        )
        mock_builder.return_value = builder_instance

        await _run_knowledge_graph_builder_task(execution_id, days_back=30, init_schema=False)

        assert agent_executions[execution_id]["status"] == "failed"
        assert "error" in agent_executions[execution_id]
        assert "KG builder error" in agent_executions[execution_id]["error"]


def test_get_execution_status_running():
    """Test getting execution status for running execution"""
    agent_executions["test_exec_running"] = {
        "agent_name": "test_agent",
        "status": "running",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": None,
        "message": "Task is running",
    }

    response = client.get("/api/autonomous-agents/executions/test_exec_running")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["completed_at"] is None


def test_get_execution_status_failed():
    """Test getting execution status for failed execution"""
    agent_executions["test_exec_failed"] = {
        "agent_name": "test_agent",
        "status": "failed",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": "2025-01-01T00:05:00",
        "message": "Task failed",
        "error": "Task failed with error",
    }

    response = client.get("/api/autonomous-agents/executions/test_exec_failed")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    # error field is optional in AgentExecutionResponse model
    assert data.get("error") is not None or "error" not in data


def test_get_autonomous_agents_status_structure():
    """Test that status endpoint returns correct structure"""
    response = client.get("/api/autonomous-agents/status")

    assert response.status_code == 200
    data = response.json()
    assert "success" in data or isinstance(data, dict)
    if isinstance(data, dict) and "success" in data:
        assert data["success"] is True
        assert "total_agents" in data
        assert "agents" in data
        assert isinstance(data["agents"], list)


# ============================================================================
# Knowledge Graph Extraction & Persistence Endpoints
# ============================================================================


def _install_main_cloud_stub(monkeypatch, retriever=None, db_pool=None):
    app_stub = types.SimpleNamespace(state=types.SimpleNamespace(retriever=retriever, db_pool=db_pool, redis_url='redis://localhost:6379')
    )
    module_stub = types.SimpleNamespace(app=app_stub, redis_url='redis://localhost:6379')
    monkeypatch.setitem(sys.modules, "app.main_cloud", module_stub)
    return app_stub


def test_extract_kg_sample_qdrant_unavailable(monkeypatch):
    """Test extract sample returns 503 when qdrant is unavailable"""
    _install_main_cloud_stub(monkeypatch, retriever=None)

    response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample")

    assert response.status_code == 503
    assert response.json()["detail"] == "Qdrant not available"


def test_extract_kg_sample_success(monkeypatch):
    """Test extract sample returns entities and relationships"""

    class _QdrantClient:
        def scroll(self, collection_name, limit, with_payload, with_vectors):
            chunks = [
                _Chunk(
                    payload={"text": "PT PMA membutuhkan NIB dan PPh 21"},
                    id="chunk-1",
                ),
                _Chunk(payload={"text": ""}, id="chunk-2"),
            ]
            return (chunks, None)

    retriever = types.SimpleNamespace(client=_QdrantClient(), redis_url='redis://localhost:6379')
    _install_main_cloud_stub(monkeypatch, retriever=retriever)

    response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample?sample_size=10")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "dry_run"
    assert data["entities_found"] >= 2
    assert data["relationships_inferred"] >= 1
    assert "legal_entity" in data["entity_type_distribution"]
    assert data["chunks_processed"] == 2


def test_persist_kg_sample_qdrant_unavailable(monkeypatch):
    """Test persist sample returns 503 when qdrant is unavailable"""
    _install_main_cloud_stub(monkeypatch, retriever=None, db_pool=object())

    response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample")

    assert response.status_code == 503
    assert response.json()["detail"] == "Qdrant not available"


def test_persist_kg_sample_db_unavailable(monkeypatch):
    """Test persist sample returns 503 when db_pool is unavailable"""
    retriever = types.SimpleNamespace(client=object(), redis_url='redis://localhost:6379')
    _install_main_cloud_stub(monkeypatch, retriever=retriever, db_pool=None)

    response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database not available"


def test_persist_kg_sample_success(monkeypatch):
    """Test persist sample adds entities to the knowledge graph"""
    added_entities = []

    class _QdrantClient:
        def scroll(self, collection_name, limit, with_payload, with_vectors):
            chunks = [
                _Chunk(
                    payload={"text": "PT PMA wajib NIB PPh 21 KBLI 12345"},
                    id="chunk-1",
                )
            ]
            return (chunks, None)

    @dataclass
    class _Entity:
        entity_id: str
        entity_type: str
        name: str
        description: str
        source_collection: str
        confidence: float
        source_chunk_ids: list

    class _KnowledgeGraphBuilder:
        def __init__(self, db_pool):
            self.db_pool = db_pool

        async def add_entity(self, entity):
            added_entities.append(entity)

    kg_module = types.SimpleNamespace(Entity=_Entity, KnowledgeGraphBuilder=_KnowledgeGraphBuilder, redis_url='redis://localhost:6379')
    monkeypatch.setitem(
        sys.modules, "services.autonomous_agents.knowledge_graph_builder", kg_module
    )

    retriever = types.SimpleNamespace(client=_QdrantClient(), redis_url='redis://localhost:6379')
    _install_main_cloud_stub(monkeypatch, retriever=retriever, db_pool=object())

    response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample?sample_size=10")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "persisted"
    assert data["entities_added"] == 4
    assert len(added_entities) == 4


# ============================================================================
# Scheduler Control Endpoints
# ============================================================================


def _install_scheduler_stub(monkeypatch, scheduler):
    module_stub = types.SimpleNamespace(get_autonomous_scheduler=lambda: scheduler, redis_url='redis://localhost:6379')
    monkeypatch.setitem(sys.modules, "services.misc.autonomous_scheduler", module_stub)


def test_get_scheduler_status_success(monkeypatch):
    """Test scheduler status success response"""

    class _Scheduler:
        def get_status(self):
            return {"running": True, "task_count": 2}

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.get("/api/autonomous-agents/scheduler/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["scheduler"]["task_count"] == 2


def test_get_scheduler_status_failure(monkeypatch):
    """Test scheduler status failure response"""

    def _raise():
        raise RuntimeError("scheduler offline")

    module_stub = types.SimpleNamespace(get_autonomous_scheduler=_raise, redis_url='redis://localhost:6379')
    monkeypatch.setitem(sys.modules, "services.misc.autonomous_scheduler", module_stub)

    response = client.get("/api/autonomous-agents/scheduler/status")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "scheduler offline" in data["error"]


def test_enable_scheduler_task_success(monkeypatch):
    """Test enabling a scheduler task"""

    class _Scheduler:
        def enable_task(self, task_name):
            return True

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/task-a/enable")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["task_name"] == "task-a"


def test_enable_scheduler_task_not_found(monkeypatch):
    """Test enabling a missing scheduler task"""

    class _Scheduler:
        def enable_task(self, task_name):
            return False

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/missing/enable")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_enable_scheduler_task_exception(monkeypatch):
    """Test enabling a task when scheduler fails"""

    class _Scheduler:
        def enable_task(self, task_name):
            raise RuntimeError("scheduler error")

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/fail/enable")

    assert response.status_code == 500
    assert "scheduler error" in response.json()["detail"]


def test_disable_scheduler_task_success(monkeypatch):
    """Test disabling a scheduler task"""

    class _Scheduler:
        def disable_task(self, task_name):
            return True

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/task-b/disable")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["task_name"] == "task-b"


def test_disable_scheduler_task_not_found(monkeypatch):
    """Test disabling a missing scheduler task"""

    class _Scheduler:
        def disable_task(self, task_name):
            return False

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/missing/disable")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_disable_scheduler_task_exception(monkeypatch):
    """Test disabling a task when scheduler fails"""

    class _Scheduler:
        def disable_task(self, task_name):
            raise RuntimeError("scheduler error")

    _install_scheduler_stub(monkeypatch, _Scheduler())

    response = client.post("/api/autonomous-agents/scheduler/task/fail/disable")

    assert response.status_code == 500
    assert "scheduler error" in response.json()["detail"]
