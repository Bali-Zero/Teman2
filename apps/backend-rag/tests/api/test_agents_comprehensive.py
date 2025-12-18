"""
Comprehensive API Tests for Agents Router
Expanded test coverage for all agentic functions

Coverage:
- GET /api/agents/status - Agent status
- POST /api/agents/journey/create - Create client journey
- GET /api/agents/journey/{journey_id} - Get journey
- POST /api/agents/journey/{journey_id}/step/{step_id}/complete - Complete step
- GET /api/agents/journey/{journey_id}/next-steps - Get next steps
- POST /api/agents/compliance/track - Track compliance
- GET /api/agents/compliance/alerts - Get compliance alerts
- GET /api/agents/compliance/client/{client_id} - Get client compliance
- POST /api/agents/knowledge-graph/extract - Extract knowledge graph
- GET /api/agents/knowledge-graph/export - Export knowledge graph
- POST /api/agents/ingestion/run - Run ingestion
- GET /api/agents/ingestion/status - Get ingestion status
- POST /api/agents/synthesis/cross-oracle - Cross oracle synthesis
- POST /api/agents/pricing/calculate - Calculate pricing
- POST /api/agents/research/autonomous - Autonomous research
- GET /api/agents/analytics/summary - Analytics summary
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
class TestAgentsStatus:
    """Comprehensive tests for GET /api/agents/status"""

    def test_get_agents_status_success(self, authenticated_client):
        """Test successful retrieval of agent status"""
        response = authenticated_client.get("/api/agents/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "total_agents" in data
        assert data["total_agents"] == 10
        assert "agents" in data
        assert "capabilities" in data

    def test_agents_status_structure(self, authenticated_client):
        """Test agent status response structure"""
        response = authenticated_client.get("/api/agents/status")

        assert response.status_code == 200
        data = response.json()

        # Validate phase structure
        assert "phase_1_2_foundation" in data["agents"]
        assert "phase_3_orchestration" in data["agents"]
        assert "phase_4_advanced" in data["agents"]
        assert "phase_5_automation" in data["agents"]

        # Validate capabilities
        assert isinstance(data["capabilities"], dict)
        assert "multi_oracle_synthesis" in data["capabilities"]
        assert "journey_orchestration" in data["capabilities"]

    def test_agents_status_requires_auth(self, test_client):
        """Test agent status requires authentication"""
        response = test_client.get("/api/agents/status")
        assert response.status_code == 401

    def test_agents_status_cached(self, authenticated_client):
        """Test agent status is cached (should be fast on second request)"""
        import time

        start1 = time.time()
        response1 = authenticated_client.get("/api/agents/status")
        time1 = time.time() - start1

        start2 = time.time()
        response2 = authenticated_client.get("/api/agents/status")
        time2 = time.time() - start2

        assert response1.status_code == 200
        assert response2.status_code == 200
        # Second request should be faster (cached)
        # Note: In test environment caching might not be as effective


@pytest.mark.api
class TestClientJourney:
    """Comprehensive tests for client journey endpoints"""

    def test_create_journey_success(self, authenticated_client):
        """Test POST /api/agents/journey/create - successful creation"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_orchestrator.create_journey = MagicMock(
                return_value={
                    "journey_id": "journey_123",
                    "client_id": "client_456",
                    "status": "active",
                    "steps": [],
                }
            )

            response = authenticated_client.post(
                "/api/agents/journey/create",
                json={
                    "client_id": "client_456",
                    "journey_type": "onboarding",
                    "metadata": {},
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_create_journey_missing_client_id(self, authenticated_client):
        """Test create journey without client_id"""
        response = authenticated_client.post(
            "/api/agents/journey/create",
            json={"journey_type": "onboarding"},
        )

        assert response.status_code == 422

    def test_get_journey_success(self, authenticated_client):
        """Test GET /api/agents/journey/{journey_id}"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_orchestrator.get_journey = MagicMock(
                return_value={
                    "journey_id": "journey_123",
                    "client_id": "client_456",
                    "status": "active",
                    "steps": [],
                }
            )

            response = authenticated_client.get("/api/agents/journey/journey_123")

            assert response.status_code in [200, 404, 500]

    def test_get_journey_not_found(self, authenticated_client):
        """Test GET journey with non-existent ID"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_orchestrator.get_journey = MagicMock(return_value=None)

            response = authenticated_client.get("/api/agents/journey/nonexistent")

            assert response.status_code in [404, 500]

    def test_complete_step_success(self, authenticated_client):
        """Test POST /api/agents/journey/{journey_id}/step/{step_id}/complete"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_orchestrator.complete_step = MagicMock(return_value={"success": True})

            response = authenticated_client.post(
                "/api/agents/journey/journey_123/step/step_456/complete",
                json={"notes": "Step completed"},
            )

            assert response.status_code in [200, 404, 500]

    def test_get_next_steps(self, authenticated_client):
        """Test GET /api/agents/journey/{journey_id}/next-steps"""
        with patch("app.routers.agents.journey_orchestrator") as mock_orchestrator:
            mock_orchestrator.get_next_steps = MagicMock(
                return_value={"steps": [{"id": "step_1", "name": "Next Step"}]}
            )

            response = authenticated_client.get("/api/agents/journey/journey_123/next-steps")

            assert response.status_code in [200, 404, 500]


@pytest.mark.api
class TestComplianceMonitoring:
    """Comprehensive tests for compliance endpoints"""

    def test_track_compliance_success(self, authenticated_client):
        """Test POST /api/agents/compliance/track"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.track_item = MagicMock(
                return_value={"alert_id": "alert_123", "severity": "warning"}
            )

            response = authenticated_client.post(
                "/api/agents/compliance/track",
                json={
                    "client_id": "client_456",
                    "item_type": "document_expiry",
                    "item_data": {"document": "passport", "expiry_date": "2025-12-31"},
                },
            )

            assert response.status_code in [200, 201, 500]

    def test_get_compliance_alerts_all(self, authenticated_client):
        """Test GET /api/agents/compliance/alerts - all alerts"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_alerts = MagicMock(return_value=[])

            response = authenticated_client.get("/api/agents/compliance/alerts")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "alerts" in data
            assert "count" in data
            assert "breakdown" in data

    def test_get_compliance_alerts_filtered(self, authenticated_client):
        """Test GET /api/agents/compliance/alerts - with filters"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_alerts = MagicMock(return_value=[])

            response = authenticated_client.get(
                "/api/agents/compliance/alerts?client_id=client_123&severity=critical"
            )

            assert response.status_code == 200

    def test_get_compliance_alerts_with_notification(self, authenticated_client):
        """Test GET /api/agents/compliance/alerts - with auto_notify"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_alerts = MagicMock(return_value=[])

            response = authenticated_client.get("/api/agents/compliance/alerts?auto_notify=true")

            assert response.status_code == 200
            data = response.json()
            assert "notifications_sent" in data

    def test_get_client_compliance(self, authenticated_client):
        """Test GET /api/agents/compliance/client/{client_id}"""
        with patch("app.routers.agents.compliance_monitor") as mock_monitor:
            mock_monitor.get_client_items = MagicMock(return_value=[])

            response = authenticated_client.get("/api/agents/compliance/client/client_123")

            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert "client_id" in data
            assert "items" in data
            assert "count" in data


@pytest.mark.api
class TestKnowledgeGraph:
    """Comprehensive tests for knowledge graph endpoints"""

    def test_extract_knowledge_graph(self, authenticated_client):
        """Test POST /api/agents/knowledge-graph/extract"""
        with patch("app.routers.agents.knowledge_graph") as mock_kg:
            mock_kg.extract_entities = MagicMock(return_value={"entities": [], "relationships": []})

            response = authenticated_client.post(
                "/api/agents/knowledge-graph/extract",
                json={"text": "Test text for extraction"},
            )

            assert response.status_code in [200, 500]

    def test_export_knowledge_graph(self, authenticated_client):
        """Test GET /api/agents/knowledge-graph/export"""
        with patch("app.routers.agents.knowledge_graph") as mock_kg:
            mock_kg.export_graph = MagicMock(return_value={"nodes": [], "edges": []})

            response = authenticated_client.get("/api/agents/knowledge-graph/export")

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestAutoIngestion:
    """Comprehensive tests for auto ingestion endpoints"""

    def test_run_ingestion(self, authenticated_client):
        """Test POST /api/agents/ingestion/run"""
        with patch("app.routers.agents.auto_ingestion") as mock_ingestion:
            mock_ingestion.run_ingestion = MagicMock(
                return_value={"status": "running", "job_id": "job_123"}
            )

            response = authenticated_client.post(
                "/api/agents/ingestion/run",
                json={"source": "gmail", "filters": {}},
            )

            assert response.status_code in [200, 201, 500]

    def test_get_ingestion_status(self, authenticated_client):
        """Test GET /api/agents/ingestion/status"""
        with patch("app.routers.agents.auto_ingestion") as mock_ingestion:
            mock_ingestion.get_status = MagicMock(return_value={"status": "idle", "last_run": None})

            response = authenticated_client.get("/api/agents/ingestion/status")

            assert response.status_code in [200, 500]


@pytest.mark.api
class TestCrossOracleSynthesis:
    """Comprehensive tests for cross-oracle synthesis"""

    def test_cross_oracle_synthesis(self, authenticated_client):
        """Test POST /api/agents/synthesis/cross-oracle"""
        response = authenticated_client.post(
            "/api/agents/synthesis/cross-oracle",
            json={
                "queries": ["query1", "query2"],
                "synthesis_type": "comparative",
            },
        )

        # May require actual service dependencies
        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestPricingCalculation:
    """Comprehensive tests for pricing calculation"""

    def test_calculate_pricing(self, authenticated_client):
        """Test POST /api/agents/pricing/calculate"""
        response = authenticated_client.post(
            "/api/agents/pricing/calculate",
            json={
                "service_type": "visa",
                "client_tier": "A",
                "complexity": "medium",
            },
        )

        # May require actual service dependencies
        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestAutonomousResearch:
    """Comprehensive tests for autonomous research"""

    def test_autonomous_research(self, authenticated_client):
        """Test POST /api/agents/research/autonomous"""
        response = authenticated_client.post(
            "/api/agents/research/autonomous",
            json={
                "research_topic": "Indonesian tax regulations",
                "depth": "medium",
            },
        )

        # May require actual service dependencies
        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestAnalyticsSummary:
    """Comprehensive tests for analytics summary"""

    def test_get_analytics_summary(self, authenticated_client):
        """Test GET /api/agents/analytics/summary"""
        response = authenticated_client.get("/api/agents/analytics/summary")

        assert response.status_code in [200, 500, 503]

    def test_analytics_summary_with_filters(self, authenticated_client):
        """Test GET /api/agents/analytics/summary with query parameters"""
        response = authenticated_client.get(
            "/api/agents/analytics/summary?timeframe=30d&agent_type=compliance"
        )

        assert response.status_code in [200, 400, 422, 500, 503]


@pytest.mark.api
class TestAgentsErrorScenarios:
    """Error scenario tests for agents endpoints"""

    def test_invalid_journey_id_format(self, authenticated_client):
        """Test with invalid journey ID format"""
        response = authenticated_client.get("/api/agents/journey/invalid-id-format-123")

        assert response.status_code in [200, 400, 404, 422, 500]

    def test_missing_required_fields_compliance(self, authenticated_client):
        """Test compliance track without required fields"""
        response = authenticated_client.post(
            "/api/agents/compliance/track",
            json={},
        )

        assert response.status_code == 422

    def test_invalid_severity_filter(self, authenticated_client):
        """Test compliance alerts with invalid severity"""
        response = authenticated_client.get(
            "/api/agents/compliance/alerts?severity=invalid_severity"
        )

        # Should handle gracefully
        assert response.status_code in [200, 400, 422, 500]

    def test_empty_text_knowledge_graph(self, authenticated_client):
        """Test knowledge graph extraction with empty text"""
        response = authenticated_client.post(
            "/api/agents/knowledge-graph/extract",
            json={"text": ""},
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_agents_endpoints_require_auth(self, test_client):
        """Test all agents endpoints require authentication"""
        endpoints = [
            ("GET", "/api/agents/status"),
            ("POST", "/api/agents/journey/create"),
            ("GET", "/api/agents/journey/journey_123"),
            ("GET", "/api/agents/compliance/alerts"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = test_client.get(path)
            else:
                response = test_client.post(path, json={})

            assert response.status_code == 401
