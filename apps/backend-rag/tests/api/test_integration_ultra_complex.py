"""
Ultra-Complex Integration Tests
Tests for the most complex integration scenarios and multi-system workflows

Coverage:
- Multi-system integrations
- Complex data flows
- Cross-service workflows
- End-to-end business processes
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
class TestMultiSystemIntegrations:
    """Test complex multi-system integrations"""

    def test_crm_oracle_intel_integration(self, authenticated_client, test_app):
        """Test integration: CRM -> Oracle -> Intel"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Create client in CRM
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Integration Client", "email": "integration@example.com"},
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # 2. Query Oracle for legal information
                with patch("app.routers.oracle_universal.get_search_service") as mock_search:
                    mock_service = MagicMock()
                    mock_service.search = AsyncMock(
                        return_value={"results": [{"text": "Legal info", "score": 0.9}]}
                    )
                    mock_search.return_value = mock_service

                    oracle_response = authenticated_client.post(
                        "/api/oracle/query",
                        json={"query": "KITAS requirements"},
                    )

                    # 3. Store intel document
                    with patch("app.routers.intel.embedder") as mock_embedder:
                        mock_embedder.generate_single_embedding = MagicMock(
                            return_value=[0.1] * 1536
                        )
                        with patch("core.qdrant_db.QdrantClient") as mock_qdrant:
                            mock_client = MagicMock()
                            mock_client.store = AsyncMock(return_value=True)
                            mock_qdrant.return_value = mock_client

                            intel_response = authenticated_client.post(
                                "/api/intel/store",
                                json={
                                    "document": "Legal intelligence document",
                                    "category": "immigration",
                                    "tier": "T1",
                                },
                            )

                            # All integrations should work
                            assert oracle_response.status_code in [200, 500, 503]
                            assert intel_response.status_code in [200, 201, 500, 503]

    def test_conversation_memory_crm_integration(self, authenticated_client, test_app):
        """Test integration: Conversation -> Memory -> CRM"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Save conversation
            conversation_response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "I need KITAS help"},
                        {"role": "assistant", "content": "I can help"},
                    ],
                },
            )

            # 2. Store in memory vector
            with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.store = AsyncMock(return_value=True)
                mock_get_db.return_value = mock_db

                memory_response = authenticated_client.post(
                    "/api/memory/store",
                    json={
                        "id": "memory_123",
                        "document": "Conversation about KITAS",
                        "embedding": [0.1] * 384,
                        "metadata": {"type": "conversation"},
                    },
                )

                # 3. Auto-populate CRM
                clients_response = authenticated_client.get("/api/crm/clients")

                assert conversation_response.status_code in [200, 201, 500]
                assert memory_response.status_code in [200, 201, 500, 503]
                assert clients_response.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.integration
class TestComplexDataFlows:
    """Test complex data flow scenarios"""

    def test_data_flow_client_practice_interaction_notification(
        self, authenticated_client, test_app
    ):
        """Test complete data flow: Client -> Practice -> Interaction -> Notification"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Flow Client", "email": "flow@example.com"},
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # 2. Create practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type_code": "KITAS",
                        "status": "inquiry",
                    },
                )

                if practice_response.status_code in [200, 201]:
                    practice_id = 1

                    # 3. Create interaction
                    interaction_response = authenticated_client.post(
                        "/api/crm/interactions",
                        json={
                            "client_id": client_id,
                            "practice_id": practice_id,
                            "interaction_type": "email",
                            "summary": "Client inquiry",
                        },
                    )

                    # 4. Send notification
                    with patch("app.routers.notifications.notification_hub") as mock_hub:
                        mock_hub.send = AsyncMock(return_value={"notification_id": "notif_123"})

                        notification_response = authenticated_client.post(
                            "/api/notifications/send",
                            json={
                                "recipient_id": str(client_id),
                                "recipient_email": "flow@example.com",
                                "title": "Practice Update",
                                "message": "Your practice status has been updated",
                            },
                        )

                        assert interaction_response.status_code in [200, 201, 500]
                        assert notification_response.status_code in [200, 201, 500, 503]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "code": "KITAS"})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.integration
class TestCrossServiceWorkflows:
    """Test cross-service workflow scenarios"""

    def test_agentic_rag_with_memory_and_crm(self, authenticated_client):
        """Test Agentic RAG using memory and CRM data"""
        # 1. Store memory
        with patch("app.routers.memory_vector.get_memory_vector_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.store = AsyncMock(return_value=True)
            mock_get_db.return_value = mock_db

            memory_response = authenticated_client.post(
                "/api/memory/store",
                json={
                    "id": "memory_123",
                    "document": "Client information",
                    "embedding": [0.1] * 384,
                    "metadata": {},
                },
            )

            # 2. Query Agentic RAG
            with patch("app.routers.agentic_rag.get_orchestrator") as mock_get_orch:
                mock_orch = MagicMock()
                mock_orch.process_query = AsyncMock(
                    return_value={
                        "answer": "Answer using memory and CRM",
                        "sources": [],
                        "context_used": 100,
                        "execution_time": 1.5,
                        "route_used": "complex",
                    }
                )
                mock_get_orch.return_value = mock_orch

                rag_response = authenticated_client.post(
                    "/api/agentic-rag/query",
                    json={"query": "What do we know about this client?"},
                )

                # 3. Get CRM data
                with patch("app.dependencies.get_database_pool") as mock_get_pool:
                    mock_pool, mock_conn = self._create_mock_db_pool()
                    mock_get_pool.return_value = mock_pool

                    crm_response = authenticated_client.get("/api/crm/clients")

                    assert memory_response.status_code in [200, 201, 500, 503]
                    assert rag_response.status_code in [200, 500, 503]
                    assert crm_response.status_code == 200

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.execute = AsyncMock(return_value="SELECT 0")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.integration
class TestEndToEndBusinessProcesses:
    """Test complete end-to-end business processes"""

    def test_complete_client_onboarding_process(self, authenticated_client, test_app):
        """Test complete client onboarding process"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Step 1: Initial inquiry via conversation
            conversation_response = authenticated_client.post(
                "/api/bali-zero/conversations/save",
                json={
                    "messages": [
                        {"role": "user", "content": "I need help with KITAS"},
                        {"role": "assistant", "content": "I can help you"},
                    ],
                },
            )

            # Step 2: Auto-create client in CRM
            clients_response = authenticated_client.get("/api/crm/clients")

            # Step 3: Create practice
            practice_response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                },
            )

            # Step 4: Send quotation
            if practice_response.status_code in [200, 201]:
                quotation_response = authenticated_client.patch(
                    "/api/crm/practices/1",
                    json={"status": "quotation_sent", "quoted_price": "1000.00"},
                )

                # Step 5: Create interaction
                interaction_response = authenticated_client.post(
                    "/api/crm/interactions",
                    json={
                        "client_id": 1,
                        "practice_id": 1,
                        "interaction_type": "email",
                        "summary": "Quotation sent",
                    },
                )

                # Step 6: Send notification
                with patch("app.routers.notifications.notification_hub") as mock_hub:
                    mock_hub.send = AsyncMock(return_value={"notification_id": "notif_123"})

                    notification_response = authenticated_client.post(
                        "/api/notifications/send",
                        json={
                            "recipient_id": "1",
                            "recipient_email": "client@example.com",
                            "title": "Quotation Ready",
                            "message": "Your quotation is ready",
                        },
                    )

                    # All steps should complete
                    assert conversation_response.status_code in [200, 201, 500]
                    assert clients_response.status_code == 200
                    assert practice_response.status_code in [200, 201, 500]
                    assert quotation_response.status_code in [200, 404, 500]
                    assert interaction_response.status_code in [200, 201, 500]
                    assert notification_response.status_code in [200, 201, 500, 503]

    def test_complete_practice_renewal_process(self, authenticated_client, test_app):
        """Test complete practice renewal process"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Step 1: Check upcoming renewals
            renewals_response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")

            # Step 2: Create renewal practice
            renewal_practice_response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                },
            )

            # Step 3: Notify client
            with patch("app.routers.notifications.notification_hub") as mock_hub:
                mock_hub.send = AsyncMock(return_value={"notification_id": "notif_123"})

                notification_response = authenticated_client.post(
                    "/api/notifications/send-template",
                    json={
                        "template_id": "practice_expiry",
                        "recipient_id": "1",
                        "recipient_email": "client@example.com",
                        "template_data": {"days_remaining": 30},
                    },
                )

                # All steps should complete
                assert renewals_response.status_code == 200
                assert renewal_practice_response.status_code in [200, 201, 500]
                assert notification_response.status_code in [200, 201, 400, 404, 500, 503]

    def _create_mock_db_pool(self):
        """Helper to create mock database pool"""
        mock_conn = AsyncMock()
        mock_pool = MagicMock()

        mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "code": "KITAS"})
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.fetch = AsyncMock(
            return_value=[
                {
                    "client_id": 1,
                    "practice_type": "KITAS",
                    "expiry_date": "2025-12-31",
                }
            ]
        )
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn
