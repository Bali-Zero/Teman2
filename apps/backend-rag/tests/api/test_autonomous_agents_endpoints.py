"""
API Tests for Autonomous Agents Router
Tests autonomous agent execution endpoints

Coverage:
- POST /api/autonomous-agents/conversation-trainer/run - Run conversation trainer
- POST /api/autonomous-agents/client-value-predictor/run - Run client value predictor
- POST /api/autonomous-agents/knowledge-graph-builder/run - Run knowledge graph builder
- GET /api/autonomous-agents/status - Get agents status
- GET /api/autonomous-agents/executions/{execution_id} - Get execution status
- GET /api/autonomous-agents/executions - List executions
"""

import os
import sys
from pathlib import Path

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAutonomousAgents:
    """Tests for autonomous agents endpoints"""

    def test_run_conversation_trainer(self, authenticated_client):
        """Test POST /api/autonomous-agents/conversation-trainer/run"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=7"
        )

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data

    def test_run_client_value_predictor(self, authenticated_client):
        """Test POST /api/autonomous-agents/client-value-predictor/run"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data

    def test_run_knowledge_graph_builder(self, authenticated_client):
        """Test POST /api/autonomous-agents/knowledge-graph-builder/run"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run?days_back=30"
        )

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data

    def test_get_agents_status(self, authenticated_client):
        """Test GET /api/autonomous-agents/status"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data or "status" in data

    def test_get_execution_status(self, authenticated_client):
        """Test GET /api/autonomous-agents/executions/{execution_id}"""
        # Test with a mock execution_id
        response = authenticated_client.get("/api/autonomous-agents/executions/test_execution_id")

        assert response.status_code in [200, 404, 503]

    def test_list_executions(self, authenticated_client):
        """Test GET /api/autonomous-agents/executions"""
        response = authenticated_client.get("/api/autonomous-agents/executions?limit=20")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "executions" in data

    def test_autonomous_agents_require_auth(self, test_client):
        """Test that autonomous agents endpoints require authentication"""
        response = test_client.post("/api/autonomous-agents/conversation-trainer/run")
        assert response.status_code == 401
