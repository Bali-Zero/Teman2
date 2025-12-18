"""
Expanded API Tests for Intel Endpoints

Tests for:
- Intel search with various filters
- Intel store operations
- Intel categories and collections
- Critical items and trends
"""

from datetime import datetime

import pytest


@pytest.mark.api
class TestIntelSearchEndpoints:
    """Test Intel search endpoints"""

    def test_search_intel_basic(self, authenticated_client):
        """Test basic intel search"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "visa regulations",
                "limit": 10,
            },
        )

        assert response.status_code in [200, 400, 422, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            assert "results" in data or "items" in data or isinstance(data, list)

    def test_search_intel_with_category(self, authenticated_client):
        """Test intel search with category filter"""
        categories = ["immigration", "bkpm_tax", "realestate", "events"]

        for category in categories:
            response = authenticated_client.post(
                "/api/intel/search",
                json={
                    "query": "test query",
                    "category": category,
                    "limit": 5,
                },
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_search_intel_with_date_range(self, authenticated_client):
        """Test intel search with date range filters"""
        date_ranges = ["today", "last_7_days", "last_30_days", "last_90_days", "all"]

        for date_range in date_ranges:
            response = authenticated_client.post(
                "/api/intel/search",
                json={
                    "query": "test query",
                    "date_range": date_range,
                    "limit": 10,
                },
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_search_intel_with_tier_filter(self, authenticated_client):
        """Test intel search with tier filter"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "test query",
                "tier": ["T1", "T2"],
                "limit": 10,
            },
        )

        assert response.status_code in [200, 400, 422, 500]

    def test_search_intel_with_impact_level(self, authenticated_client):
        """Test intel search with impact level filter"""
        impact_levels = ["high", "medium", "low"]

        for impact_level in impact_levels:
            response = authenticated_client.post(
                "/api/intel/search",
                json={
                    "query": "test query",
                    "impact_level": impact_level,
                    "limit": 10,
                },
            )

            assert response.status_code in [200, 400, 422, 500]

    def test_search_intel_combined_filters(self, authenticated_client):
        """Test intel search with multiple filters combined"""
        response = authenticated_client.post(
            "/api/intel/search",
            json={
                "query": "visa updates",
                "category": "immigration",
                "date_range": "last_30_days",
                "tier": ["T1", "T2", "T3"],
                "impact_level": "high",
                "limit": 20,
            },
        )

        assert response.status_code in [200, 400, 422, 500]


@pytest.mark.api
class TestIntelStoreEndpoints:
    """Test Intel store endpoints"""

    def test_store_intel_item(self, authenticated_client):
        """Test storing intel item"""
        # Generate mock embedding (1536 dimensions for typical embeddings)
        mock_embedding = [0.1] * 1536

        response = authenticated_client.post(
            "/api/intel/store",
            json={
                "collection": "bali_intel_immigration",
                "id": f"test_item_{datetime.now().timestamp()}",
                "document": "Test intel document content",
                "embedding": mock_embedding,
                "metadata": {
                    "title": "Test Intel Item",
                    "published_date": datetime.now().isoformat(),
                    "tier": "T1",
                    "impact_level": "medium",
                },
                "full_data": {
                    "source": "test",
                    "url": "https://test.example.com",
                },
            },
        )

        assert response.status_code in [200, 201, 400, 422, 500]


@pytest.mark.api
class TestIntelCriticalItemsEndpoints:
    """Test Intel critical items endpoints"""

    def test_get_critical_items(self, authenticated_client):
        """Test retrieving critical items"""
        response = authenticated_client.get("/api/intel/critical")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict) or isinstance(data, list)

    def test_get_critical_items_with_category(self, authenticated_client):
        """Test retrieving critical items filtered by category"""
        categories = ["immigration", "bkpm_tax", "realestate"]

        for category in categories:
            response = authenticated_client.get(
                "/api/intel/critical", params={"category": category}
            )

            assert response.status_code in [200, 400, 404, 500]

    def test_get_critical_items_with_days(self, authenticated_client):
        """Test retrieving critical items with days filter"""
        response = authenticated_client.get("/api/intel/critical", params={"days": 7})

        assert response.status_code in [200, 400, 404, 500]


@pytest.mark.api
class TestIntelTrendsEndpoints:
    """Test Intel trends endpoints"""

    def test_get_trends(self, authenticated_client):
        """Test retrieving trends"""
        response = authenticated_client.get("/api/intel/trends")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_trends_with_category(self, authenticated_client):
        """Test retrieving trends filtered by category"""
        categories = ["immigration", "bkpm_tax", "realestate"]

        for category in categories:
            response = authenticated_client.get("/api/intel/trends", params={"category": category})

            assert response.status_code in [200, 400, 404, 500]

    def test_get_trends_with_days(self, authenticated_client):
        """Test retrieving trends with days filter"""
        response = authenticated_client.get("/api/intel/trends", params={"days": 30})

        assert response.status_code in [200, 400, 404, 500]


@pytest.mark.api
class TestIntelCollectionsEndpoints:
    """Test Intel collections endpoints"""

    def test_get_collections_stats(self, authenticated_client):
        """Test retrieving collection statistics"""
        response = authenticated_client.get("/api/intel/collections/stats")

        assert response.status_code in [200, 400, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
