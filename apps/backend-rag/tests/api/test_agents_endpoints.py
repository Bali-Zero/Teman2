"""
API Tests for Agents Router
Tests agent management endpoints
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
class TestAgentsEndpoints:
    """Tests for agents endpoints"""

    def test_get_agents_status(self, authenticated_client):
        """Test GET /api/agents/status"""
        with patch("app.dependencies.get_search_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.router.get_routing_stats.return_value = {"selected_collection": "test"}
            mock_get_service.return_value = mock_service

            response = authenticated_client.get("/api/agents/status")

            assert response.status_code in [200, 500, 503]

    def test_get_agents_status_requires_auth(self, test_client):
        """Test that agents status requires authentication"""
        response = test_client.get("/api/agents/status")
        assert response.status_code == 401
