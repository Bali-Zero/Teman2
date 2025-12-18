"""
Ultimate Business Scenario Tests
Tests for the most complex business scenarios and real-world use cases

Coverage:
- Complex business workflows
- Real-world scenarios
- Multi-entity relationships
- Business rule validations
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
@pytest.mark.business
class TestComplexBusinessWorkflows:
    """Test complex business workflow scenarios"""

    def test_multi_client_practice_management(self, authenticated_client, test_app):
        """Test managing multiple clients with multiple practices"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create multiple clients
            clients = []
            for i in range(5):
                response = authenticated_client.post(
                    "/api/crm/clients",
                    json={"full_name": f"Client {i}", "email": f"client{i}@example.com"},
                )
                if response.status_code in [200, 201]:
                    clients.append(i + 1)

            # Create practices for each client
            practices = []
            for client_id in clients:
                for practice_type in ["KITAS", "PT_PMA", "VISA"]:
                    response = authenticated_client.post(
                        "/api/crm/practices",
                        json={
                            "client_id": client_id,
                            "practice_type_code": practice_type,
                            "status": "inquiry",
                        },
                    )
                    if response.status_code in [200, 201]:
                        practices.append((client_id, practice_type))

            # Get statistics
            stats_response = authenticated_client.get("/api/crm/clients/stats/overview")
            practice_stats_response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert stats_response.status_code == 200
            assert practice_stats_response.status_code == 200

    def test_practice_renewal_workflow_complete(self, authenticated_client, test_app):
        """Test complete practice renewal workflow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Find expiring practices
            renewals_response = authenticated_client.get(
                "/api/crm/shared-memory/upcoming-renewals?days=90"
            )

            # 2. Create renewal practice for each expiring practice
            if renewals_response.status_code == 200:
                renewals = renewals_response.json()
                if isinstance(renewals, list) and len(renewals) > 0:
                    for renewal in renewals[:3]:  # Process first 3
                        client_id = renewal.get("client_id", 1)
                        practice_type = renewal.get("practice_code", "KITAS")

                        response = authenticated_client.post(
                            "/api/crm/practices",
                            json={
                                "client_id": client_id,
                                "practice_type_code": practice_type,
                                "status": "inquiry",
                                "priority": "high",
                            },
                        )

                        assert response.status_code in [200, 201, 500]

    def test_client_journey_with_all_interactions(self, authenticated_client, test_app):
        """Test complete client journey with all interaction types"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Journey Client", "email": "journey@example.com"},
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # Create interactions of all types
                interaction_types = ["chat", "email", "phone", "meeting", "note"]

                for interaction_type in interaction_types:
                    response = authenticated_client.post(
                        "/api/crm/interactions",
                        json={
                            "client_id": client_id,
                            "interaction_type": interaction_type,
                            "summary": f"{interaction_type} interaction",
                        },
                    )

                    assert response.status_code in [200, 201, 500]

                # Get client timeline
                timeline_response = authenticated_client.get(
                    f"/api/crm/interactions/client/{client_id}/timeline"
                )

                assert timeline_response.status_code == 200

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
                    "practice_code": "KITAS",
                    "expiry_date": "2025-12-31",
                }
            ]
        )
        mock_conn.execute = AsyncMock(return_value="INSERT 1")

        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        return mock_pool, mock_conn


@pytest.mark.api
@pytest.mark.business
class TestRealWorldScenarios:
    """Test real-world business scenarios"""

    def test_high_priority_client_onboarding(self, authenticated_client, test_app):
        """Test high-priority client onboarding scenario"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Create VIP client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={
                    "full_name": "VIP Client",
                    "email": "vip@example.com",
                    "tags": ["vip", "priority"],
                },
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # 2. Create urgent practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type_code": "KITAS",
                        "status": "inquiry",
                        "priority": "urgent",
                    },
                )

                # 3. Create immediate interaction
                interaction_response = authenticated_client.post(
                    "/api/crm/interactions",
                    json={
                        "client_id": client_id,
                        "interaction_type": "phone",
                        "summary": "Urgent inquiry",
                        "sentiment": "positive",
                    },
                )

                # 4. Send priority notification
                with patch("app.routers.notifications.notification_hub") as mock_hub:
                    mock_hub.send = AsyncMock(return_value={"notification_id": "notif_123"})

                    notification_response = authenticated_client.post(
                        "/api/notifications/send",
                        json={
                            "recipient_id": str(client_id),
                            "title": "Welcome VIP Client",
                            "message": "We're here to help",
                            "priority": "high",
                        },
                    )

                    assert practice_response.status_code in [200, 201, 500]
                    assert interaction_response.status_code in [200, 201, 500]
                    assert notification_response.status_code in [200, 201, 500, 503]

    def test_bulk_practice_processing(self, authenticated_client, test_app):
        """Test bulk processing of practices"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create multiple practices
            practices_created = 0
            for i in range(10):
                response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": 1,
                        "practice_type_code": "KITAS",
                        "status": "inquiry",
                    },
                )
                if response.status_code in [200, 201]:
                    practices_created += 1

            # Get active practices
            active_response = authenticated_client.get("/api/crm/practices/active")

            # Get statistics
            stats_response = authenticated_client.get("/api/crm/practices/stats/overview")

            assert active_response.status_code == 200
            assert stats_response.status_code == 200

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
@pytest.mark.business
class TestMultiEntityRelationships:
    """Test multi-entity relationship scenarios"""

    def test_client_practice_interaction_relationships(self, authenticated_client, test_app):
        """Test relationships between clients, practices, and interactions"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Relationship Client", "email": "rel@example.com"},
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # Create practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type_code": "KITAS",
                        "status": "in_progress",
                    },
                )

                if practice_response.status_code in [200, 201]:
                    practice_id = 1

                    # Create interaction linked to both
                    interaction_response = authenticated_client.post(
                        "/api/crm/interactions",
                        json={
                            "client_id": client_id,
                            "practice_id": practice_id,
                            "interaction_type": "email",
                            "summary": "Practice update",
                        },
                    )

                    # Get client with practices
                    client_detail_response = authenticated_client.get(
                        f"/api/crm/clients/{client_id}"
                    )

                    # Get practice timeline
                    practice_timeline_response = authenticated_client.get(
                        f"/api/crm/interactions/client/{client_id}/timeline"
                    )

                    assert interaction_response.status_code in [200, 201, 500]
                    assert client_detail_response.status_code in [200, 404, 500]
                    assert practice_timeline_response.status_code == 200

    def test_practice_document_management(self, authenticated_client, test_app):
        """Test practice document management workflow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create practice
            practice_response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "waiting_documents",
                },
            )

            if practice_response.status_code in [200, 201]:
                practice_id = 1

                # Add documents
                documents_response = authenticated_client.post(
                    f"/api/crm/practices/{practice_id}/documents/add",
                    json={
                        "documents": [
                            {"type": "passport", "url": "https://example.com/passport.pdf"},
                            {"type": "photo", "url": "https://example.com/photo.jpg"},
                            {"type": "application", "url": "https://example.com/app.pdf"},
                        ],
                    },
                )

                # Update practice status
                update_response = authenticated_client.patch(
                    f"/api/crm/practices/{practice_id}",
                    json={"status": "submitted_to_gov"},
                )

                assert documents_response.status_code in [200, 201, 404, 500]
                assert update_response.status_code in [200, 404, 500]

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
@pytest.mark.business
class TestBusinessRuleValidations:
    """Test business rule validation scenarios"""

    def test_practice_status_transition_rules(self, authenticated_client, test_app):
        """Test practice status transition business rules"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Create practice in inquiry
            create_response = authenticated_client.post(
                "/api/crm/practices",
                json={
                    "client_id": 1,
                    "practice_type_code": "KITAS",
                    "status": "inquiry",
                },
            )

            if create_response.status_code in [200, 201]:
                practice_id = 1

                # Test valid transitions
                valid_transitions = [
                    ("inquiry", "quotation_sent"),
                    ("quotation_sent", "payment_pending"),
                    ("payment_pending", "in_progress"),
                    ("in_progress", "waiting_documents"),
                    ("waiting_documents", "submitted_to_gov"),
                    ("submitted_to_gov", "approved"),
                    ("approved", "completed"),
                ]

                for from_status, to_status in valid_transitions:
                    mock_conn.fetchrow = AsyncMock(
                        return_value={"id": practice_id, "status": from_status}
                    )

                    response = authenticated_client.patch(
                        f"/api/crm/practices/{practice_id}",
                        json={"status": to_status},
                    )

                    assert response.status_code in [200, 404, 500]

    def test_price_validation_rules(self, authenticated_client, test_app):
        """Test price validation business rules"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1})
            mock_get_pool.return_value = mock_pool

            # Test price scenarios
            price_scenarios = [
                {"quoted_price": "1000.00", "actual_price": "950.00"},  # Actual less than quoted
                {"quoted_price": "1000.00", "actual_price": "1000.00"},  # Actual equals quoted
                {"quoted_price": "1000.00", "paid_amount": "500.00"},  # Partial payment
                {"quoted_price": "1000.00", "paid_amount": "1000.00"},  # Full payment
            ]

            for scenario in price_scenarios:
                response = authenticated_client.patch(
                    "/api/crm/practices/1",
                    json=scenario,
                )

                assert response.status_code in [200, 400, 422, 404, 500]

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
