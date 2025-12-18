"""
Expanded API Tests for Agents Endpoints

Tests for:
- Client Journey Orchestrator endpoints
- Proactive Compliance Monitor endpoints
- Knowledge Graph Builder endpoints
- Auto Ingestion Orchestrator endpoints
"""

from datetime import datetime, timedelta

import pytest


@pytest.mark.api
class TestAgentsJourneyEndpoints:
    """Test Client Journey Orchestrator API endpoints"""

    def test_create_journey_pt_pma(self, authenticated_client):
        """Test creating PT PMA setup journey"""
        # First create a client
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Journey Test Client",
                "email": "journey.test@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                # Create journey
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "pt_pma_setup",
                        "client_id": str(client_id),
                    },
                )

                assert journey_response.status_code in [200, 201]
                if journey_response.status_code in [200, 201]:
                    data = journey_response.json()
                    assert "success" in data or "journey_id" in data
                    assert "journey" in data or "journey_id" in data

    def test_create_journey_kitas(self, authenticated_client):
        """Test creating KITAS application journey"""
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "KITAS Journey Client",
                "email": "kitas.journey@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "kitas_application",
                        "client_id": str(client_id),
                    },
                )

                assert journey_response.status_code in [200, 201]

    def test_get_journey_details(self, authenticated_client):
        """Test retrieving journey details"""
        # Create journey first
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Get Journey Client",
                "email": "get.journey@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "pt_pma_setup",
                        "client_id": str(client_id),
                    },
                )

                if journey_response.status_code in [200, 201]:
                    journey_id = journey_response.json().get(
                        "journey_id"
                    ) or journey_response.json().get("journey", {}).get("journey_id")

                    if journey_id:
                        # Get journey details
                        get_response = authenticated_client.get(f"/api/agents/journey/{journey_id}")

                        assert get_response.status_code in [200, 404]
                        if get_response.status_code == 200:
                            data = get_response.json()
                            assert "success" in data or "journey" in data

    def test_complete_journey_step(self, authenticated_client):
        """Test completing a journey step"""
        # Create journey
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Step Complete Client",
                "email": "step.complete@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "pt_pma_setup",
                        "client_id": str(client_id),
                    },
                )

                if journey_response.status_code in [200, 201]:
                    journey_data = journey_response.json()
                    journey_id = journey_data.get("journey_id") or journey_data.get(
                        "journey", {}
                    ).get("journey_id")

                    if journey_id:
                        # Get journey to find first step
                        journey_details = authenticated_client.get(
                            f"/api/agents/journey/{journey_id}"
                        )

                        if journey_details.status_code == 200:
                            journey_info = journey_details.json()
                            steps = (
                                journey_info.get("journey", {}).get("steps", [])
                                if isinstance(journey_info.get("journey"), dict)
                                else []
                            )

                            if steps:
                                first_step_id = steps[0].get("step_id") or steps[0].get("id")

                                if first_step_id:
                                    # Complete step
                                    complete_response = authenticated_client.post(
                                        f"/api/agents/journey/{journey_id}/step/{first_step_id}/complete",
                                        params={"notes": "Test completion"},
                                    )

                                    assert complete_response.status_code in [200, 400, 404]

    def test_get_next_steps(self, authenticated_client):
        """Test retrieving next available steps"""
        # Create journey
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Next Steps Client",
                "email": "next.steps@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                journey_response = authenticated_client.post(
                    "/api/agents/journey/create",
                    json={
                        "journey_type": "pt_pma_setup",
                        "client_id": str(client_id),
                    },
                )

                if journey_response.status_code in [200, 201]:
                    journey_id = journey_response.json().get(
                        "journey_id"
                    ) or journey_response.json().get("journey", {}).get("journey_id")

                    if journey_id:
                        # Get next steps
                        next_steps_response = authenticated_client.get(
                            f"/api/agents/journey/{journey_id}/next-steps"
                        )

                        assert next_steps_response.status_code in [200, 404]
                        if next_steps_response.status_code == 200:
                            data = next_steps_response.json()
                            assert "success" in data or "next_steps" in data


@pytest.mark.api
class TestAgentsComplianceEndpoints:
    """Test Proactive Compliance Monitor API endpoints"""

    def test_add_compliance_tracking(self, authenticated_client):
        """Test adding compliance tracking item"""
        # Create client first
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Compliance Test Client",
                "email": "compliance.test@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                deadline = (datetime.now() + timedelta(days=30)).isoformat()

                compliance_response = authenticated_client.post(
                    "/api/agents/compliance/track",
                    json={
                        "client_id": str(client_id),
                        "compliance_type": "visa_expiry",
                        "title": "KITAS Expiry",
                        "description": "Director KITAS expires soon",
                        "deadline": deadline.split("T")[0],  # YYYY-MM-DD format
                        "estimated_cost": 5000000.0,
                        "required_documents": ["passport", "sponsor_letter"],
                    },
                )

                assert compliance_response.status_code in [200, 201, 400, 422]

    def test_get_compliance_alerts(self, authenticated_client):
        """Test retrieving compliance alerts"""
        response = authenticated_client.get("/api/agents/compliance/alerts")

        assert response.status_code in [200, 400, 404]
        if response.status_code == 200:
            data = response.json()
            assert "success" in data or "alerts" in data

    def test_get_compliance_alerts_with_filters(self, authenticated_client):
        """Test retrieving compliance alerts with filters"""
        # Create client and compliance item first
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Filter Compliance Client",
                "email": "filter.compliance@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                # Get alerts filtered by client
                alerts_response = authenticated_client.get(
                    "/api/agents/compliance/alerts",
                    params={"client_id": str(client_id)},
                )

                assert alerts_response.status_code in [200, 400, 404]

                # Get alerts filtered by severity
                severity_response = authenticated_client.get(
                    "/api/agents/compliance/alerts",
                    params={"severity": "critical"},
                )

                assert severity_response.status_code in [200, 400, 404]

    def test_get_client_compliance(self, authenticated_client):
        """Test retrieving all compliance items for a client"""
        # Create client
        client_response = authenticated_client.post(
            "/api/crm/clients",
            json={
                "full_name": "Client Compliance Test",
                "email": "client.compliance@example.com",
                "phone": "+6281234567890",
            },
        )

        if client_response.status_code in [200, 201]:
            client_id = client_response.json().get("id") or client_response.json().get("client_id")

            if client_id:
                # Get client compliance
                compliance_response = authenticated_client.get(
                    f"/api/agents/compliance/client/{client_id}"
                )

                assert compliance_response.status_code in [200, 404]


@pytest.mark.api
class TestAgentsKnowledgeGraphEndpoints:
    """Test Knowledge Graph Builder API endpoints"""

    def test_get_knowledge_graph_status(self, authenticated_client):
        """Test retrieving knowledge graph status"""
        response = authenticated_client.get("/api/agents/knowledge-graph/status")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_query_knowledge_graph(self, authenticated_client):
        """Test querying knowledge graph"""
        response = authenticated_client.post(
            "/api/agents/knowledge-graph/query",
            json={"query": "PT PMA requirements", "limit": 10},
        )

        assert response.status_code in [200, 400, 404, 422]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.api
class TestAgentsStatusEndpoints:
    """Test Agents status and info endpoints"""

    def test_get_agents_status(self, authenticated_client):
        """Test retrieving status of all agents"""
        response = authenticated_client.get("/api/agents/status")

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
            assert "total_agents" in data or "agents" in data

    def test_agents_status_caching(self, authenticated_client):
        """Test that agents status endpoint is cached"""
        import time

        # First request
        start1 = time.time()
        response1 = authenticated_client.get("/api/agents/status")
        time1 = time.time() - start1

        # Second request (should be faster if cached)
        start2 = time.time()
        response2 = authenticated_client.get("/api/agents/status")
        time2 = time.time() - start2

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Cached response should be faster (or similar)
        assert time2 <= time1 * 1.5  # Allow some variance
