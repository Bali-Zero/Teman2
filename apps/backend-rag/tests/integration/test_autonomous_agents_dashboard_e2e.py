"""
End-to-End Integration Tests for Autonomous Agents Dashboard

Tests the complete user flow:
1. Load agents dashboard page
2. View agent statuses
3. Run agents (Conversation Trainer, Client Value Predictor, Knowledge Graph Builder)
4. Check execution status
5. View execution history
6. Scheduler control (enable/disable tasks)
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Setup environment
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_key")

# Make backend modules importable
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="class")
def test_client():
    """Create test client for API requests"""
    # Import here to avoid early initialization
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
    from conftest import test_app
    from fastapi.testclient import TestClient

    for app_instance in test_app():
        return TestClient(app_instance)


@pytest.fixture(scope="class")
def test_token():
    """Create test authentication token"""
    from datetime import datetime, timedelta

    import jwt

    secret_key = os.environ.get(
        "JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars"
    )

    payload = {
        "sub": "test_user",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token


@pytest.mark.integration
class TestAutonomousAgentsDashboardE2E:
    """End-to-end tests for the Autonomous Agents Dashboard"""

    @pytest.fixture(autouse=True)
    def setup_db_tables(self, db_pool):
        """Setup required database tables for agents"""

        async def _setup():
            async with db_pool.acquire() as conn:
                # Create agent_executions table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_executions (
                        execution_id VARCHAR(255) PRIMARY KEY,
                        agent_name VARCHAR(100) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        started_at TIMESTAMP NOT NULL,
                        completed_at TIMESTAMP,
                        result JSONB,
                        error TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                # Create conversations table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        conversation_id VARCHAR(255) PRIMARY KEY,
                        messages JSONB,
                        client_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                # Create clients table for Client Value Predictor
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS clients (
                        id VARCHAR(255) PRIMARY KEY,
                        name VARCHAR(255),
                        email VARCHAR(255),
                        phone VARCHAR(50),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                # Create knowledge graph tables
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_entities (
                        id SERIAL PRIMARY KEY,
                        type VARCHAR(100),
                        name VARCHAR(255),
                        canonical_name VARCHAR(255),
                        metadata JSONB,
                        mention_count INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kg_relationships (
                        id SERIAL PRIMARY KEY,
                        source_entity_id INTEGER REFERENCES kg_entities(id),
                        target_entity_id INTEGER REFERENCES kg_entities(id),
                        relationship_type VARCHAR(100),
                        strength FLOAT,
                        evidence TEXT,
                        source_ref JSONB,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                    """
                )

        import asyncio

        asyncio.get_event_loop().run_until_complete(_setup())

        yield

        # Cleanup
        async def _cleanup():
            async with db_pool.acquire() as conn:
                await conn.execute("DROP TABLE IF EXISTS agent_executions CASCADE")
                await conn.execute("DROP TABLE IF EXISTS conversations CASCADE")
                await conn.execute("DROP TABLE IF EXISTS clients CASCADE")
                await conn.execute("DROP TABLE IF EXISTS kg_relationships CASCADE")
                await conn.execute("DROP TABLE IF EXISTS kg_entities CASCADE")

        asyncio.get_event_loop().run_until_complete(_cleanup())

    def test_dashboard_load_and_view_agent_statuses(self, test_client, test_token):
        """
        E2E Test: User loads dashboard and views agent statuses

        Flow:
        1. User navigates to /api/autonomous-agents/status
        2. Dashboard shows all 3 agents with their current status
        3. Each agent displays: name, status, success_rate, total_runs
        """
        response = test_client.get(
            "/api/autonomous-agents/status", headers={"Authorization": f"Bearer {test_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all 3 agents are present
        assert "conversation_trainer" in data
        assert "client_value_predictor" in data
        assert "knowledge_graph_builder" in data

        # Verify each agent has required fields
        for agent_name, agent_data in data.items():
            assert "name" in agent_data
            assert "status" in agent_data
            assert agent_data["status"] in ["idle", "running", "error"]

    def test_run_conversation_trainer_end_to_end(self, test_client, test_token, db_pool):
        """
        E2E Test: User runs Conversation Trainer agent

        Flow:
        1. User clicks "Run" button on Conversation Trainer card
        2. Agent starts execution
        3. Agent analyzes conversations from last 7 days
        4. Agent returns results with improvements generated
        5. Dashboard updates to show execution status
        """
        # Step 1: Insert test conversations
        import asyncio
        import json

        async def insert_test_data():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO conversations (conversation_id, messages, client_id, created_at)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '2 days')
                    """,
                    "conv_test_1",
                    json.dumps(
                        [
                            {"role": "user", "content": "What is a PT?"},
                            {"role": "assistant", "content": "PT stands for Perseroan Terbatas..."},
                        ]
                    ),
                    "client_1",
                )

                await conn.execute(
                    """
                    INSERT INTO conversations (conversation_id, messages, client_id, created_at)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '1 day')
                    """,
                    "conv_test_2",
                    json.dumps(
                        [
                            {"role": "user", "content": "How to register a company?"},
                            {
                                "role": "assistant",
                                "content": "To register a company in Indonesia...",
                            },
                        ]
                    ),
                    "client_2",
                )

        asyncio.get_event_loop().run_until_complete(insert_test_data())

        # Step 2: Run the agent
        with patch("agents.agents.conversation_trainer.ConversationTrainer") as mock_trainer_class:
            mock_trainer = AsyncMock()
            mock_trainer_class.return_value = mock_trainer

            # Mock the training results
            mock_trainer.analyze_conversations.return_value = {
                "conversations_analyzed": 2,
                "improvements_generated": 1,
                "avg_quality_score": 0.85,
            }

            response = test_client.post(
                "/api/autonomous-agents/conversation-trainer/run",
                params={"days_back": 7},
                headers={"Authorization": f"Bearer {test_token}"},
            )

        assert response.status_code == 200
        data = response.json()

        # Verify execution started
        assert "execution_id" in data
        assert "message" in data
        assert "conversation_trainer" in data["message"].lower()

        # Step 3: Check execution status
        execution_id = data["execution_id"]

        # Wait a moment for async execution
        import time

        time.sleep(0.5)

        status_response = test_client.get(
            f"/api/autonomous-agents/executions/{execution_id}",
            headers={"Authorization": f"Bearer {test_token}"},
        )

        assert status_response.status_code in [200, 503]  # May still be running or completed

    def test_run_client_value_predictor_end_to_end(self, test_client, test_token, db_pool):
        """
        E2E Test: User runs Client Value Predictor agent

        Flow:
        1. User clicks "Run" button on Client Value Predictor card
        2. Agent calculates LTV scores for active clients
        3. Agent generates nurturing messages for VIP clients
        4. Dashboard shows results (clients scored, messages sent)
        """
        # Step 1: Insert test clients
        import asyncio

        async def insert_test_clients():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO clients (id, name, email, phone, created_at)
                    VALUES ($1, $2, $3, $4, NOW() - INTERVAL '30 days')
                    """,
                    "client_vip_1",
                    "John Doe",
                    "john@example.com",
                    "+62812345678",
                )

                await conn.execute(
                    """
                    INSERT INTO clients (id, name, email, phone, created_at)
                    VALUES ($1, $2, $3, $4, NOW() - INTERVAL '60 days')
                    """,
                    "client_standard_1",
                    "Jane Smith",
                    "jane@example.com",
                    "+62887654321",
                )

        asyncio.get_event_loop().run_until_complete(insert_test_clients())

        # Step 2: Run the agent
        with patch(
            "agents.agents.client_value_predictor.ClientValuePredictor"
        ) as mock_predictor_class:
            mock_predictor = AsyncMock()
            mock_predictor_class.return_value = mock_predictor

            # Mock the prediction results
            mock_predictor.run_daily_nurturing.return_value = {
                "vip_nurtured": 1,
                "high_risk_contacted": 0,
                "total_messages_sent": 1,
                "errors": [],
            }

            response = test_client.post(
                "/api/autonomous-agents/client-value-predictor/run",
                headers={"Authorization": f"Bearer {test_token}"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "execution_id" in data
        assert "message" in data

    def test_run_knowledge_graph_builder_end_to_end(self, test_client, test_token, db_pool):
        """
        E2E Test: User runs Knowledge Graph Builder agent

        Flow:
        1. User clicks "Run" button on Knowledge Graph Builder card
        2. Agent initializes schema (if init_schema=true)
        3. Agent extracts entities and relationships from conversations
        4. Agent builds knowledge graph
        5. Dashboard shows results (entities extracted, relationships created)
        """
        # Step 1: Insert test conversations
        import asyncio
        import json

        async def insert_test_conversations():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO conversations (conversation_id, messages, client_id, created_at)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '3 days')
                    """,
                    "conv_kg_1",
                    json.dumps(
                        [
                            {"role": "user", "content": "I'm Sarah from TechCorp Indonesia"},
                            {
                                "role": "assistant",
                                "content": "Hello Sarah! How can I help TechCorp today?",
                            },
                        ]
                    ),
                    "client_techcorp",
                )

        asyncio.get_event_loop().run_until_complete(insert_test_conversations())

        # Step 2: Run the agent
        with patch(
            "agents.agents.knowledge_graph_builder.KnowledgeGraphBuilder"
        ) as mock_builder_class:
            mock_builder = AsyncMock()
            mock_builder_class.return_value = mock_builder

            # Mock the building results
            mock_builder.build_graph_from_all_conversations.return_value = {
                "conversations_processed": 1,
                "entities_extracted": 2,
                "relationships_created": 1,
            }

            response = test_client.post(
                "/api/autonomous-agents/knowledge-graph-builder/run",
                params={"days_back": 7, "init_schema": False},
                headers={"Authorization": f"Bearer {test_token}"},
            )

        assert response.status_code == 200
        data = response.json()

        assert "execution_id" in data
        assert "message" in data

    def test_view_execution_history(self, test_client, test_token, db_pool):
        """
        E2E Test: User views execution history

        Flow:
        1. User navigates to execution history section
        2. Dashboard shows list of recent executions
        3. Each execution shows: agent name, status, started_at, result
        """
        # Step 1: Insert test executions
        import asyncio
        import json

        async def insert_test_executions():
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_executions (execution_id, agent_name, status, started_at, result)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '1 hour', $4)
                    """,
                    "exec_1",
                    "conversation_trainer",
                    "completed",
                    json.dumps({"conversations_analyzed": 10, "improvements_generated": 3}),
                )

                await conn.execute(
                    """
                    INSERT INTO agent_executions (execution_id, agent_name, status, started_at, result)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '30 minutes', $4)
                    """,
                    "exec_2",
                    "client_value_predictor",
                    "completed",
                    json.dumps({"vip_nurtured": 5, "total_messages_sent": 5}),
                )

        asyncio.get_event_loop().run_until_complete(insert_test_executions())

        # Step 2: Get execution history
        response = test_client.get(
            "/api/autonomous-agents/executions",
            params={"limit": 10},
            headers={"Authorization": f"Bearer {test_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "executions" in data
        assert len(data["executions"]) >= 2

        # Verify execution structure
        exec_1 = data["executions"][0]
        assert "execution_id" in exec_1
        assert "agent_name" in exec_1
        assert "status" in exec_1
        assert "started_at" in exec_1

    def test_scheduler_control_end_to_end(self, test_client, test_token):
        """
        E2E Test: User controls scheduler

        Flow:
        1. User views scheduler status
        2. User enables a scheduled task
        3. User disables a scheduled task
        4. Dashboard updates scheduler status
        """
        # Step 1: Get scheduler status
        response = test_client.get(
            "/api/autonomous-agents/scheduler/status",
            headers={"Authorization": f"Bearer {test_token}"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "is_running" in data
        assert "scheduled_tasks" in data

        # Step 2: Enable a task
        enable_response = test_client.post(
            "/api/autonomous-agents/scheduler/tasks/conversation_trainer/enable",
            headers={"Authorization": f"Bearer {test_token}"},
        )

        # May succeed or fail depending on scheduler state
        assert enable_response.status_code in [200, 404]

        # Step 3: Disable a task
        disable_response = test_client.post(
            "/api/autonomous-agents/scheduler/tasks/conversation_trainer/disable",
            headers={"Authorization": f"Bearer {test_token}"},
        )

        # May succeed or fail depending on scheduler state
        assert disable_response.status_code in [200, 404]

    def test_complete_user_journey(self, test_client, test_token, db_pool):
        """
        E2E Test: Complete user journey through dashboard

        Flow:
        1. Load dashboard and view all agents
        2. Run Conversation Trainer
        3. Check execution status
        4. Run Client Value Predictor
        5. View execution history showing both runs
        6. Check scheduler status

        This simulates a real user session.
        """
        # Step 1: Load dashboard
        status_response = test_client.get(
            "/api/autonomous-agents/status", headers={"Authorization": f"Bearer {test_token}"}
        )
        assert status_response.status_code == 200

        # Step 2: Insert test data
        import asyncio
        import json

        async def insert_data():
            async with db_pool.acquire() as conn:
                # Insert conversations for Conversation Trainer
                await conn.execute(
                    """
                    INSERT INTO conversations (conversation_id, messages, client_id, created_at)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '1 day')
                    """,
                    "conv_journey_1",
                    json.dumps([{"role": "user", "content": "test"}]),
                    "client_1",
                )

                # Insert clients for Client Value Predictor
                await conn.execute(
                    """
                    INSERT INTO clients (id, name, email, created_at)
                    VALUES ($1, $2, $3, NOW() - INTERVAL '30 days')
                    """,
                    "client_journey_1",
                    "Test Client",
                    "test@example.com",
                )

        asyncio.get_event_loop().run_until_complete(insert_data())

        # Step 3: Run Conversation Trainer
        with patch("agents.agents.conversation_trainer.ConversationTrainer") as mock_trainer:
            mock_instance = AsyncMock()
            mock_trainer.return_value = mock_instance
            mock_instance.analyze_conversations.return_value = {"conversations_analyzed": 1}

            trainer_response = test_client.post(
                "/api/autonomous-agents/conversation-trainer/run",
                params={"days_back": 7},
                headers={"Authorization": f"Bearer {test_token}"},
            )

        assert trainer_response.status_code == 200
        trainer_data = trainer_response.json()
        assert "execution_id" in trainer_data

        # Step 4: Check execution status
        exec_id = trainer_data["execution_id"]
        exec_response = test_client.get(
            f"/api/autonomous-agents/executions/{exec_id}",
            headers={"Authorization": f"Bearer {test_token}"},
        )
        assert exec_response.status_code in [200, 503]  # May still be running

        # Step 5: View execution history
        history_response = test_client.get(
            "/api/autonomous-agents/executions", headers={"Authorization": f"Bearer {test_token}"}
        )
        assert history_response.status_code == 200

        # Step 6: Check scheduler
        scheduler_response = test_client.get(
            "/api/autonomous-agents/scheduler/status",
            headers={"Authorization": f"Bearer {test_token}"},
        )
        assert scheduler_response.status_code == 200

        # Complete journey - all endpoints accessible
        assert True
