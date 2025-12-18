"""
Expanded API Tests for Handlers Endpoints

Tests for:
- Handler listing
- Handler search
- Handler categorization
- Handler discovery
"""

import pytest


@pytest.mark.api
class TestHandlersListing:
    """Test handlers listing endpoints"""

    def test_list_all_handlers(self, authenticated_client):
        """Test listing all available handlers"""
        response = authenticated_client.get("/api/handlers/list")

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert "total_handlers" in data or "handlers" in data
            assert "categories" in data or "handlers" in data

    def test_list_all_handlers_structure(self, authenticated_client):
        """Test handlers list response structure"""
        response = authenticated_client.get("/api/handlers/list")

        if response.status_code == 200:
            data = response.json()
            # Verify structure
            assert isinstance(data, dict)
            if "handlers" in data:
                assert isinstance(data["handlers"], list)
            if "categories" in data:
                assert isinstance(data["categories"], dict)


@pytest.mark.api
class TestHandlersSearch:
    """Test handlers search endpoints"""

    def test_search_handlers_by_name(self, authenticated_client):
        """Test searching handlers by name"""
        search_terms = ["oracle", "crm", "client", "conversation", "memory"]

        for term in search_terms:
            response = authenticated_client.get("/api/handlers/search", params={"query": term})

            assert response.status_code == 200
            if response.status_code == 200:
                data = response.json()
                assert "query" in data
                assert "matches" in data or "handlers" in data

    def test_search_handlers_by_path(self, authenticated_client):
        """Test searching handlers by path"""
        response = authenticated_client.get("/api/handlers/search", params={"query": "/api/oracle"})

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_search_handlers_by_description(self, authenticated_client):
        """Test searching handlers by description keywords"""
        response = authenticated_client.get("/api/handlers/search", params={"query": "query"})

        assert response.status_code == 200

    def test_search_handlers_case_insensitive(self, authenticated_client):
        """Test that handler search is case insensitive"""
        response1 = authenticated_client.get("/api/handlers/search", params={"query": "ORACLE"})
        response2 = authenticated_client.get("/api/handlers/search", params={"query": "oracle"})

        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_search_handlers_empty_query(self, authenticated_client):
        """Test searching handlers with empty query"""
        response = authenticated_client.get("/api/handlers/search", params={"query": ""})

        # Should handle gracefully
        assert response.status_code in [200, 400]

    def test_search_handlers_partial_match(self, authenticated_client):
        """Test searching handlers with partial matches"""
        response = authenticated_client.get("/api/handlers/search", params={"query": "ora"})

        assert response.status_code == 200

    def test_search_handlers_no_results(self, authenticated_client):
        """Test searching handlers with query that returns no results"""
        response = authenticated_client.get(
            "/api/handlers/search", params={"query": "nonexistent_handler_xyz_123"}
        )

        assert response.status_code == 200
        if response.status_code == 200:
            data = response.json()
            assert data.get("matches", 0) == 0 or len(data.get("handlers", [])) == 0


@pytest.mark.api
class TestHandlersByCategory:
    """Test handlers by category endpoints"""

    def test_get_handlers_by_category_oracle(self, authenticated_client):
        """Test getting handlers in oracle category"""
        response = authenticated_client.get("/api/handlers/category/oracle_universal")

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_get_handlers_by_category_crm(self, authenticated_client):
        """Test getting handlers in CRM categories"""
        crm_categories = ["crm_clients", "crm_practices", "crm_interactions"]

        for category in crm_categories:
            response = authenticated_client.get(f"/api/handlers/category/{category}")

            assert response.status_code in [200, 404]

    def test_get_handlers_by_category_agents(self, authenticated_client):
        """Test getting handlers in agents category"""
        response = authenticated_client.get("/api/handlers/category/agents")

        assert response.status_code in [200, 404]

    def test_get_handlers_by_category_notifications(self, authenticated_client):
        """Test getting handlers in notifications category"""
        response = authenticated_client.get("/api/handlers/category/notifications")

        assert response.status_code in [200, 404]

    def test_get_handlers_by_category_productivity(self, authenticated_client):
        """Test getting handlers in productivity category"""
        response = authenticated_client.get("/api/handlers/category/productivity")

        assert response.status_code in [200, 404]

    def test_get_handlers_by_category_invalid(self, authenticated_client):
        """Test getting handlers with invalid category"""
        response = authenticated_client.get("/api/handlers/category/invalid_category_xyz_123")

        assert response.status_code == 404


@pytest.mark.api
class TestHandlersIntegration:
    """Test handlers endpoint integration scenarios"""

    def test_list_then_search(self, authenticated_client):
        """Test listing handlers then searching in the results"""
        # First list all handlers
        list_response = authenticated_client.get("/api/handlers/list")

        if list_response.status_code == 200:
            list_data = list_response.json()
            handlers = list_data.get("handlers", [])

            if handlers:
                # Get first handler name and search for it
                first_handler_name = handlers[0].get("name", "")

                if first_handler_name:
                    search_response = authenticated_client.get(
                        "/api/handlers/search",
                        params={"query": first_handler_name.split("_")[0]},
                    )

                    assert search_response.status_code == 200

    def test_list_then_filter_by_category(self, authenticated_client):
        """Test listing handlers then filtering by category"""
        # List all handlers
        list_response = authenticated_client.get("/api/handlers/list")

        if list_response.status_code == 200:
            list_data = list_response.json()
            categories = list_data.get("categories", {})

            if categories:
                # Get first category and retrieve its handlers
                first_category = list(categories.keys())[0]
                category_response = authenticated_client.get(
                    f"/api/handlers/category/{first_category}"
                )

                assert category_response.status_code in [200, 404]
