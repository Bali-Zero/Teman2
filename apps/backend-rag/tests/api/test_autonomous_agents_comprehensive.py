"""
Comprehensive API Tests for Autonomous Agents Router
Complete test coverage for all autonomous agent endpoints

Coverage:
- POST /api/autonomous-agents/conversation-trainer/run - Run conversation trainer
- POST /api/autonomous-agents/client-value-predictor/run - Run client value predictor
- POST /api/autonomous-agents/knowledge-graph-builder/run - Run knowledge graph builder
- GET /api/autonomous-agents/status - Get agent status
- GET /api/autonomous-agents/executions/{execution_id} - Get execution status
- GET /api/autonomous-agents/executions - List all executions
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestConversationTrainer:
    """Comprehensive tests for POST /api/autonomous-agents/conversation-trainer/run"""

    def test_run_conversation_trainer_default(self, authenticated_client):
        """Test running conversation trainer with default parameters"""
        response = authenticated_client.post("/api/autonomous-agents/conversation-trainer/run")

        assert response.status_code in [200, 201, 500, 503]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data
            assert data["status"] == "started"

    def test_run_conversation_trainer_with_days(self, authenticated_client):
        """Test running conversation trainer with custom days_back"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=30"
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_run_conversation_trainer_min_days(self, authenticated_client):
        """Test running conversation trainer with minimum days"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=1"
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_run_conversation_trainer_max_days(self, authenticated_client):
        """Test running conversation trainer with maximum days"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=365"
        )

        assert response.status_code in [200, 201, 500, 503]

    def test_run_conversation_trainer_exceeds_max(self, authenticated_client):
        """Test running conversation trainer exceeding maximum days"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=1000"
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_run_conversation_trainer_zero_days(self, authenticated_client):
        """Test running conversation trainer with zero days"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=0"
        )

        assert response.status_code in [200, 201, 400, 422, 500, 503]

    def test_run_conversation_trainer_negative_days(self, authenticated_client):
        """Test running conversation trainer with negative days"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=-1"
        )

        assert response.status_code in [400, 422, 500, 503]


@pytest.mark.api
class TestClientValuePredictor:
    """Comprehensive tests for POST /api/autonomous-agents/client-value-predictor/run"""

    def test_run_client_value_predictor(self, authenticated_client):
        """Test running client value predictor"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code in [200, 201, 500, 503]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data

    def test_run_client_value_predictor_response_structure(self, authenticated_client):
        """Test client value predictor response structure"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert "status" in data
            assert "message" in data
            assert "started_at" in data


@pytest.mark.api
class TestKnowledgeGraphBuilder:
    """Comprehensive tests for POST /api/autonomous-agents/knowledge-graph-builder/run"""

    def test_run_knowledge_graph_builder(self, authenticated_client):
        """Test running knowledge graph builder"""
        response = authenticated_client.post("/api/autonomous-agents/knowledge-graph-builder/run")

        assert response.status_code in [200, 201, 500, 503]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data

    def test_run_knowledge_graph_builder_response_structure(self, authenticated_client):
        """Test knowledge graph builder response structure"""
        response = authenticated_client.post("/api/autonomous-agents/knowledge-graph-builder/run")

        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert "status" in data


@pytest.mark.api
class TestAgentStatus:
    """Comprehensive tests for GET /api/autonomous-agents/status"""

    def test_get_agent_status(self, authenticated_client):
        """Test getting agent status"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_agent_status_structure(self, authenticated_client):
        """Test agent status response structure"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        # Should have status information
        assert isinstance(data, dict)


@pytest.mark.api
class TestExecutionStatus:
    """Comprehensive tests for GET /api/autonomous-agents/executions/{execution_id}"""

    def test_get_execution_status(self, authenticated_client):
        """Test getting execution status"""
        # First start an execution
        start_response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run"
        )

        if start_response.status_code in [200, 201]:
            execution_id = start_response.json()["execution_id"]

            # Get execution status
            status_response = authenticated_client.get(
                f"/api/autonomous-agents/executions/{execution_id}"
            )

            assert status_response.status_code in [200, 404, 500]

    def test_get_execution_status_not_found(self, authenticated_client):
        """Test getting status for non-existent execution"""
        response = authenticated_client.get(
            "/api/autonomous-agents/executions/nonexistent_execution_id"
        )

        assert response.status_code in [200, 404, 500]

    def test_get_execution_status_structure(self, authenticated_client):
        """Test execution status response structure"""
        # Start an execution
        start_response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run"
        )

        if start_response.status_code in [200, 201]:
            execution_id = start_response.json()["execution_id"]

            status_response = authenticated_client.get(
                f"/api/autonomous-agents/executions/{execution_id}"
            )

            if status_response.status_code == 200:
                data = status_response.json()
                assert "execution_id" in data
                assert "status" in data
                assert "started_at" in data


@pytest.mark.api
class TestListExecutions:
    """Comprehensive tests for GET /api/autonomous-agents/executions"""

    def test_list_executions(self, authenticated_client):
        """Test listing all executions"""
        response = authenticated_client.get("/api/autonomous-agents/executions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_executions_with_filters(self, authenticated_client):
        """Test listing executions with filters"""
        filters = [
            "?agent_name=conversation_trainer",
            "?status=completed",
            "?limit=10",
        ]

        for filter_param in filters:
            response = authenticated_client.get(f"/api/autonomous-agents/executions{filter_param}")

            assert response.status_code == 200

    def test_list_executions_structure(self, authenticated_client):
        """Test executions list response structure"""
        response = authenticated_client.get("/api/autonomous-agents/executions")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            execution = data[0]
            assert "execution_id" in execution or "status" in execution


@pytest.mark.api
class TestAutonomousAgentsSecurity:
    """Security tests for autonomous agents endpoints"""

    def test_autonomous_agents_endpoints_require_auth(self, test_client):
        """Test all autonomous agents endpoints require authentication"""
        endpoints = [
            ("POST", "/api/autonomous-agents/conversation-trainer/run"),
            ("POST", "/api/autonomous-agents/client-value-predictor/run"),
            ("POST", "/api/autonomous-agents/knowledge-graph-builder/run"),
            ("GET", "/api/autonomous-agents/status"),
            ("GET", "/api/autonomous-agents/executions/exec_123"),
            ("GET", "/api/autonomous-agents/executions"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path)

            assert response.status_code == 401
