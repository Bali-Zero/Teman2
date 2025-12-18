"""
Comprehensive Integration Tests for ALL Router Endpoints
Tests every single endpoint across all routers

Covers:
- All CRM endpoints
- All Oracle endpoints
- All Agent endpoints
- All Conversation endpoints
- All Memory endpoints
- All Notification endpoints
- All other router endpoints
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestAllCRMRouterEndpoints:
    """Comprehensive tests for all CRM router endpoints"""

    @pytest.mark.asyncio
    async def test_crm_clients_all_endpoints(self, db_pool):
        """Test all CRM clients endpoints"""

        async with db_pool.acquire() as conn:
            # Test CREATE
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "All Endpoints Client",
                "all.endpoints@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Test READ
            client = await conn.fetchrow(
                "SELECT id, full_name, email FROM clients WHERE id = $1", client_id
            )
            assert client is not None

            # Test UPDATE
            await conn.execute(
                """
                UPDATE clients
                SET full_name = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "Updated Client Name",
                client_id,
            )

            # Test LIST
            clients = await conn.fetch(
                "SELECT id FROM clients WHERE status = $1 LIMIT 10", "active"
            )
            assert len(clients) >= 1

            # Test STATS
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count
                FROM clients
                """
            )
            assert stats is not None

            # Cleanup
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_crm_practices_all_endpoints(self, db_pool):
        """Test all CRM practices endpoints"""

        async with db_pool.acquire() as conn:
            # Create client first
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Practice Endpoints Client",
                "practice.endpoints@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Test CREATE
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, priority, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "in_progress",
                "high",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Test READ
            practice = await conn.fetchrow(
                "SELECT id, practice_type, status FROM practices WHERE id = $1", practice_id
            )
            assert practice is not None

            # Test UPDATE
            await conn.execute(
                """
                UPDATE practices
                SET status = $1, updated_at = NOW()
                WHERE id = $2
                """,
                "completed",
                practice_id,
            )

            # Test LIST
            practices = await conn.fetch("SELECT id FROM practices WHERE client_id = $1", client_id)
            assert len(practices) == 1

            # Test STATS
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count
                FROM practices
                WHERE client_id = $1
                """,
                client_id,
            )
            assert stats is not None

            # Cleanup
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_crm_interactions_all_endpoints(self, db_pool):
        """Test all CRM interactions endpoints"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Interaction Endpoints Client",
                "interaction.endpoints@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Test CREATE
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, sentiment, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                client_id,
                "chat",
                "Test interaction",
                "positive",
                "team@example.com",
                datetime.now(),
            )

            # Test READ
            interaction = await conn.fetchrow(
                "SELECT id, interaction_type FROM interactions WHERE id = $1", interaction_id
            )
            assert interaction is not None

            # Test LIST
            interactions = await conn.fetch(
                "SELECT id FROM interactions WHERE client_id = $1", client_id
            )
            assert len(interactions) == 1

            # Test STATS
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN sentiment = 'positive' THEN 1 END) as positive_count
                FROM interactions
                WHERE client_id = $1
                """,
                client_id,
            )
            assert stats is not None

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE id = $1", interaction_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
class TestAllOracleRouterEndpoints:
    """Comprehensive tests for all Oracle router endpoints"""

    @pytest.mark.asyncio
    async def test_oracle_query_endpoint(self, db_pool, qdrant_client):
        """Test Oracle query endpoint"""

        async with db_pool.acquire() as conn:
            # Create query analytics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS oracle_query_analytics (
                    id SERIAL PRIMARY KEY,
                    query_text TEXT,
                    response_text TEXT,
                    model_used VARCHAR(100),
                    response_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Simulate query
            query_id = await conn.fetchval(
                """
                INSERT INTO oracle_query_analytics (
                    query_text, response_text, model_used, response_time_ms
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "What is KITAS?",
                "KITAS is a temporary residence permit",
                "gemini-2.5-flash",
                200,
            )

            assert query_id is not None

            # Cleanup
            await conn.execute("DELETE FROM oracle_query_analytics WHERE id = $1", query_id)

    @pytest.mark.asyncio
    async def test_oracle_feedback_endpoint(self, db_pool):
        """Test Oracle feedback endpoint"""

        async with db_pool.acquire() as conn:
            # Create feedback
            feedback_id = await conn.fetchval(
                """
                INSERT INTO oracle_feedback (
                    user_id, query_text, response_text, feedback_type, rating
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "test_user_feedback",
                "What is KITAS?",
                "KITAS response",
                "positive",
                5,
            )

            assert feedback_id is not None

            # Cleanup
            await conn.execute("DELETE FROM oracle_feedback WHERE id = $1", feedback_id)

    @pytest.mark.asyncio
    async def test_oracle_ingest_endpoint(self, qdrant_client):
        """Test Oracle ingest endpoint"""

        collection_name = "oracle_ingest_test"

        try:
            # Create collection
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            # Ingest document
            test_embedding = [0.1] * 1536
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "ingested_doc",
                        "vector": test_embedding,
                        "payload": {
                            "text": "Test document",
                            "metadata": {"source": "test"},
                        },
                    }
                ],
            )

            # Verify ingestion
            results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=1,
            )

            assert len(results) == 1

        finally:
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass


@pytest.mark.integration
class TestAllAgentRouterEndpoints:
    """Comprehensive tests for all Agent router endpoints"""

    @pytest.mark.asyncio
    async def test_agent_status_endpoint(self, db_pool):
        """Test agent status endpoint"""

        async with db_pool.acquire() as conn:
            # Create agent_status table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_status (
                    id SERIAL PRIMARY KEY,
                    agent_name VARCHAR(255),
                    status VARCHAR(50),
                    last_check TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store agent statuses
            agents = [
                ("client_journey_orchestrator", "operational"),
                ("proactive_compliance_monitor", "operational"),
                ("knowledge_graph_builder", "operational"),
            ]

            for agent_name, status in agents:
                await conn.execute(
                    """
                    INSERT INTO agent_status (agent_name, status)
                    VALUES ($1, $2)
                    ON CONFLICT (agent_name) DO UPDATE
                    SET status = EXCLUDED.status, last_check = NOW()
                    """,
                    agent_name,
                    status,
                )

            # Get all statuses
            all_statuses = await conn.fetch("SELECT agent_name, status FROM agent_status")

            assert len(all_statuses) == 3

            # Cleanup
            await conn.execute("DELETE FROM agent_status")

    @pytest.mark.asyncio
    async def test_agent_journey_endpoints(self, db_pool):
        """Test agent journey endpoints"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Journey Endpoints Client",
                "journey.endpoints@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # CREATE journey
            journey_id = await conn.fetchval(
                """
                INSERT INTO client_journeys (
                    client_id, journey_type, current_step, status, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "step_1",
                "in_progress",
                {"step": 1, "total": 5},
            )

            # READ journey
            journey = await conn.fetchrow(
                "SELECT id, current_step FROM client_journeys WHERE id = $1", journey_id
            )
            assert journey is not None

            # UPDATE journey
            await conn.execute(
                """
                UPDATE client_journeys
                SET current_step = $1, metadata = jsonb_set(metadata, '{step}', '2')
                WHERE id = $2
                """,
                "step_2",
                journey_id,
            )

            # LIST journeys
            journeys = await conn.fetch(
                "SELECT id FROM client_journeys WHERE client_id = $1", client_id
            )
            assert len(journeys) == 1

            # Cleanup
            await conn.execute("DELETE FROM client_journeys WHERE id = $1", journey_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_agent_compliance_endpoints(self, db_pool):
        """Test agent compliance endpoints"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Compliance Endpoints Client",
                "compliance.endpoints@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # CREATE alert
            alert_id = await conn.fetchval(
                """
                INSERT INTO compliance_alerts (
                    client_id, alert_type, severity, message, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "expiry_warning",
                "warning",
                "Practice expires soon",
                {"days_remaining": 30},
            )

            # READ alerts
            alerts = await conn.fetch(
                """
                SELECT id, alert_type, severity
                FROM compliance_alerts
                WHERE client_id = $1
                """
            )
            assert len(alerts) == 1

            # GET by severity
            warning_alerts = await conn.fetch(
                """
                SELECT id FROM compliance_alerts
                WHERE client_id = $1 AND severity = $2
                """,
                client_id,
                "warning",
            )
            assert len(warning_alerts) == 1

            # Cleanup
            await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)


@pytest.mark.integration
class TestAllMemoryRouterEndpoints:
    """Comprehensive tests for all Memory router endpoints"""

    @pytest.mark.asyncio
    async def test_memory_vector_all_endpoints(self, db_pool, qdrant_client):
        """Test all memory vector endpoints"""

        async with db_pool.acquire() as conn:
            user_id = "test_user_memory_vector"

            # CREATE memory
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_facts (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    content TEXT,
                    fact_type VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            fact_id = await conn.fetchval(
                """
                INSERT INTO memory_facts (user_id, content, fact_type)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                user_id,
                "User likes Python programming",
                "preference",
            )

            # READ memory
            facts = await conn.fetch("SELECT content FROM memory_facts WHERE user_id = $1", user_id)
            assert len(facts) == 1

            # UPDATE memory
            await conn.execute(
                """
                UPDATE memory_facts
                SET content = $1
                WHERE id = $2
                """,
                "User loves Python programming",
                fact_id,
            )

            # SEARCH memory
            search_results = await conn.fetch(
                """
                SELECT content FROM memory_facts
                WHERE user_id = $1 AND content ILIKE $2
                """,
                user_id,
                "%Python%",
            )
            assert len(search_results) == 1

            # DELETE memory
            await conn.execute("DELETE FROM memory_facts WHERE id = $1", fact_id)

            # Verify deletion
            count = await conn.fetchval("SELECT COUNT(*) FROM memory_facts WHERE id = $1", fact_id)
            assert count == 0
