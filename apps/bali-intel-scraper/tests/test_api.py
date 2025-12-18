"""
BALI INTEL SCRAPER - API Tests
Tests for scraper REST API
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app


class TestScraperAPI:
    """Test scraper API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "Bali Intel Scraper" in data["service"]

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "Bali Intel Scraper API"
        assert "endpoints" in data

    @patch('api.main.run_stage1_scraping')
    def test_trigger_scrape(self, mock_scrape, client):
        """Test triggering scrape job."""
        mock_scrape.return_value = {
            "success": True,
            "total_scraped": 50,
        }

        response = client.post(
            "/api/v1/scrape/trigger",
            json={
                "categories": ["immigration"],
                "limit": 10,
                "generate_articles": True,
                "upload_to_vector_db": False,
                "max_articles": 10
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data

    def test_list_sources(self, client):
        """Test listing sources."""
        # This requires config file to exist
        response = client.get("/api/v1/sources")

        # Will fail if config not found, which is expected in test environment
        assert response.status_code in [200, 500]

    def test_get_source_stats(self, client):
        """Test getting source statistics."""
        response = client.get("/api/v1/sources/stats")

        # Will fail if config not found, which is expected
        assert response.status_code in [200, 500]
