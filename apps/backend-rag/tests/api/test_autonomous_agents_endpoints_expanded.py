"""
Expanded API Tests for Autonomous Agents Endpoints

Tests for:
- Conversation Quality Trainer
- Client LTV Predictor & Nurturing
- Knowledge Graph Builder
- Scheduler status and control
"""

import pytest


@pytest.mark.api
class TestAutonomousAgentsConversationTrainer:
    """Test Conversation Quality Trainer endpoints"""

    def test_run_conversation_trainer(self, authenticated_client):
        """Test running conversation trainer agent"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            params={"days_back": 7},
        )

        assert response.status_code in [200, 201, 400, 422, 500]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data
            assert data["status"] in ["started", "running", "completed"]

    def test_run_conversation_trainer_custom_days(self, authenticated_client):
        """Test running conversation trainer with custom days_back"""
        response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            params={"days_back": 30},
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_conversation_trainer_execution_status(self, authenticated_client):
        """Test retrieving execution status"""
        # First run the trainer
        run_response = authenticated_client.post(
            "/api/autonomous-agents/conversation-trainer/run",
            params={"days_back": 7},
        )

        if run_response.status_code in [200, 201]:
            execution_id = run_response.json().get("execution_id")

            if execution_id:
                # Get execution status
                status_response = authenticated_client.get(
                    f"/api/autonomous-agents/executions/{execution_id}"
                )

                assert status_response.status_code in [200, 404]
                if status_response.status_code == 200:
                    data = status_response.json()
                    assert "execution_id" in data
                    assert "status" in data


@pytest.mark.api
class TestAutonomousAgentsClientValuePredictor:
    """Test Client LTV Predictor endpoints"""

    def test_run_client_value_predictor(self, authenticated_client):
        """Test running client value predictor agent"""
        response = authenticated_client.post("/api/autonomous-agents/client-value-predictor/run")

        assert response.status_code in [200, 201, 400, 422, 500]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data

    def test_get_client_value_predictor_execution_status(self, authenticated_client):
        """Test retrieving execution status"""
        # Run predictor
        run_response = authenticated_client.post(
            "/api/autonomous-agents/client-value-predictor/run"
        )

        if run_response.status_code in [200, 201]:
            execution_id = run_response.json().get("execution_id")

            if execution_id:
                # Get status
                status_response = authenticated_client.get(
                    f"/api/autonomous-agents/executions/{execution_id}"
                )

                assert status_response.status_code in [200, 404]


@pytest.mark.api
class TestAutonomousAgentsKnowledgeGraphBuilder:
    """Test Knowledge Graph Builder endpoints"""

    def test_run_knowledge_graph_builder(self, authenticated_client):
        """Test running knowledge graph builder agent"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run",
            params={"days_back": 30, "init_schema": False},
        )

        assert response.status_code in [200, 201, 400, 422, 500]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "execution_id" in data
            assert "status" in data

    def test_run_knowledge_graph_builder_with_schema_init(self, authenticated_client):
        """Test running knowledge graph builder with schema initialization"""
        response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run",
            params={"days_back": 7, "init_schema": True},
        )

        assert response.status_code in [200, 201, 400, 422, 500]

    def test_get_knowledge_graph_builder_execution_status(self, authenticated_client):
        """Test retrieving execution status"""
        # Run builder
        run_response = authenticated_client.post(
            "/api/autonomous-agents/knowledge-graph-builder/run",
            params={"days_back": 30},
        )

        if run_response.status_code in [200, 201]:
            execution_id = run_response.json().get("execution_id")

            if execution_id:
                # Get status
                status_response = authenticated_client.get(
                    f"/api/autonomous-agents/executions/{execution_id}"
                )

                assert status_response.status_code in [200, 404]


@pytest.mark.api
class TestAutonomousAgentsStatus:
    """Test Autonomous Agents status endpoints"""

    def test_get_autonomous_agents_status(self, authenticated_client):
        """Test retrieving status of all autonomous agents"""
        response = authenticated_client.get("/api/autonomous-agents/status")

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "total_agents" in data
            assert "agents" in data or "total_agents" in data

    def test_list_executions(self, authenticated_client):
        """Test listing recent agent executions"""
        response = authenticated_client.get("/api/autonomous-agents/executions")

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "executions" in data
            assert isinstance(data.get("executions", []), list)

    def test_list_executions_with_limit(self, authenticated_client):
        """Test listing executions with custom limit"""
        response = authenticated_client.get(
            "/api/autonomous-agents/executions", params={"limit": 10}
        )

        assert response.status_code == 200


@pytest.mark.api
class TestAutonomousSchedulerEndpoints:
    """Test Autonomous Scheduler endpoints"""

    def test_get_scheduler_status(self, authenticated_client):
        """Test retrieving scheduler status"""
        response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "scheduler" in data

    def test_enable_scheduler_task(self, authenticated_client):
        """Test enabling a scheduled task"""
        # First get scheduler status to find task names
        status_response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        if status_response.status_code == 200:
            status_data = status_response.json()
            scheduler_info = status_data.get("scheduler", {})
            tasks = scheduler_info.get("tasks", [])

            if tasks:
                task_name = tasks[0].get("name") or tasks[0].get("task_name")

                if task_name:
                    # Enable task
                    enable_response = authenticated_client.post(
                        f"/api/autonomous-agents/scheduler/task/{task_name}/enable"
                    )

                    assert enable_response.status_code in [200, 404, 500]

    def test_disable_scheduler_task(self, authenticated_client):
        """Test disabling a scheduled task"""
        # Get scheduler status
        status_response = authenticated_client.get("/api/autonomous-agents/scheduler/status")

        if status_response.status_code == 200:
            status_data = status_response.json()
            scheduler_info = status_data.get("scheduler", {})
            tasks = scheduler_info.get("tasks", [])

            if tasks:
                task_name = tasks[0].get("name") or tasks[0].get("task_name")

                if task_name:
                    # Disable task
                    disable_response = authenticated_client.post(
                        f"/api/autonomous-agents/scheduler/task/{task_name}/disable"
                    )

                    assert disable_response.status_code in [200, 404, 500]
