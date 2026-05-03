"""
Unit tests for autonomous_agents router.
Coverage target: POST /run, GET /status, GET /executions, GET /scheduler/status,
POST /scheduler/task/{name}/enable|disable, GET /knowledge-graph/extract-sample,
POST /knowledge-graph/persist-sample.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.autonomous_agents import agent_executions, router


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture(autouse=True)
def clear_executions():
    """Clear global execution state between tests."""
    agent_executions.clear()
    yield
    agent_executions.clear()


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ============================================================
# POST /api/autonomous-agents/conversation-trainer/run
# ============================================================


def test_run_conversation_trainer_happy_path(client):
    """Should return 200 and 'started' status immediately."""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=7")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["agent_name"] == "conversation_trainer"
    assert "execution_id" in data
    assert data["execution_id"].startswith("conv_trainer_")


def test_run_conversation_trainer_default_days(client):
    """Should use default days_back=7 when not provided."""
    response = client.post("/api/autonomous-agents/conversation-trainer/run")
    assert response.status_code == 200
    data = response.json()
    assert "7" in data["message"] or "started" in data["status"]


def test_run_conversation_trainer_invalid_days(client):
    """Should return 422 for invalid days_back (0 is below minimum 1)."""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=0")
    assert response.status_code == 422


def test_run_conversation_trainer_days_too_large(client):
    """Should return 422 for days_back > 365."""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=366")
    assert response.status_code == 422


def test_run_conversation_trainer_max_days(client):
    """Should accept days_back=365."""
    response = client.post("/api/autonomous-agents/conversation-trainer/run?days_back=365")
    assert response.status_code == 200


# ============================================================
# POST /api/autonomous-agents/client-value-predictor/run
# ============================================================


def test_run_client_value_predictor_happy_path(client):
    """Should return 200 and 'started' status immediately."""
    response = client.post("/api/autonomous-agents/client-value-predictor/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["agent_name"] == "client_value_predictor"
    assert "execution_id" in data
    assert data["execution_id"].startswith("client_predictor_")


def test_run_client_value_predictor_returns_message(client):
    """Should return message indicating background execution."""
    response = client.post("/api/autonomous-agents/client-value-predictor/run")
    data = response.json()
    assert "background" in data["message"].lower() or "started" in data["message"].lower()


# ============================================================
# POST /api/autonomous-agents/knowledge-graph-builder/run
# ============================================================


def test_run_knowledge_graph_builder_happy_path(client):
    """Should return 200 and 'started' status."""
    response = client.post("/api/autonomous-agents/knowledge-graph-builder/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["agent_name"] == "knowledge_graph_builder"
    assert data["execution_id"].startswith("kg_builder_")


def test_run_knowledge_graph_builder_with_params(client):
    """Should accept days_back and init_schema params."""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=60&init_schema=true"
    )
    assert response.status_code == 200


def test_run_knowledge_graph_builder_invalid_days(client):
    """Should reject days_back=0."""
    response = client.post(
        "/api/autonomous-agents/knowledge-graph-builder/run?days_back=0"
    )
    assert response.status_code == 422


# ============================================================
# GET /api/autonomous-agents/status
# ============================================================


def test_get_autonomous_agents_status_empty(client):
    """Should return all 3 agents with idle status when no executions."""
    # get_autonomous_scheduler is imported lazily inside the function,
    # so we patch its module path
    with patch(
        "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler",
        side_effect=Exception("no scheduler"),
    ):
        response = client.get("/api/autonomous-agents/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["total_agents"] == 3
    assert data["tier"] == 1
    assert len(data["agents"]) == 3


def test_get_autonomous_agents_status_with_executions(client):
    """Should reflect execution history in agent stats."""
    # Pre-populate an execution
    agent_executions["conv_trainer_001"] = {
        "agent_name": "conversation_trainer",
        "status": "completed",
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "completed_at": datetime.now(tz=timezone.utc).isoformat(),
        "message": "done",
        "result": {"message": "test"},
    }
    response = client.get("/api/autonomous-agents/status")
    assert response.status_code == 200
    data = response.json()
    # recent_executions reflects populated dict
    assert data["recent_executions"] >= 1


# ============================================================
# GET /api/autonomous-agents/executions
# ============================================================


def test_list_executions_empty(client):
    """Should return empty list when no executions."""
    response = client.get("/api/autonomous-agents/executions")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["executions"] == []
    assert data["total"] == 0


def test_list_executions_with_data(client):
    """Should return executions from in-memory store."""
    agent_executions["exec_001"] = {
        "agent_name": "conversation_trainer",
        "status": "completed",
        "started_at": "2026-01-01T00:00:00",
        "message": "done",
    }
    response = client.get("/api/autonomous-agents/executions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["executions"][0]["execution_id"] == "exec_001"


def test_list_executions_limit(client):
    """Should respect limit parameter."""
    for i in range(5):
        agent_executions[f"exec_{i:03d}"] = {
            "agent_name": "conversation_trainer",
            "status": "completed",
            "started_at": f"2026-01-0{i + 1}T00:00:00",
            "message": "done",
        }
    response = client.get("/api/autonomous-agents/executions?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["executions"]) <= 2


# ============================================================
# GET /api/autonomous-agents/executions/{execution_id}
# ============================================================


def test_get_execution_status_found(client):
    """Should return execution data when execution_id exists."""
    agent_executions["my_exec_001"] = {
        "agent_name": "conversation_trainer",
        "status": "running",
        "started_at": datetime.now(tz=timezone.utc).isoformat(),
        "message": "In progress",
    }
    response = client.get("/api/autonomous-agents/executions/my_exec_001")
    assert response.status_code == 200
    data = response.json()
    assert data["execution_id"] == "my_exec_001"
    assert data["status"] == "running"


def test_get_execution_status_not_found(client):
    """Should return 404 when execution_id doesn't exist."""
    response = client.get("/api/autonomous-agents/executions/nonexistent_999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================
# GET /api/autonomous-agents/scheduler/status
# ============================================================


def test_get_scheduler_status_success(client):
    """Should return scheduler status when scheduler is available."""
    mock_scheduler = MagicMock()
    mock_scheduler.get_status.return_value = {
        "running": True,
        "task_count": 3,
        "tasks": {},
    }
    with patch(
        "backend.services.misc.autonomous_scheduler.get_autonomous_scheduler",
        return_value=mock_scheduler,
    ):
        response = client.get("/api/autonomous-agents/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "scheduler" in data


def test_get_scheduler_status_failure(client):
    """Should return success=False when scheduler raises exception."""
    # Patch the module where it is defined so the lazy import sees it
    import backend.services.misc.autonomous_scheduler as _sched_mod
    original = getattr(_sched_mod, "get_autonomous_scheduler", None)

    with patch.object(_sched_mod, "get_autonomous_scheduler", side_effect=Exception("scheduler unavailable")):
        response = client.get("/api/autonomous-agents/scheduler/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "error" in data


# ============================================================
# POST /api/autonomous-agents/scheduler/task/{task_name}/enable
# ============================================================


def test_enable_scheduler_task_success(client):
    """Should return success when task is found and enabled."""
    import backend.services.misc.autonomous_scheduler as _sched_mod
    mock_scheduler = MagicMock()
    mock_scheduler.enable_task.return_value = True
    with patch.object(_sched_mod, "get_autonomous_scheduler", return_value=mock_scheduler):
        response = client.post("/api/autonomous-agents/scheduler/task/conversation_trainer/enable")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["task_name"] == "conversation_trainer"


def test_enable_scheduler_task_not_found(client):
    """Should return 404 when task is not found."""
    import backend.services.misc.autonomous_scheduler as _sched_mod
    mock_scheduler = MagicMock()
    mock_scheduler.enable_task.return_value = False
    with patch.object(_sched_mod, "get_autonomous_scheduler", return_value=mock_scheduler):
        response = client.post("/api/autonomous-agents/scheduler/task/nonexistent/enable")
    assert response.status_code == 404


def test_enable_scheduler_task_exception(client):
    """Should return 500 when an unexpected error occurs."""
    import backend.services.misc.autonomous_scheduler as _sched_mod
    with patch.object(_sched_mod, "get_autonomous_scheduler", side_effect=RuntimeError("crash")):
        response = client.post("/api/autonomous-agents/scheduler/task/any_task/enable")
    assert response.status_code == 500


# ============================================================
# POST /api/autonomous-agents/scheduler/task/{task_name}/disable
# ============================================================


def test_disable_scheduler_task_success(client):
    """Should return success when task is found and disabled."""
    import backend.services.misc.autonomous_scheduler as _sched_mod
    mock_scheduler = MagicMock()
    mock_scheduler.disable_task.return_value = True
    with patch.object(_sched_mod, "get_autonomous_scheduler", return_value=mock_scheduler):
        response = client.post("/api/autonomous-agents/scheduler/task/knowledge_graph_builder/disable")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_disable_scheduler_task_not_found(client):
    """Should return 404 when task not found."""
    import backend.services.misc.autonomous_scheduler as _sched_mod
    mock_scheduler = MagicMock()
    mock_scheduler.disable_task.return_value = False
    with patch.object(_sched_mod, "get_autonomous_scheduler", return_value=mock_scheduler):
        response = client.post("/api/autonomous-agents/scheduler/task/ghost_task/disable")
    assert response.status_code == 404


# ============================================================
# GET /api/autonomous-agents/knowledge-graph/extract-sample
# ============================================================


def test_extract_kg_sample_qdrant_unavailable(client):
    """Should return 503 when Qdrant retriever not available."""
    import backend.app.main_cloud as _main
    original_state = getattr(_main.app, "state", None)
    # Remove retriever from state
    _main.app.state.retriever = None
    try:
        response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample")
    finally:
        pass
    assert response.status_code == 503


def test_extract_kg_sample_qdrant_client_none(client):
    """Should return 503 when retriever.client is None."""
    import backend.app.main_cloud as _main
    mock_retriever = MagicMock()
    mock_retriever.client = None
    _main.app.state.retriever = mock_retriever
    response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample")
    assert response.status_code == 503


def test_extract_kg_sample_success(client):
    """Should return 200 with dry_run status when Qdrant available."""
    import backend.app.main_cloud as _main

    mock_chunk = MagicMock()
    mock_chunk.id = "chunk_abc"
    mock_chunk.payload = {"text": "PT PMA memerlukan NIB dan KBLI 56101 biaya Rp 10 miliar"}

    mock_qdrant = MagicMock()
    mock_qdrant.scroll.return_value = ([mock_chunk], None)

    mock_retriever = MagicMock()
    mock_retriever.client = mock_qdrant
    _main.app.state.retriever = mock_retriever

    response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample?sample_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "dry_run"
    assert "entities_found" in data
    assert "relationships_inferred" in data


def test_extract_kg_sample_qdrant_error(client):
    """Should return 500 when Qdrant scroll fails."""
    import backend.app.main_cloud as _main

    mock_qdrant = MagicMock()
    mock_qdrant.scroll.side_effect = Exception("Qdrant unavailable")

    mock_retriever = MagicMock()
    mock_retriever.client = mock_qdrant
    _main.app.state.retriever = mock_retriever

    response = client.get("/api/autonomous-agents/knowledge-graph/extract-sample")
    assert response.status_code == 500


# ============================================================
# POST /api/autonomous-agents/knowledge-graph/persist-sample
# ============================================================


def test_persist_kg_sample_qdrant_unavailable(client):
    """Should return 503 when Qdrant not available."""
    import backend.app.main_cloud as _main
    _main.app.state.retriever = None
    response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample")
    assert response.status_code == 503


def test_persist_kg_sample_db_unavailable(client):
    """Should return 503 when db_pool is None."""
    import backend.app.main_cloud as _main
    mock_retriever = MagicMock()
    mock_retriever.client = MagicMock()
    _main.app.state.retriever = mock_retriever
    _main.app.state.db_pool = None
    response = client.post("/api/autonomous-agents/knowledge-graph/persist-sample")
    assert response.status_code == 503
