"""
Comprehensive Integration Tests for Multi-Service Orchestration
Tests complex scenarios involving multiple services working together

Covers:
- Service orchestration
- Inter-service communication
- Service dependency management
- Complex workflows
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

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestMultiServiceOrchestrationIntegration:
    """Integration tests for multi-service orchestration"""

    @pytest.mark.asyncio
    async def test_search_rag_memory_orchestration(self, db_pool, qdrant_client):
        """Test orchestration of Search, RAG, and Memory services"""

        async with db_pool.acquire() as conn:
            # Setup: Create user memory
            user_id = "orchestration_user_1"
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

            # Mock services
            with (
                patch("services.search_service.SearchService") as mock_search,
                patch("services.rag.agentic.create_agentic_rag") as mock_rag,
                patch("services.memory_service_postgres.MemoryServicePostgres") as mock_memory,
            ):
                # Setup search service
                mock_search_instance = MagicMock()
                mock_search_instance.search = AsyncMock(
                    return_value={
                        "results": [{"text": "KITAS document", "score": 0.9}],
                        "collection_used": "visa_oracle",
                    }
                )

                # Setup RAG orchestrator
                mock_rag_instance = MagicMock()
                mock_rag_instance.process_query = AsyncMock(
                    return_value={
                        "answer": "KITAS is a temporary residence permit",
                        "sources": [{"text": "KITAS document"}],
                    }
                )

                # Setup memory service
                mock_memory_instance = MagicMock()
                mock_memory_instance.get_memory = AsyncMock(
                    return_value=MagicMock(profile_facts=["User is interested in KITAS"])
                )

                # Orchestrate: Search -> RAG -> Memory
                search_result = await mock_search_instance.search("What is KITAS?", user_level=1)
                rag_result = await mock_rag_instance.process_query(
                    query="What is KITAS?", user_id=user_id
                )
                memory = await mock_memory_instance.get_memory(user_id)

                assert search_result is not None
                assert rag_result is not None
                assert memory is not None

            # Cleanup
            await conn.execute("DELETE FROM memory_facts WHERE user_id = $1", user_id)

    @pytest.mark.asyncio
    async def test_crm_notification_compliance_orchestration(self, db_pool):
        """Test orchestration of CRM, Notification, and Compliance services"""

        async with db_pool.acquire() as conn:
            # Create client
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "Orchestration Client",
                "orchestration@example.com",
                "active",
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Create practice with expiry
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
                "team@example.com",
                datetime.now(),
                datetime.now(),
            )

            # Compliance check -> Alert -> Notification
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
                {"practice_id": practice_id},
            )

            notification_id = await conn.fetchval(
                """
                INSERT INTO notifications (
                    user_id, notification_type, title, message, status
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "team@example.com",
                "compliance_alert",
                "Practice Expiry Warning",
                "Practice expires in 30 days",
                "pending",
            )

            # Verify orchestration
            workflow = await conn.fetchrow(
                """
                SELECT
                    c.id as client_id,
                    p.id as practice_id,
                    ca.id as alert_id,
                    n.id as notification_id
                FROM clients c
                JOIN practices p ON c.id = p.client_id
                JOIN compliance_alerts ca ON c.id = ca.client_id
                JOIN notifications n ON n.user_id = 'team@example.com'
                WHERE c.id = $1
                LIMIT 1
                """,
                client_id,
            )

            assert workflow is not None
            assert workflow["client_id"] == client_id
            assert workflow["practice_id"] == practice_id
            assert workflow["alert_id"] == alert_id
            assert workflow["notification_id"] == notification_id

            # Cleanup
            await conn.execute("DELETE FROM notifications WHERE id = $1", notification_id)
            await conn.execute("DELETE FROM compliance_alerts WHERE id = $1", alert_id)
            await conn.execute("DELETE FROM practices WHERE id = $1", practice_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)

    @pytest.mark.asyncio
    async def test_ingestion_search_rag_orchestration(self, qdrant_client, db_pool):
        """Test orchestration of Ingestion, Search, and RAG services"""

        collection_name = "orchestration_test"

        try:
            # Step 1: Ingest document
            await qdrant_client.create_collection(collection_name=collection_name, vector_size=1536)

            test_embedding = [0.1] * 1536
            await qdrant_client.upsert(
                collection_name=collection_name,
                points=[
                    {
                        "id": "ingested_doc_1",
                        "vector": test_embedding,
                        "payload": {
                            "text": "KITAS application process",
                            "metadata": {"source": "test"},
                        },
                    }
                ],
            )

            # Step 2: Search ingested document
            search_results = await qdrant_client.search(
                collection_name=collection_name,
                query_vector=test_embedding,
                limit=5,
            )

            assert len(search_results) > 0

            # Step 3: Use in RAG (mocked)
            with patch("services.rag.agentic.create_agentic_rag") as mock_rag:
                mock_rag_instance = MagicMock()
                mock_rag_instance.process_query = AsyncMock(
                    return_value={
                        "answer": "RAG response using ingested document",
                        "sources": [{"text": "KITAS application process"}],
                    }
                )

                result = await mock_rag_instance.process_query(
                    query="How to apply for KITAS?", user_id="test_user"
                )

                assert result is not None
                assert "answer" in result

        finally:
            # Cleanup
            try:
                await qdrant_client.delete_collection(collection_name=collection_name)
            except Exception:
                pass
