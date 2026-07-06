"""
End-to-end API contract tests for the Autonomous Agents dashboard.

The router stores execution state in memory and starts agents through FastAPI
background tasks, so these tests exercise the real mounted routes while mocking
only the agent implementations behind those routes.
"""

import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# Setup environment before importing the shared API test app.
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")

backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


async def _noop_task() -> None:
    return None


@pytest.fixture(scope="class")
def test_client() -> Generator[TestClient, None, None]:
    """Create the shared FastAPI API-test app without calling a fixture directly."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
    from conftest import test_app

    app_factory = getattr(test_app, "__wrapped__", test_app)
    app_generator = app_factory()
    app_instance = next(app_generator)

    with TestClient(app_instance, raise_server_exceptions=False) as client:
        yield client

    try:
        next(app_generator)
    except StopIteration:
        pass


@pytest.fixture(scope="class")
def auth_headers() -> dict[str, str]:
    """Use the middleware-supported service API key path for these API tests."""
    api_key = os.environ["API_KEYS"].split(",")[0]
    return {"X-API-Key": api_key}


@pytest.fixture(autouse=True)
def reset_agent_state() -> Generator[None, None, None]:
    """Keep the router's in-memory execution store isolated per test."""
    from backend.app.routers import autonomous_agents

    autonomous_agents.agent_executions.clear()
    yield
    autonomous_agents.agent_executions.clear()


def _execution_ids(payload: dict[str, Any]) -> set[str]:
    return {item["execution_id"] for item in payload["executions"]}


@pytest.mark.integration
class TestAutonomousAgentsDashboardE2E:
    """End-to-end tests for the Autonomous Agents dashboard API."""

    def test_dashboard_load_and_view_agent_statuses(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = test_client.get("/api/autonomous-agents/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["tier"] == 1
        assert data["total_agents"] == 3

        agent_names = {agent["name"] for agent in data["agents"]}
        assert agent_names == {
            "Conversation Quality Trainer",
            "Client LTV Predictor & Nurturer",
            "Knowledge Graph Builder",
        }

        for agent in data["agents"]:
            assert agent["status"] in {"idle", "running", "error"}
            assert "success_rate" in agent
            assert "total_runs" in agent
            assert "latest_result" in agent

    def test_run_conversation_trainer_end_to_end(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        with patch("backend.app.routers.autonomous_agents.ConversationTrainer") as trainer_cls:
            trainer = AsyncMock()
            trainer.analyze_winning_patterns.return_value = [{"pattern": "clear pricing"}]
            trainer.generate_prompt_update.return_value = "Improved prompt"
            trainer.create_improvement_pr.return_value = "agent/test-conversation-trainer"
            trainer_cls.return_value = trainer

            response = test_client.post(
                "/api/autonomous-agents/conversation-trainer/run",
                params={"days_back": 7},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        execution_id = data["execution_id"]

        assert data["agent_name"] == "conversation_trainer"
        assert data["status"] == "started"
        assert data["message"] == "Agent execution started in background"
        trainer.analyze_winning_patterns.assert_awaited_once_with(days_back=7)
        trainer.generate_prompt_update.assert_awaited_once_with([{"pattern": "clear pricing"}])
        trainer.create_improvement_pr.assert_awaited_once_with(
            "Improved prompt",
            [{"pattern": "clear pricing"}],
        )

        status_response = test_client.get(
            f"/api/autonomous-agents/executions/{execution_id}",
            headers=auth_headers,
        )
        assert status_response.status_code == 200
        execution = status_response.json()
        assert execution["status"] == "completed"
        assert execution["result"]["insights_found"] == 1
        assert execution["result"]["pr_branch"] == "agent/test-conversation-trainer"

    def test_run_client_value_predictor_end_to_end(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        with patch("backend.app.routers.autonomous_agents.ClientValuePredictor") as predictor_cls:
            predictor = AsyncMock()
            predictor.run_daily_nurturing.return_value = {
                "vip_nurtured": 1,
                "high_risk_contacted": 0,
                "total_messages_sent": 1,
                "errors": [],
            }
            predictor_cls.return_value = predictor

            response = test_client.post(
                "/api/autonomous-agents/client-value-predictor/run",
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        execution_id = data["execution_id"]

        assert data["agent_name"] == "client_value_predictor"
        predictor.run_daily_nurturing.assert_awaited_once_with()

        status_response = test_client.get(
            f"/api/autonomous-agents/executions/{execution_id}",
            headers=auth_headers,
        )
        assert status_response.status_code == 200
        execution = status_response.json()
        assert execution["status"] == "completed"
        assert execution["result"]["vip_nurtured"] == 1
        assert execution["result"]["total_messages_sent"] == 1

    def test_run_knowledge_graph_builder_end_to_end(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        insights = {
            "top_entities": [{"name": "TechCorp Indonesia"}],
            "hubs": [{"name": "Sarah"}],
            "relationship_types": {"WORKS_AT": 1},
        }

        with patch("backend.app.routers.autonomous_agents.KnowledgeGraphBuilder") as builder_cls:
            builder = AsyncMock()
            builder.build_graph_from_all_conversations.return_value = None
            builder.get_entity_insights.return_value = insights
            builder_cls.return_value = builder

            response = test_client.post(
                "/api/autonomous-agents/knowledge-graph-builder/run",
                params={"days_back": 7, "init_schema": False},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        execution_id = data["execution_id"]

        assert data["agent_name"] == "knowledge_graph_builder"
        builder.init_graph_schema.assert_not_awaited()
        builder.build_graph_from_all_conversations.assert_awaited_once_with(days_back=7)
        builder.get_entity_insights.assert_awaited_once_with(top_n=10)

        status_response = test_client.get(
            f"/api/autonomous-agents/executions/{execution_id}",
            headers=auth_headers,
        )
        assert status_response.status_code == 200
        execution = status_response.json()
        assert execution["status"] == "completed"
        assert execution["result"]["top_entities_count"] == 1
        assert execution["result"]["relationship_types_count"] == 1

    def test_view_execution_history(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        from backend.app.routers import autonomous_agents

        autonomous_agents.agent_executions.update(
            {
                "exec_1": {
                    "agent_name": "conversation_trainer",
                    "status": "completed",
                    "started_at": "2026-07-05T10:00:00",
                    "completed_at": "2026-07-05T10:01:00",
                    "result": {"conversations_analyzed": 10},
                },
                "exec_2": {
                    "agent_name": "client_value_predictor",
                    "status": "completed",
                    "started_at": "2026-07-05T10:30:00",
                    "completed_at": "2026-07-05T10:31:00",
                    "result": {"vip_nurtured": 5},
                },
            },
        )

        response = test_client.get(
            "/api/autonomous-agents/executions",
            params={"limit": 10},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert _execution_ids(data) == {"exec_1", "exec_2"}
        assert data["executions"][0]["execution_id"] == "exec_2"

    def test_scheduler_control_end_to_end(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        from backend.services.misc.autonomous_scheduler import get_autonomous_scheduler

        scheduler = get_autonomous_scheduler()
        scheduler.tasks.clear()
        scheduler.register_task("conversation_trainer", _noop_task, 300, enabled=False)

        response = test_client.get(
            "/api/autonomous-agents/scheduler/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "scheduler" in data
        assert data["scheduler"]["tasks"]["conversation_trainer"]["enabled"] is False

        enable_response = test_client.post(
            "/api/autonomous-agents/scheduler/task/conversation_trainer/enable",
            headers=auth_headers,
        )
        assert enable_response.status_code == 200
        assert enable_response.json()["success"] is True

        disable_response = test_client.post(
            "/api/autonomous-agents/scheduler/task/conversation_trainer/disable",
            headers=auth_headers,
        )
        assert disable_response.status_code == 200
        assert disable_response.json()["success"] is True
        assert scheduler.tasks["conversation_trainer"].enabled is False

    def test_complete_user_journey(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        status_response = test_client.get("/api/autonomous-agents/status", headers=auth_headers)
        assert status_response.status_code == 200

        with patch("backend.app.routers.autonomous_agents.ConversationTrainer") as trainer_cls:
            trainer = AsyncMock()
            trainer.analyze_winning_patterns.return_value = [{"pattern": "concise answers"}]
            trainer.generate_prompt_update.return_value = "Better prompt"
            trainer.create_improvement_pr.return_value = "agent/journey-conversation"
            trainer_cls.return_value = trainer

            trainer_response = test_client.post(
                "/api/autonomous-agents/conversation-trainer/run",
                params={"days_back": 7},
                headers=auth_headers,
            )

        with patch("backend.app.routers.autonomous_agents.ClientValuePredictor") as predictor_cls:
            predictor = AsyncMock()
            predictor.run_daily_nurturing.return_value = {
                "vip_nurtured": 2,
                "high_risk_contacted": 1,
                "total_messages_sent": 3,
                "errors": [],
            }
            predictor_cls.return_value = predictor

            predictor_response = test_client.post(
                "/api/autonomous-agents/client-value-predictor/run",
                headers=auth_headers,
            )

        assert trainer_response.status_code == 200
        assert predictor_response.status_code == 200

        trainer_id = trainer_response.json()["execution_id"]
        predictor_id = predictor_response.json()["execution_id"]

        exec_response = test_client.get(
            f"/api/autonomous-agents/executions/{trainer_id}",
            headers=auth_headers,
        )
        assert exec_response.status_code == 200
        assert exec_response.json()["status"] == "completed"

        history_response = test_client.get(
            "/api/autonomous-agents/executions",
            headers=auth_headers,
        )
        assert history_response.status_code == 200
        history = history_response.json()
        assert {trainer_id, predictor_id}.issubset(_execution_ids(history))

        scheduler_response = test_client.get(
            "/api/autonomous-agents/scheduler/status",
            headers=auth_headers,
        )
        assert scheduler_response.status_code == 200
        assert scheduler_response.json()["success"] is True
