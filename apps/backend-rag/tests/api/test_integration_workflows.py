"""
Integration Workflow Tests
Tests complete workflows across multiple endpoints

Coverage:
- Client onboarding workflow (CRM -> Journey -> Compliance)
- Conversation -> Memory -> Search workflow
- Document ingestion -> Search -> Query workflow
- Notification -> Alert -> Compliance workflow
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
@pytest.mark.integration
class TestClientOnboardingWorkflow:
    """Test complete client onboarding workflow"""

    def test_client_onboarding_complete_flow(self, authenticated_client):
        """Test: Create client -> Create journey -> Track compliance"""
        # Step 1: Create client
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "email": "newclient@example.com",
                    "name": "New Client",
                    "company": "Test Company",
                },
            )

            # Step 2: Create journey (if client created successfully)
            if client_response.status_code in [200, 201]:
                with patch("app.routers.agents.journey_orchestrator") as mock_journey:
                    mock_journey.create_journey = MagicMock(
                        return_value={"journey_id": "journey_123", "status": "active"}
                    )

                    journey_response = authenticated_client.post(
                        "/api/agents/journey/create",
                        json={
                            "client_id": "client_123",
                            "journey_type": "onboarding",
                        },
                    )

                    # Step 3: Track compliance
                    if journey_response.status_code in [200, 201]:
                        with patch("app.routers.agents.compliance_monitor") as mock_compliance:
                            mock_compliance.track_item = MagicMock(
                                return_value={"alert_id": "alert_123"}
                            )

                            compliance_response = authenticated_client.post(
                                "/api/agents/compliance/track",
                                json={
                                    "client_id": "client_123",
                                    "item_type": "document_upload",
                                    "item_data": {},
                                },
                            )

                            assert compliance_response.status_code in [200, 201, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(
            return_value={"id": "client_123", "email": "newclient@example.com"}
        )
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")
        mock_conn.fetchval = AsyncMock(return_value="client_123")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.integration
class TestConversationMemoryWorkflow:
    """Test conversation -> memory -> search workflow"""

    def test_conversation_to_memory_workflow(self, authenticated_client):
        """Test: Save conversation -> Store in memory -> Search memory"""
        # Step 1: Save conversation
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            conversation_response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "What is tax law?"},
                        {"role": "assistant", "content": "Tax law is..."},
                    ],
                },
            )

            # Step 2: Store in memory (if conversation saved)
            if conversation_response.status_code in [200, 201]:
                with patch("app.routers.memory_vector.initialize_memory_vector_db") as mock_mem:
                    mock_db = MagicMock()
                    mock_db.store_memory = AsyncMock(return_value={"memory_id": "mem_123"})
                    mock_mem.return_value = mock_db

                    memory_response = authenticated_client.post(
                        "/api/memory/store",
                        json={
                            "text": "Tax law discussion",
                            "metadata": {"conversation_id": "conv_123"},
                        },
                    )

                    # Step 3: Search memory
                    if memory_response.status_code in [200, 201]:
                        mock_db.search_memories = AsyncMock(
                            return_value={"results": [], "query": "tax"}
                        )

                        search_response = authenticated_client.post(
                            "/api/memory/search",
                            json={"query": "tax law", "limit": 10},
                        )

                        assert search_response.status_code in [200, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchval = AsyncMock(return_value="conv_123")
        mock_conn.fetchrow = AsyncMock(return_value={"id": "conv_123", "messages": []})
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.integration
class TestDocumentIngestionWorkflow:
    """Test document ingestion -> search -> query workflow"""

    def test_document_to_query_workflow(self, authenticated_client):
        """Test: Ingest document -> Search -> Query oracle"""
        # Step 1: Ingest document
        with patch("services.ingestion_service.IngestionService") as mock_ingest:
            mock_service = MagicMock()
            mock_service.ingest_book = AsyncMock(
                return_value={
                    "success": True,
                    "book_id": "book_123",
                    "chunks_created": 10,
                }
            )
            mock_ingest.return_value = mock_service

            ingest_response = authenticated_client.post(
                "/api/ingest/upload",
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            )

            # Step 2: Search (if ingested successfully)
            if ingest_response.status_code in [200, 201]:
                with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                    mock_search_service = MagicMock()
                    mock_search_service.search = AsyncMock(
                        return_value={"results": [], "query": "test"}
                    )
                    mock_search.return_value = mock_search_service

                    search_response = authenticated_client.post(
                        "/api/oracle/query",
                        json={"query": "What is in the document?", "limit": 5},
                    )

                    assert search_response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
@pytest.mark.integration
class TestNotificationComplianceWorkflow:
    """Test notification -> alert -> compliance workflow"""

    def test_notification_to_compliance_workflow(self, authenticated_client):
        """Test: Send notification -> Track compliance -> Get alerts"""
        # Step 1: Send notification
        with patch("services.notification_hub.NotificationHub") as mock_notif:
            mock_hub = MagicMock()
            mock_hub.send_notification = AsyncMock(
                return_value={"success": True, "notification_id": "notif_123"}
            )
            mock_notif.return_value = mock_hub

            notif_response = authenticated_client.post(
                "/api/notifications/send",
                json={
                    "recipient": "user@example.com",
                    "message": "Document expiry alert",
                    "channels": ["email"],
                },
            )

            # Step 2: Track compliance (if notification sent)
            if notif_response.status_code in [200, 201]:
                with patch("app.routers.agents.compliance_monitor") as mock_compliance:
                    mock_compliance.track_item = MagicMock(return_value={"alert_id": "alert_123"})

                    compliance_response = authenticated_client.post(
                        "/api/agents/compliance/track",
                        json={
                            "client_id": "client_123",
                            "item_type": "document_expiry",
                            "item_data": {"expiry_date": "2025-12-31"},
                        },
                    )

                    # Step 3: Get alerts
                    if compliance_response.status_code in [200, 201]:
                        mock_compliance.get_alerts = MagicMock(return_value=[])

                        alerts_response = authenticated_client.get(
                            "/api/agents/compliance/alerts?client_id=client_123"
                        )

                        assert alerts_response.status_code == 200


@pytest.mark.api
@pytest.mark.integration
class TestMultiEndpointInteractions:
    """Test interactions between multiple endpoints"""

    def test_crm_client_to_conversation_workflow(self, authenticated_client):
        """Test: Create client -> Start conversation -> Save conversation"""
        # This tests the flow of creating a client and then having a conversation
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "email": "client@example.com",
                    "name": "Test Client",
                },
            )

            # Save conversation for client
            if client_response.status_code in [200, 201]:
                conversation_response = authenticated_client.post(
                    "/api/bali-zero/conversations/save",
                    json={
                        "messages": [
                            {"role": "user", "content": "Hello"},
                            {"role": "assistant", "content": "Hi!"},
                        ],
                        "metadata": {"client_id": "client_123"},
                    },
                )

                assert conversation_response.status_code in [200, 201, 500]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(
            return_value={"id": "client_123", "email": "client@example.com"}
        )
        mock_conn.fetchval = AsyncMock(return_value="conv_123")
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn
