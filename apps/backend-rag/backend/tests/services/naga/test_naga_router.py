"""
Tests for the Naga research engine FastAPI router.

Verifies:
- Router has correct routes with correct methods/paths
- POST /api/naga/research accepts valid request and returns 200 placeholder
- GET /api/naga/claims/search returns empty list for v1
- GET /api/naga/session/{session_id} returns 404 for unknown session
"""

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.app.routers.naga import router


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with only the naga router mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRouterStructure:
    """Verify the router object has the correct routes."""

    def test_router_has_correct_routes(self) -> None:
        """Router must expose exactly 3 routes with correct methods and paths."""
        routes = [r for r in router.routes if isinstance(r, APIRoute)]
        route_map: dict[str, set[str]] = {}
        for r in routes:
            route_map[r.path] = r.methods

        assert "/api/naga/research" in route_map
        assert "POST" in route_map["/api/naga/research"]

        assert "/api/naga/session/{session_id}" in route_map
        assert "GET" in route_map["/api/naga/session/{session_id}"]

        assert "/api/naga/claims/search" in route_map
        assert "GET" in route_map["/api/naga/claims/search"]

    def test_router_prefix_and_tags(self) -> None:
        """Router must use /api/naga prefix and naga tag."""
        assert router.prefix == "/api/naga"
        assert "naga" in router.tags


class TestResearchEndpoint:
    """POST /api/naga/research"""

    def test_research_endpoint_accepts_request(self, client: TestClient) -> None:
        """Valid request body returns 200 with completed or failed status."""
        resp = client.post(
            "/api/naga/research",
            json={"query": "What are the latest visa regulations?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")
        assert "session_id" in data

    def test_research_endpoint_with_all_fields(self, client: TestClient) -> None:
        """Request with all optional fields returns 200."""
        resp = client.post(
            "/api/naga/research",
            json={
                "query": "PT PMA requirements",
                "tier": "flash",
                "domain": "indonesia",
                "mode": "oneshot",
                "trusted_mode": True,
                "channel": "telegram",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "failed")

    def test_research_endpoint_missing_query(self, client: TestClient) -> None:
        """Request without required query field returns 422."""
        resp = client.post("/api/naga/research", json={})
        assert resp.status_code == 422


class TestSessionEndpoint:
    """GET /api/naga/session/{session_id}"""

    def test_session_not_found(self, client: TestClient) -> None:
        """Unknown session_id returns 404."""
        resp = client.get("/api/naga/session/nonexistent-session-id")
        assert resp.status_code == 404
        data = resp.json()
        assert "not found" in data["detail"].lower()


class TestClaimsSearchEndpoint:
    """GET /api/naga/claims/search"""

    def test_claims_search_returns_empty(self, client: TestClient) -> None:
        """V1 stub returns empty claims list."""
        resp = client.get("/api/naga/claims/search", params={"q": "visa"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["claims"] == []
        assert data["total"] == 0

    def test_claims_search_with_filters(self, client: TestClient) -> None:
        """Claims search accepts optional filter params."""
        resp = client.get(
            "/api/naga/claims/search",
            params={
                "q": "tax",
                "domain": "tax",
                "verification": "verified",
                "limit": 50,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["claims"] == []
        assert data["total"] == 0

    def test_claims_search_missing_query(self, client: TestClient) -> None:
        """Claims search without required q param returns 422."""
        resp = client.get("/api/naga/claims/search")
        assert resp.status_code == 422

    def test_claims_search_limit_capped(self, client: TestClient) -> None:
        """Limit above 100 is rejected by validation."""
        resp = client.get(
            "/api/naga/claims/search",
            params={"q": "test", "limit": 200},
        )
        assert resp.status_code == 422
