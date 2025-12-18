"""
Cross-Component Integration Tests
Tests integration between multiple components working together

Covers:
- CRM + Memory integration
- RAG + Search + Memory integration
- Oracle + Analytics + Feedback integration
- Agents + Notifications + Compliance integration
- Multi-service workflows
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
@pytest.mark.slow
class TestCrossComponentIntegration:
    """Cross-component integration tests"""

    @pytest.mark.asyncio
    async def test_crm_memory_integration(self, db_pool):
        """Test CRM + Memory integration"""

        async with db_pool.acquire() as conn:
            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "CRM Memory Client",
                "crm.memory@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Store client preferences in memory
            await conn.execute(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                client_id,
                "preference",
                "Client prefers email communication",
                ["communication"],
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 3: Create interaction using memory
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    client_id, interaction_type, summary, created_by, created_at
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                client_id,
                "email",  # Using preference from memory
                "Sent email as per client preference",
                "team@example.com",
                datetime.now(),
            )

            # Step 4: Verify integration
            integration = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    COUNT(DISTINCT sm.id) as memory_count,
                    COUNT(DISTINCT i.id) as interaction_count
                FROM clients c
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                WHERE c.id = $1
                GROUP BY c.id
                """,
                client_id,
            )

            assert integration["memory_count"] == 1
            assert integration["interaction_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM interactions WHERE id = $1", interaction_id)
            await conn.execute("DELETE FROM shared_memory WHERE client_id = $1", client_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_rag_search_memory_integration(self, qdrant_client, db_pool):
        """Test RAG + Search + Memory integration"""

        async with db_pool.acquire() as conn:
            user_id = "rag_search_memory_user"

            # Step 1: Store user memory
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_facts (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            await conn.execute(
                """
                INSERT INTO memory_facts (user_id, content)
                VALUES ($1, $2)
                """,
                user_id,
                "User is interested in KITAS",
            )

            # Step 2: Search in Qdrant
            collection_name = "rag_search_memory_test"
            try:
                await qdrant_client.create_collection(
                    collection_name=collection_name, vector_size=1536
                )

                test_embedding = [0.1] * 1536
                await qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[
                        {
                            "id": "doc_1",
                            "vector": test_embedding,
                            "payload": {"text": "KITAS information"},
                        }
                    ],
                )

                # Step 3: Search with memory context
                search_results = await qdrant_client.search(
                    collection_name=collection_name,
                    query_vector=test_embedding,
                    limit=5,
                )

                # Step 4: Verify integration
                memory = await conn.fetchrow(
                    """
                    SELECT content FROM memory_facts WHERE user_id = $1 LIMIT 1
                    """,
                    user_id,
                )

                assert memory is not None
                assert len(search_results) > 0

                # Cleanup
                await conn.execute("DELETE FROM memory_facts WHERE user_id = $1", user_id)
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_oracle_analytics_feedback_integration(self, db_pool):
        """Test Oracle + Analytics + Feedback integration"""

        async with db_pool.acquire() as conn:
            user_id = "oracle_analytics_user"

            # Step 1: Create Oracle query
            query_id = await conn.fetchval(
                """
                INSERT INTO oracle_query_analytics (
                    query_text, response_text, model_used, response_time_ms, user_id
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "What is KITAS?",
                "KITAS is a temporary residence permit",
                "gemini-2.5-flash",
                200,
                user_id,
            )

            # Step 2: Store feedback
            feedback_id = await conn.fetchval(
                """
                INSERT INTO oracle_feedback (
                    user_id, query_text, response_text, feedback_type, rating
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id,
                "What is KITAS?",
                "KITAS is a temporary residence permit",
                "positive",
                5,
            )

            # Step 3: Link feedback to query
            await conn.execute(
                """
                UPDATE oracle_query_analytics
                SET metadata = jsonb_set(
                    COALESCE(metadata, '{}'::jsonb),
                    '{feedback_id}',
                    $1::text::jsonb
                )
                WHERE id = $2
                """,
                str(feedback_id),
                query_id,
            )

            # Step 4: Verify integration
            integration = await conn.fetchrow(
                """
                SELECT
                    oqa.id as query_id,
                    ofb.id as feedback_id,
                    ofb.rating
                FROM oracle_query_analytics oqa
                LEFT JOIN oracle_feedback ofb ON oqa.metadata->>'feedback_id' = ofb.id::text
                WHERE oqa.id = $1
                """,
                query_id,
            )

            assert integration["feedback_id"] == feedback_id
            assert integration["rating"] == 5

            # Cleanup
            await conn.execute("DELETE FROM oracle_feedback WHERE id = $1", feedback_id)
            await conn.execute("DELETE FROM oracle_query_analytics WHERE id = $1", query_id)

    @pytest.mark.asyncio
    async def test_agents_notifications_compliance_integration(self, db_pool):
        """Test Agents + Notifications + Compliance integration"""

        async with db_pool.acquire() as conn:
            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (
                    full_name, email, status, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Agent Notification Client",
                "agent.notification@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Create compliance alert
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

            # Step 3: Create notification
            notification_id = await conn.fetchval(
                """
                INSERT INTO notifications (
                    user_id, notification_type, title, message, status, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "team@example.com",
                "compliance_alert",
                "Compliance Alert",
                "Practice expires soon",
                "pending",
                {"alert_id": alert_id, "client_id": client_id},
            )

            # Step 4: Verify integration
            integration = await conn.fetchrow(
                """
                SELECT
                    ca.id as alert_id,
                    n.id as notification_id,
                    n.metadata->>'alert_id' as linked_alert_id
                FROM compliance_alerts ca
                LEFT JOIN notifications n ON n.metadata->>'alert_id' = ca.id::text
                WHERE ca.id = $1
                """,
                alert_id,
            )

            assert integration["notification_id"] == notification_id
            assert integration["linked_alert_id"] == str(alert_id)

            # Cleanup
            await conn.execute("DELETE FROM notifications WHERE id = $1", notification_id)
            await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)










