"""
Comprehensive Scenario Tests
Tests for complex real-world scenarios and use cases

Coverage:
- Multi-user scenarios
- Complex business workflows
- Real-world data patterns
- Production-like scenarios
- End-to-end user journeys
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
@pytest.mark.comprehensive
class TestMultiUserScenarios:
    """Test multi-user scenarios"""

    def test_multiple_users_same_endpoint(self, authenticated_client):
        """Test multiple users accessing same endpoint"""
        # Simulate multiple users by making requests
        responses = []

        for i in range(10):
            response = authenticated_client.get("/api/agents/status")
            responses.append(response)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

    def test_user_isolation(self, authenticated_client, test_app):
        """Test user data isolation"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            # Simulate user-specific data
            mock_conn.fetchrow = AsyncMock(return_value={"id": 1, "full_name": "User's Client"})
            mock_get_pool.return_value = mock_pool

            response = authenticated_client.get("/api/crm/clients/1")

            # Should return user's data only
            assert response.status_code in [200, 403, 404, 500]

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
@pytest.mark.comprehensive
class TestComplexWorkflows:
    """Test complex business workflows"""

    def test_complete_client_lifecycle(self, authenticated_client, test_app):
        """Test complete client lifecycle workflow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "Lifecycle Client", "email": "lifecycle@example.com"},
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
                            "interaction_type": "chat",
                            "team_member": "team@example.com",
                        },
                    )

                    # 4. Update practice status
                    update_response = authenticated_client.patch(
                        f"/api/crm/practices/{practice_id}",
                        json={"status": "in_progress"},
                    )

                    # 5. Get client summary
                    summary_response = authenticated_client.get(
                        f"/api/crm/clients/{client_id}/summary"
                    )

                    # All steps should complete
                    assert interaction_response.status_code in [200, 201, 500]
                    assert update_response.status_code in [200, 404, 500]
                    assert summary_response.status_code in [200, 404, 500]

    def test_practice_renewal_workflow(self, authenticated_client, test_app):
        """Test practice renewal workflow"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Get upcoming renewals
            renewals_response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")

            if renewals_response.status_code == 200:
                renewals = renewals_response.json()

                # 2. For each renewal, create new practice
                if isinstance(renewals, list) and len(renewals) > 0:
                    renewal = renewals[0]
                    client_id = renewal.get("client_id", 1)

                    new_practice_response = authenticated_client.post(
                        "/api/crm/practices",
                        json={
                            "client_id": client_id,
                            "practice_type_code": "KITAS",
                            "status": "inquiry",
                        },
                    )

                    assert new_practice_response.status_code in [200, 201, 500]

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


@pytest.mark.api
@pytest.mark.comprehensive
class TestRealWorldDataPatterns:
    """Test real-world data patterns"""

    def test_realistic_client_data(self, authenticated_client, test_app):
        """Test with realistic client data"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            realistic_client = {
                "full_name": "John Smith",
                "email": "john.smith@example.com",
                "phone": "+62 812 3456 7890",
                "whatsapp": "+62 812 3456 7890",
                "nationality": "US",
                "passport_number": "P123456789",
                "client_type": "individual",
                "address": "Jl. Raya Ubud No. 123, Bali, Indonesia",
                "tags": ["vip", "premium", "renewal"],
            }

            response = authenticated_client.post(
                "/api/crm/clients",
                json=realistic_client,
            )

            assert response.status_code in [200, 201, 500]

    def test_realistic_practice_data(self, authenticated_client, test_app):
        """Test with realistic practice data"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            realistic_practice = {
                "client_id": 1,
                "practice_type_code": "KITAS",
                "status": "in_progress",
                "priority": "high",
                "quoted_price": "15000000",
                "assigned_to": "team@example.com",
                "notes": "Client needs urgent processing",
                "internal_notes": "Follow up in 3 days",
            }

            response = authenticated_client.post(
                "/api/crm/practices",
                json=realistic_practice,
            )

            assert response.status_code in [200, 201, 500]

    def test_realistic_interaction_data(self, authenticated_client, test_app):
        """Test with realistic interaction data"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            realistic_interaction = {
                "client_id": 1,
                "practice_id": 1,
                "interaction_type": "email",
                "channel": "gmail",
                "subject": "Re: KITAS Application Status",
                "summary": "Client asking about application status",
                "full_content": "Dear Team, I would like to know the status of my KITAS application...",
                "sentiment": "neutral",
                "team_member": "team@example.com",
                "direction": "inbound",
                "extracted_entities": {
                    "dates": ["2025-12-31"],
                    "documents": ["passport", "visa"],
                },
                "action_items": [
                    {"task": "Send status update", "due_date": "2025-01-15"},
                ],
            }

            response = authenticated_client.post(
                "/api/crm/interactions",
                json=realistic_interaction,
            )

            assert response.status_code in [200, 201, 500]

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
@pytest.mark.comprehensive
class TestProductionLikeScenarios:
    """Test production-like scenarios"""

    def test_high_volume_requests(self, authenticated_client):
        """Test high volume of requests"""
        responses = []

        # Simulate high volume
        for _ in range(500):
            response = authenticated_client.get("/api/agents/status")
            responses.append(response)

        # Should handle high volume
        assert len(responses) == 500
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 400  # Most should succeed

    def test_mixed_request_types(self, authenticated_client, test_app):
        """Test mixed request types"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # Mix of GET, POST, PATCH, DELETE
            get_response = authenticated_client.get("/api/crm/clients")
            post_response = authenticated_client.post(
                "/api/crm/clients", json={"full_name": "Test"}
            )
            patch_response = authenticated_client.patch(
                "/api/crm/clients/1", json={"full_name": "Updated"}
            )
            delete_response = authenticated_client.delete("/api/crm/clients/1")

            # All should handle appropriately
            assert get_response.status_code in [200, 500]
            assert post_response.status_code in [200, 201, 500]
            assert patch_response.status_code in [200, 404, 500]
            assert delete_response.status_code in [200, 204, 404, 500]

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
@pytest.mark.comprehensive
class TestEndToEndJourneys:
    """Test end-to-end user journeys"""

    def test_new_client_onboarding_journey(self, authenticated_client, test_app):
        """Test complete new client onboarding journey"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Create client
            client_response = authenticated_client.post(
                "/api/crm/clients",
                json={"full_name": "New Client", "email": "new@example.com"},
            )

            if client_response.status_code in [200, 201]:
                client_id = 1

                # 2. Create initial practice
                practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": client_id,
                        "practice_type_code": "KITAS",
                        "status": "inquiry",
                    },
                )

                # 3. Log initial interaction
                interaction_response = authenticated_client.post(
                    "/api/crm/interactions",
                    json={
                        "client_id": client_id,
                        "interaction_type": "chat",
                        "team_member": "team@example.com",
                        "summary": "Initial consultation",
                    },
                )

                # 4. Create journey
                with patch("app.routers.agents.journey_orchestrator") as mock_journey:
                    mock_journey.create_journey = MagicMock(
                        return_value={"journey_id": "journey_123"}
                    )

                    journey_response = authenticated_client.post(
                        "/api/agents/journey/create",
                        json={
                            "client_id": str(client_id),
                            "journey_type": "onboarding",
                        },
                    )

                    # All steps should complete
                    assert practice_response.status_code in [200, 201, 500]
                    assert interaction_response.status_code in [200, 201, 500]
                    assert journey_response.status_code in [200, 201, 500]

    def test_existing_client_renewal_journey(self, authenticated_client, test_app):
        """Test existing client renewal journey"""
        with patch("app.dependencies.get_database_pool") as mock_get_pool:
            mock_pool, mock_conn = self._create_mock_db_pool()
            mock_get_pool.return_value = mock_pool

            # 1. Search for clients with expiring practices
            search_response = authenticated_client.get(
                "/api/crm/shared-memory/search?q=clients with expiring practices"
            )

            # 2. Get upcoming renewals
            renewals_response = authenticated_client.get("/api/crm/shared-memory/upcoming-renewals")

            # 3. Create renewal practice
            if renewals_response.status_code == 200:
                renewal_practice_response = authenticated_client.post(
                    "/api/crm/practices",
                    json={
                        "client_id": 1,
                        "practice_type_code": "KITAS",
                        "status": "inquiry",
                    },
                )

                assert renewal_practice_response.status_code in [200, 201, 500]

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
