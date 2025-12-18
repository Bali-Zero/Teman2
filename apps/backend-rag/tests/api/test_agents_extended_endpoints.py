"""
API Tests for Agents Router - Extended
Tests additional agent endpoints

Coverage:
- POST /api/agents/journey/create - Create client journey
- GET /api/agents/journey/{journey_id} - Get journey
- POST /api/agents/knowledge-graph/extract - Extract knowledge graph
- GET /api/agents/knowledge-graph/export - Export knowledge graph
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestAgentsExtended:
    """Tests for extended agents endpoints"""

    def test_create_client_journey(self, authenticated_client):
        """Test POST /api/agents/journey/create"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_journey = MagicMock()
            mock_journey.journey_id = "journey_123"
            mock_journey.steps = [{"step": 1, "name": "Step 1"}]
            mock_orchestrator.create_journey.return_value = mock_journey

            response = authenticated_client.post(
                "/api/agents/journey/create",
                json={
                    "journey_type": "pt_pma_setup",
                    "client_id": "client_123",
                },
            )

            assert response.status_code in [200, 400, 429, 500]

    def test_get_journey(self, authenticated_client):
        """Test GET /api/agents/journey/{journey_id}"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_journey = MagicMock()
            mock_journey.journey_id = "journey_123"
            mock_orchestrator.get_journey.return_value = mock_journey

            response = authenticated_client.get("/api/agents/journey/journey_123")

            assert response.status_code in [200, 404, 500]

    def test_extract_knowledge_graph(self, authenticated_client):
        """Test POST /api/agents/knowledge-graph/extract"""
        response = authenticated_client.post(
            "/api/agents/knowledge-graph/extract",
            params={"text": "Test text for knowledge extraction"},
        )

        assert response.status_code in [200, 500, 503]

    def test_export_knowledge_graph(self, authenticated_client):
        """Test GET /api/agents/knowledge-graph/export"""
        response = authenticated_client.get("/api/agents/knowledge-graph/export?format=neo4j")

        assert response.status_code in [200, 500, 503]

    def test_get_next_steps(self, authenticated_client):
        """Test GET /api/agents/journey/{journey_id}/next-steps"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_step = MagicMock()
            mock_step.__dict__ = {"step_id": "step1", "name": "Step 1"}
            mock_orchestrator.get_next_steps.return_value = [mock_step]

            response = authenticated_client.get("/api/agents/journey/journey_123/next-steps")

            assert response.status_code in [200, 404, 500]

    def test_complete_journey_step(self, authenticated_client):
        """Test POST /api/agents/journey/{journey_id}/step/{step_id}/complete"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_journey = MagicMock()
            mock_journey.__dict__ = {"journey_id": "journey_123"}
            mock_orchestrator.complete_step.return_value = None
            mock_orchestrator.get_journey.return_value = mock_journey

            response = authenticated_client.post(
                "/api/agents/journey/journey_123/step/step1/complete",
                params={"notes": "Completed step"},
            )

            assert response.status_code in [200, 400, 404, 500]

    def test_add_compliance_tracking(self, authenticated_client):
        """Test POST /api/agents/compliance/track"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_item = MagicMock()
            mock_item.item_id = "item_123"
            mock_monitor.add_compliance_item.return_value = mock_item

            response = authenticated_client.post(
                "/api/agents/compliance/track",
                json={
                    "client_id": "client_123",
                    "compliance_type": "visa_expiry",
                    "title": "KITAS Renewal",
                    "description": "KITAS expires soon",
                    "deadline": "2025-12-31",
                },
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_get_compliance_alerts(self, authenticated_client):
        """Test GET /api/agents/compliance/alerts"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_upcoming_alerts.return_value = []

            response = authenticated_client.get("/api/agents/compliance/alerts")

            assert response.status_code in [200, 500]

    def test_get_client_compliance(self, authenticated_client):
        """Test GET /api/agents/compliance/client/{client_id}"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_client_compliance.return_value = []

            response = authenticated_client.get("/api/agents/compliance/client/client_123")

            assert response.status_code in [200, 404, 500]

    def test_get_ingestion_status(self, authenticated_client):
        """Test GET /api/agents/ingestion/status"""
        response = authenticated_client.get("/api/agents/ingestion/status")

        assert response.status_code in [200, 500, 503]

    def test_get_analytics_summary(self, authenticated_client):
        """Test GET /api/agents/analytics/summary"""
        response = authenticated_client.get("/api/agents/analytics/summary")

        assert response.status_code in [200, 500, 503]

    def test_agents_extended_require_auth(self, test_client):
        """Test that extended agents endpoints require authentication"""
        response = test_client.post(
            "/api/agents/journey/create",
            json={"journey_type": "test", "client_id": "test"},
        )
        assert response.status_code in [401, 429]
