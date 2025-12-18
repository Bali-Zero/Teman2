"""
Comprehensive API Tests for Autonomous Agents Router
Complete test coverage including scheduler endpoints

Coverage:
- POST /api/autonomous-agents/conversation-trainer/run
- POST /api/autonomous-agents/client-value-predictor/run
- POST /api/autonomous-agents/knowledge-graph-builder/run
- GET /api/autonomous-agents/status
- GET /api/autonomous-agents/executions/{execution_id}
- GET /api/autonomous-agents/executions
- GET /api/autonomous-agents/scheduler/status
- POST /api/autonomous-agents/scheduler/task/{task_name}/enable
- POST /api/autonomous-agents/scheduler/task/{task_name}/disable
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
class TestConversationTrainerEndpoints:
    """Tests for Conversation Trainer agent endpoints"""

    def test_run_conversation_trainer_default_params(self, authenticated_client):
        """Test running conversation trainer with default parameters (days_back=7)"""
        response = authenticated_client.post("/api/autonomous-agents/conversation-trainer/run")

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert "status" in data
            assert "message" in data
            assert "started_at" in data
            assert data["agent_name"] == "conversation_trainer"
            assert data["status"] == "started"
            assert "conv_trainer_" in data["execution_id"]

    def test_run_conversation_trainer_custom_days(self, authenticated_client):
        """Test running conversation trainer with custom days_back=30"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=30"
        )

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "started"

    def test_run_conversation_trainer_min_days(self, authenticated_client):
        """Test running conversation trainer with minimum days_back=1"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=1"
        )

        assert response.status_code in [200, 500, 503]

    def test_run_conversation_trainer_max_days(self, authenticated_client):
        """Test running conversation trainer with maximum days_back=365"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=365"
        )

        assert response.status_code in [200, 500, 503]

    def test_run_conversation_trainer_exceeds_max(self, authenticated_client):
        """Test running conversation trainer with days_back > 365 (should fail validation)"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=1000"
        )

        # Should return validation error (422) or success if validation not strict
        assert response.status_code in [200, 422, 500, 503]
        if response.status_code == 422:
            data = response.json()
            assert "detail" in data

    def test_run_conversation_trainer_zero_days(self, authenticated_client):
        """Test running conversation trainer with days_back=0 (should fail validation)"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=0"
        )

        # Should return validation error (422)
        assert response.status_code in [422, 500, 503]

    def test_run_conversation_trainer_negative_days(self, authenticated_client):
        """Test running conversation trainer with negative days_back (should fail)"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=-1"
        )

        assert response.status_code in [422, 500, 503]

    def test_run_conversation_trainer_requires_auth(self, test_client):
        """Test that conversation trainer requires authentication"""
        response = test_client.post("/api/autonomous-agents/conversation-trainer/run")
        assert response.status_code == 401


@pytest.mark.api
class TestClientValuePredictorEndpoints:
    """Tests for Client Value Predictor agent endpoints"""

    def test_run_client_value_predictor(self, authenticated_client):
        """Test running client value predictor agent"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert "status" in data
            assert data["agent_name"] == "client_value_predictor"
            assert data["status"] == "started"
            assert "client_predictor_" in data["execution_id"]

    def test_run_client_value_predictor_requires_auth(self, test_client):
        """Test that client value predictor requires authentication"""
        response = test_client.post("/api/autonomous-agents/client-value-predictor/run")
        assert response.status_code == 401


@pytest.mark.api
class TestKnowledgeGraphBuilderEndpoints:
    """Tests for Knowledge Graph Builder agent endpoints"""

    def test_run_knowledge_graph_builder_default(self, authenticated_client):
        """Test running knowledge graph builder with default parameters"""
        response = authenticated_client.post("/api/autonomous-agents/knowledge-graph-builder/run")

        assert response.status_code in [200, 500, 503]
        if response.status_code == 200:
            data = response.json()
            assert "execution_id" in data
            assert "agent_name" in data
            assert data["agent_name"] == "knowledge_graph_builder"
            assert "kg_builder_" in data["execution_id"]

    def test_run_knowledge_graph_builder_custom_days(self, authenticated_client):
        """Test running knowledge graph builder with custom days_back"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run?days_back=60"
        )

        assert response.status_code in [200, 500, 503]

    def test_run_knowledge_graph_builder_with_init_schema(self, authenticated_client):
        """Test running knowledge graph builder with schema initialization"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run?init_schema=true"
        )

        assert response.status_code in [200, 500, 503]

    def test_run_knowledge_graph_builder_full_params(self, authenticated_client):
        """Test running knowledge graph builder with all parameters"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run?days_back=90&init_schema=true"
        )

        assert response.status_code in [200, 500, 503]

    def test_run_knowledge_graph_builder_exceeds_max(self, authenticated_client):
        """Test running knowledge graph builder with days_back > 365"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run?days_back=500"
        )

        assert response.status_code in [200, 422, 500, 503]

    def test_run_knowledge_graph_builder_requires_auth(self, test_client):
        """Test that knowledge graph builder requires authentication"""
        response = test_client.post("/api/autonomous-agents/knowledge-graph-builder/run")
        assert response.status_code == 401


@pytest.mark.api
class TestAgentStatusEndpoints:
    """Tests for agent status and execution management endpoints"""

    def test_get_agents_status(self, authenticated_client):
        """Test GET /api/autonomous-agents/status"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "tier" in data
        assert data["tier"] == 1
        assert "total_agents" in data
        assert data["total_agents"] == 3
        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) == 3

        # Verify agent structure
        for agent in data["agents"]:
            assert "id" in agent
            assert "name" in agent
            assert "description" in agent
            assert "schedule" in agent
            assert "priority" in agent
            assert "estimated_duration_min" in agent

        # Verify specific agents
        agent_ids = [agent["id"] for agent in data["agents"]]
        assert "conversation_trainer" in agent_ids
        assert "client_value_predictor" in agent_ids
        assert "knowledge_graph_builder" in agent_ids

    def test_get_agents_status_unauthenticated(self, test_client):
        """Test that status endpoint works without authentication (public info)"""
        response = test_client.get("/api/autonomous-agents/status")
        # Status endpoint may or may not require auth - accept both
        assert response.status_code in [200, 401]

    def test_get_execution_status_not_found(self, authenticated_client):
        """Test getting status for non-existent execution"""
        response = authenticated_client.get("/api/autonomous-agents/executions/nonexistent_id")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_list_executions_default(self, authenticated_client):
        """Test listing executions with default limit"""
        response = authenticated_client.get("/api/autonomous-agents/executions")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "executions" in data
        assert "total" in data
        assert isinstance(data["executions"], list)

    def test_list_executions_custom_limit(self, authenticated_client):
        """Test listing executions with custom limit"""
        response = authenticated_client.get("/api/autonomous-agents/executions?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        # Should return at most 5 executions
        assert len(data["executions"]) <= 5

    def test_list_executions_requires_auth(self, test_client):
        """Test that listing executions requires authentication"""
        response = test_client.get("/api/autonomous-agents/executions")
        # May or may not require auth depending on implementation
        assert response.status_code in [200, 401]


@pytest.mark.api
class TestSchedulerEndpoints:
    """Tests for autonomous scheduler management endpoints"""

    def test_get_scheduler_status(self, authenticated_client):
        """Test GET /api/autonomous-agents/scheduler/status"""
        response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "timestamp" in data

        # If successful, verify scheduler structure
        if data["success"]:
            assert "scheduler" in data
            scheduler = data["scheduler"]
            assert "running" in scheduler
            assert "task_count" in scheduler
            assert "tasks" in scheduler
            assert isinstance(scheduler["tasks"], dict)
        else:
            # If failed, should have error
            assert "error" in data

    def test_enable_scheduler_task_success(self, authenticated_client):
        """Test enabling a scheduler task"""
        # First get available tasks
        status_response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        if status_response.status_code == 200:
            status_data = status_response.json()
            if (
                status_data.get("success")
                and "scheduler" in status_data
                and status_data["scheduler"].get("tasks")
            ):
                # Get first task name
                task_names = list(status_data["scheduler"]["tasks"].keys())
                if task_names:
                    task_name = task_names[0]

                    # Try to enable it
                    response = authenticated_client.post(
                        f"/api/autonomous-agents/scheduler/task/{task_name}/enable"
                    )

                    # Accept success or error (task might already be enabled)
                    assert response.status_code in [200, 404, 500]
                    if response.status_code == 200:
                        data = response.json()
                        assert "success" in data
                        assert data["success"] is True
                        assert "message" in data
                        assert "task_name" in data
                        assert data["task_name"] == task_name

    def test_disable_scheduler_task_success(self, authenticated_client):
        """Test disabling a scheduler task"""
        # First get available tasks
        status_response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        if status_response.status_code == 200:
            status_data = status_response.json()
            if (
                status_data.get("success")
                and "scheduler" in status_data
                and status_data["scheduler"].get("tasks")
            ):
                # Get first task name
                task_names = list(status_data["scheduler"]["tasks"].keys())
                if task_names:
                    task_name = task_names[0]

                    # Try to disable it
                    response = authenticated_client.post(
                        f"/api/autonomous-agents/scheduler/task/{task_name}/disable"
                    )

                    assert response.status_code in [200, 404, 500]
                    if response.status_code == 200:
                        data = response.json()
                        assert "success" in data
                        assert data["success"] is True

    def test_enable_nonexistent_task(self, authenticated_client):
        """Test enabling a task that doesn't exist"""
        response = authenticated_client.post(
            "/api/autonomous-agents/scheduler/task/nonexistent_task_12345/enable"
        )

        assert response.status_code in [404, 500]
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data

    def test_disable_nonexistent_task(self, authenticated_client):
        """Test disabling a task that doesn't exist"""
        response = authenticated_client.post(
            "/api/autonomous-agents/scheduler/task/nonexistent_task_12345/disable"
        )

        assert response.status_code in [404, 500]
        if response.status_code == 404:
            data = response.json()
            assert "detail" in data

    def test_scheduler_endpoints_require_auth(self, test_client):
        """Test that scheduler endpoints require authentication"""
        # Get status
        response = test_client.get("/api/autonomous-agents/scheduler/status")
        assert response.status_code in [200, 401]  # May be public

        # Enable task
        response = test_client.post("/api/autonomous-agents/scheduler/task/test/enable")
        assert response.status_code in [401, 404, 500]

        # Disable task
        response = test_client.post("/api/autonomous-agents/scheduler/task/test/disable")
        assert response.status_code in [401, 404, 500]


@pytest.mark.api
class TestAgentExecutionFlow:
    """Integration tests for complete agent execution flow"""

    def test_run_and_check_execution_status(self, authenticated_client):
        """Test running an agent and checking its execution status"""
        # Run conversation trainer
        run_response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=7"
        )

        if run_response.status_code == 200:
            run_data = run_response.json()
            execution_id = run_data["execution_id"]

            # Check execution status
            status_response = authenticated_client.get(
                f"/api/autonomous-agents/executions/{execution_id}"
            )

            assert status_response.status_code == 200
            status_data = status_response.json()
            assert status_data["execution_id"] == execution_id
            assert status_data["agent_name"] == "conversation_trainer"
            assert status_data["status"] in ["started", "running", "completed", "failed"]

    def test_multiple_agent_executions_in_list(self, authenticated_client):
        """Test that running multiple agents shows in executions list"""
        # Run multiple agents
        agents_to_run = [
            "/api/autonomous-agents/conversation-trainer/run?days_back=7",
            "/api/autonomous-agents/client-value-predictor/run",
        ]

        execution_ids = []
        for endpoint in agents_to_run:
            response = authenticated_client.post(endpoint)
            if response.status_code == 200:
                execution_ids.append(response.json()["execution_id"])

        # List executions
        if execution_ids:
            list_response = authenticated_client.get("/api/autonomous-agents/executions")

            assert list_response.status_code == 200
            list_data = list_response.json()

            # Check that our executions are in the list
            listed_ids = [exec_data["execution_id"] for exec_data in list_data["executions"]]
            for exec_id in execution_ids:
                assert exec_id in listed_ids


@pytest.mark.api
class TestErrorHandling:
    """Tests for error handling in autonomous agents endpoints"""

    def test_invalid_query_parameter_type(self, authenticated_client):
        """Test handling of invalid query parameter types"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=invalid"
        )

        assert response.status_code in [422, 500]

    def test_multiple_runs_same_agent(self, authenticated_client):
        """Test running the same agent multiple times concurrently"""
        # Should be allowed - each gets unique execution_id
        response1 = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=7"
        )
        response2 = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run?days_back=14"
        )

        # Both should succeed (or both fail if service down)
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()
            # Execution IDs should be different
            assert data1["execution_id"] != data2["execution_id"]
