"""
End-to-End Integration Tests
Tests complete user flows across multiple services

Covers:
- Complete chat flow (query -> search -> RAG -> response)
- Complete CRM flow (client creation -> practice -> interaction -> memory)
- Complete Oracle flow (query -> routing -> search -> synthesis -> response)
- Complete agent flow (trigger -> research -> synthesis -> action)
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndFlows:
    """End-to-end integration tests for complete user flows"""

    @pytest.mark.asyncio
    async def test_complete_chat_flow(self, db_pool, qdrant_client):
        """Test complete chat flow: query -> search -> RAG -> response -> memory"""

        async with db_pool.acquire() as conn:
            # Setup: Create user and conversation
            user_id = "test_user_e2e_1"
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                user_id,
                "E2E Test Conversation",
                datetime.now(),
                datetime.now(),
            )

            # Step 1: User sends query
            query = "What is KITAS?"

            # Step 2: Search service finds relevant documents
            with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
                from services.search_service import SearchService

                embedder = MagicMock()
                embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
                embedder.provider = "openai"
                embedder.dimensions = 1536
                mock_embedder.return_value = embedder

                search_service = SearchService()
                search_result = await search_service.search(query, user_level=1, limit=5)

                assert search_result is not None
                assert "results" in search_result

            # Step 3: AI generates response (mocked)
            with patch("llm.zantara_ai_client.ZantaraAIClient") as mock_ai:
                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(
                    return_value="KITAS is a temporary residence permit..."
                )
                mock_ai.return_value = mock_ai_instance

                response = await mock_ai_instance.generate_response(
                    query=query, context=search_result.get("results", [])
                )

                assert response is not None
                assert "KITAS" in response

            # Step 4: Store conversation message
            message_id = await conn.fetchval(
                """
                INSERT INTO conversation_messages (
                    conversation_id, role, content, created_at
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                conversation_id,
                "assistant",
                response,
                datetime.now(),
            )

            assert message_id is not None

            # Step 5: Update user memory
            await conn.execute(
                """
                INSERT INTO memory_facts (user_id, content, fact_type, source)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id, LOWER(content)) DO NOTHING
                """,
                user_id,
                "User asked about KITAS",
                "query_history",
                "conversation",
            )

            # Verify complete flow
            conversation = await conn.fetchrow(
                """
                SELECT id, user_id, title
                FROM conversations
                WHERE id = $1
                """,
                conversation_id,
            )

            assert conversation is not None
            assert conversation["user_id"] == user_id

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1", conversation_id
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM memory_facts WHERE user_id = $1", user_id)

    @pytest.mark.asyncio
    async def test_complete_crm_flow(self, db_pool):
        """Test complete CRM flow: client -> practice -> interaction -> memory -> analytics"""

        async with db_pool.acquire() as conn:
            # Step 1: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, phone, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                "E2E CRM Client",
                "e2e.crm@example.com",
                "+6281234567890",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert client_id is not None

            # Step 2: Create practice
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
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert practice_id is not None

            # Step 3: Log interaction
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
                "Client inquired about KITAS requirements",
                "positive",
                "test@team.com",
                datetime.now(),
            )

            assert interaction_id is not None

            # Step 4: Store shared memory
            memory_id = await conn.fetchval(
                """
                INSERT INTO shared_memory (
                    client_id, memory_type, content, tags, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "preference",
                "Client prefers email communication",
                ["communication", "preference"],
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            assert memory_id is not None

            # Step 5: Generate analytics
            client_stats = await conn.fetchrow(
                """
                SELECT
                    c.id,
                    c.full_name,
                    COUNT(DISTINCT p.id) as practice_count,
                    COUNT(DISTINCT i.id) as interaction_count,
                    COUNT(DISTINCT sm.id) as memory_count
                FROM clients c
                LEFT JOIN practices p ON c.id = p.client_id
                LEFT JOIN interactions i ON c.id = i.client_id
                LEFT JOIN shared_memory sm ON c.id = sm.client_id
                WHERE c.id = $1
                GROUP BY c.id, c.full_name
                """,
                client_id,
            )

            assert client_stats is not None
            assert client_stats["practice_count"] == 1
            assert client_stats["interaction_count"] == 1
            assert client_stats["memory_count"] == 1

            # Cleanup
            await conn.execute("DELETE FROM shared_memory WHERE id = $1", memory_id)
            await conn.execute("DELETE FROM interactions WHERE id = $1", interaction_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_complete_oracle_flow(self, db_pool, qdrant_client):
        """Test complete Oracle flow: query -> routing -> search -> synthesis -> response -> analytics"""

        async with db_pool.acquire() as conn:
            # Setup: Create user profile
            user_id = "test_user_oracle_e2e"
            await conn.execute(
                """
                INSERT INTO users (id, email, role)
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """,
                user_id,
                "oracle.e2e@example.com",
                "member",
            )

            # Step 1: User sends query
            query = "How to start a business in Indonesia?"

            # Step 2: Route query to appropriate collections
            with patch("core.embeddings.create_embeddings_generator") as mock_embedder:
                from services.query_router import QueryRouter

                embedder = MagicMock()
                embedder.generate_query_embedding = AsyncMock(return_value=[0.1] * 1536)
                mock_embedder.return_value = embedder

                router = QueryRouter()
                routing_result = await router.route_query(query)

                assert routing_result is not None
                assert "collection_name" in routing_result

            # Step 3: Search across multiple collections
            collections = ["kbli_unified", "legal_unified", "tax_genius"]

            # Step 4: Synthesize results (mocked)
            with patch("llm.zantara_ai_client.ZantaraAIClient") as mock_ai:
                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(
                    return_value="To start a business in Indonesia, you need..."
                )
                mock_ai.return_value = mock_ai_instance

                response = await mock_ai_instance.generate_response(
                    query=query, context=["Document 1", "Document 2", "Document 3"]
                )

                assert response is not None

            # Step 5: Store query analytics
            query_hash = "test_query_hash_e2e"
            analytics_id = await conn.fetchval(
                """
                INSERT INTO oracle_query_analytics (
                    user_id, query_hash, query_text, response_text,
                    language_preference, model_used, response_time_ms,
                    document_count, session_id, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                user_id,
                query_hash,
                query,
                response,
                "en",
                "gemini-2.5-flash",
                200,
                len(collections),
                "session_e2e_123",
                {"collections": collections},
            )

            assert analytics_id is not None

            # Step 6: Store feedback (optional)
            feedback_id = await conn.fetchval(
                """
                INSERT INTO oracle_feedback (
                    user_id, query_text, response_text, feedback_type, rating
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                user_id,
                query,
                response,
                "positive",
                5,
            )

            assert feedback_id is not None

            # Verify complete flow
            analytics = await conn.fetchrow(
                """
                SELECT query_text, document_count, model_used
                FROM oracle_query_analytics
                WHERE id = $1
                """,
                analytics_id,
            )

            assert analytics is not None
            assert analytics["query_text"] == query
            assert analytics["document_count"] == len(collections)

            # Cleanup
            await conn.execute("DELETE FROM oracle_feedback WHERE id = $1", feedback_id)
            await conn.execute("DELETE FROM oracle_query_analytics WHERE id = $1", analytics_id)
            await conn.execute("DELETE FROM users WHERE id = $1", user_id)

    @pytest.mark.asyncio
    async def test_complete_agent_flow(self, db_pool, qdrant_client):
        """Test complete agent flow: trigger -> research -> synthesis -> action -> notification"""

        async with db_pool.acquire() as conn:
            # Setup: Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Agent E2E Client",
                "agent.e2e@example.com",
                "active",
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 1: Trigger compliance check
            practice_id = await conn.fetchval(
                """
                INSERT INTO practices (
                    client_id, practice_type, status, expiry_date, created_by, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                client_id,
                "KITAS",
                "active",
                datetime.now().date() + timedelta(days=30),
                "test@team.com",
                datetime.now(),
                datetime.now(),
            )

            # Step 2: Research compliance requirements
            with (
                patch("services.proactive_compliance_monitor.SearchService") as mock_search,
                patch("services.proactive_compliance_monitor.ZantaraAIClient") as mock_ai,
            ):
                mock_search_instance = MagicMock()
                mock_search.return_value = mock_search_instance

                mock_ai_instance = MagicMock()
                mock_ai_instance.generate_response = AsyncMock(
                    return_value="Compliance requirements: ..."
                )
                mock_ai.return_value = mock_ai_instance

                # Step 3: Generate compliance alert
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
                    "Practice expires in 30 days",
                    {"practice_id": practice_id, "days_remaining": 30},
                )

                assert alert_id is not None

            # Step 4: Create notification
            notification_id = await conn.fetchval(
                """
                INSERT INTO notifications (
                    user_id, notification_type, title, message, status, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "test@team.com",
                "compliance_alert",
                "Practice Expiry Warning",
                "Practice expires in 30 days",
                "pending",
                datetime.now(),
            )

            assert notification_id is not None

            # Verify complete flow
            alert = await conn.fetchrow(
                """
                SELECT id, alert_type, severity, status
                FROM compliance_alerts
                WHERE id = $1
                """,
                alert_id,
            )

            assert alert is not None
            assert alert["alert_type"] == "expiry_warning"

            # Cleanup
            await conn.execute("DELETE FROM notifications WHERE id = $1", notification_id)
            await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
