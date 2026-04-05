"""
Unit tests for Agent Router

Tests cover:
- POST /api/agent/invoke - Invoke RAG workflow
- GET /api/agent/health - Agent health check
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.agent import router

# ============================================
# FIXTURES
# ============================================


@pytest.fixture
def app(mock_current_user):
    """Create FastAPI app with auth override."""
    from backend.app.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    return app


@pytest.fixture
def client(app):
    """TestClient for agent router."""
    return TestClient(app)


@pytest.fixture
def sample_workflow_result():
    """Successful workflow result."""
    return {
        "generation": "Based on the documents, KITAS visa requirements include...",
        "execution_path": ["retrieve", "grade", "generate"],
        "step_count": 3,
        "timestamp": datetime(2026, 4, 1, tzinfo=timezone.utc),
        "errors": None,
    }


# ============================================
# POST /invoke TESTS
# ============================================


class TestInvokeAgent:
    """Tests for POST /api/agent/invoke"""

    @patch("backend.app.routers.agent.invoke_rag_workflow")
    def test_invoke_success(
        self, mock_invoke, client, sample_workflow_result,
    ):
        """Happy path: invoke workflow and get answer."""
        mock_invoke.return_value = sample_workflow_result

        response = client.post(
            "/api/agent/invoke",
            json={
                "question": "What are the requirements for a KITAS visa?",
                "metadata": {"user_id": "user_123"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["question"] == "What are the requirements for a KITAS visa?"
        assert "KITAS" in data["generation"]
        assert data["execution_path"] == ["retrieve", "grade", "generate"]
        assert data["step_count"] == 3

    @patch("backend.app.routers.agent.invoke_rag_workflow")
    def test_invoke_with_errors(self, mock_invoke, client):
        """Workflow completes with errors flagged."""
        mock_invoke.return_value = {
            "generation": "Partial answer available.",
            "execution_path": ["retrieve", "generate"],
            "step_count": 2,
            "timestamp": datetime.now(tz=timezone.utc),
            "errors": ["Grading step failed: timeout"],
        }

        response = client.post(
            "/api/agent/invoke",
            json={"question": "Test question"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["errors"] == ["Grading step failed: timeout"]

    @patch("backend.app.routers.agent.invoke_rag_workflow")
    def test_invoke_workflow_exception(self, mock_invoke, client):
        """Workflow raises exception returns 500."""
        mock_invoke.side_effect = RuntimeError("LLM gateway down")

        response = client.post(
            "/api/agent/invoke",
            json={"question": "Test question"},
        )

        assert response.status_code == 500
        assert "Failed to invoke agent workflow" in response.json()["detail"]

    def test_invoke_empty_question(self, client):
        """Empty question fails validation (min_length=1)."""
        response = client.post(
            "/api/agent/invoke",
            json={"question": ""},
        )

        assert response.status_code == 422

    def test_invoke_question_too_long(self, client):
        """Question exceeding max_length fails validation."""
        response = client.post(
            "/api/agent/invoke",
            json={"question": "x" * 2001},
        )

        assert response.status_code == 422

    @patch("backend.app.routers.agent.invoke_rag_workflow")
    def test_invoke_no_metadata(self, mock_invoke, client, sample_workflow_result):
        """Works without optional metadata."""
        mock_invoke.return_value = sample_workflow_result

        response = client.post(
            "/api/agent/invoke",
            json={"question": "Simple question"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"] is None


# ============================================
# GET /health TESTS
# ============================================


class TestAgentHealth:
    """Tests for GET /api/agent/health"""

    @patch("backend.app.routers.agent.rag_graph", new=MagicMock())
    def test_health_healthy(self, client):
        """Graph loaded returns healthy."""
        # Need to patch the import inside the function
        with patch.dict(
            "sys.modules",
            {"backend.app.agents.graph": MagicMock(rag_graph=MagicMock())},
        ):
            response = client.get("/api/agent/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["graph_loaded"] is True

    def test_health_graph_not_loaded(self, client):
        """Graph is None returns unhealthy."""
        with patch.dict(
            "sys.modules",
            {"backend.app.agents.graph": MagicMock(rag_graph=None)},
        ):
            response = client.get("/api/agent/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["graph_loaded"] is False

    def test_health_import_error(self, client):
        """Import error returns unhealthy."""
        with patch.dict("sys.modules", {"backend.app.agents.graph": None}):
            # Remove the module so import fails
            import sys

            saved = sys.modules.pop("backend.app.agents.graph", None)
            try:
                # This should trigger the ImportError path in agent_health
                response = client.get("/api/agent/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] in ("unhealthy", "degraded")
            finally:
                if saved is not None:
                    sys.modules["backend.app.agents.graph"] = saved
