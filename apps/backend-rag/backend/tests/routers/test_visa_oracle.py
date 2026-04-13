"""
Tests for Visa Oracle Router

Covers:
- Router exists and exposes expected routes
- Request model validation (RecommendRequest, ChatRequest, HandoffRequest)
- Response model shapes
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.dependencies import get_database_pool
from backend.app.routers.visa_oracle import (
    ChatRequest,
    HandoffRequest,
    RecommendRequest,
    router,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with visa_oracle router mounted."""
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    # Override db_pool dependency with a mock for testing
    application.dependency_overrides[get_database_pool] = lambda: MagicMock()
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """TestClient for the visa oracle router."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Router structure tests
# ---------------------------------------------------------------------------


class TestRouterStructure:
    """Verify the router is correctly configured."""

    def test_router_prefix(self) -> None:
        assert router.prefix == "/visa-oracle"

    def test_router_tags(self) -> None:
        assert router.tags == ["visa-oracle"]

    def test_router_has_recommend_route(self) -> None:
        paths = [route.path for route in router.routes]
        assert any("recommend" in p for p in paths)

    def test_router_has_chat_route(self) -> None:
        paths = [route.path for route in router.routes]
        assert any("chat" in p for p in paths)

    def test_router_has_handoff_route(self) -> None:
        paths = [route.path for route in router.routes]
        assert any("handoff" in p for p in paths)

    def test_router_has_visa_types_route(self) -> None:
        paths = [route.path for route in router.routes]
        assert any("visa-types" in p for p in paths)

    def test_router_has_visa_type_detail_route(self) -> None:
        paths = [route.path for route in router.routes]
        assert any("{code}" in p for p in paths)


# ---------------------------------------------------------------------------
# 2. Request model validation tests
# ---------------------------------------------------------------------------


class TestRecommendRequest:
    """Validate RecommendRequest Pydantic model."""

    def test_valid_request(self) -> None:
        req = RecommendRequest(
            nationality="British",
            purpose="work",
            duration="long",
            family="yes",
        )
        assert req.nationality == "British"
        assert req.purpose == "work"
        assert req.duration == "long"
        assert req.family == "yes"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            RecommendRequest(nationality="British", purpose="work", duration="long")

    def test_family_as_no(self) -> None:
        req = RecommendRequest(
            nationality="German",
            purpose="visit",
            duration="short",
            family="no",
        )
        assert req.family == "no"


class TestChatRequest:
    """Validate ChatRequest Pydantic model."""

    def test_minimal_valid_request(self) -> None:
        req = ChatRequest(session_id="abc123", message="What visa do I need?")
        assert req.session_id == "abc123"
        assert req.message == "What visa do I need?"
        assert req.quiz_answers is None
        assert req.conversation_history is None

    def test_with_quiz_answers(self) -> None:
        req = ChatRequest(
            session_id="abc123",
            message="How long does processing take?",
            quiz_answers={"nationality": "US", "purpose": "work"},
            conversation_history=[{"role": "user", "content": "Hello"}],
        )
        assert req.quiz_answers == {"nationality": "US", "purpose": "work"}
        assert len(req.conversation_history) == 1

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest(session_id="abc123")  # message missing


class TestHandoffRequest:
    """Validate HandoffRequest Pydantic model."""

    def test_valid_handoff_request(self) -> None:
        req = HandoffRequest(
            session_id="sess_abc",
            quiz_answers={"nationality": "Australian", "purpose": "retire"},
            recommended_visas=[{"visa_name": "Retirement KITAS", "price": "8.500.000 IDR"}],
            messages=[{"role": "user", "content": "I want to retire in Bali"}],
            language="en",
        )
        assert req.session_id == "sess_abc"
        assert req.language == "en"
        assert len(req.recommended_visas) == 1

    def test_optional_language_defaults_none(self) -> None:
        req = HandoffRequest(
            session_id="sess_def",
            quiz_answers={"nationality": "Russian"},
            recommended_visas=[],
            messages=[],
        )
        assert req.language is None

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            HandoffRequest(session_id="sess_xyz")  # missing quiz_answers, etc.


# ---------------------------------------------------------------------------
# 3. Recommend endpoint (mocked service)
# ---------------------------------------------------------------------------


class TestRecommendEndpoint:
    """Integration-style tests for POST /api/v1/visa-oracle/recommend."""

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_recommend_success(self, mock_get_service, mock_persist, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = [
            {
                "visa_name": "Digital Nomad Visa E33G",
                "category": "single_entry_visas",
                "price": "5.800.000 IDR",
                "duration": "60 days",
                "validity": "1 year",
                "notes": "",
                "score": 4.0,
            }
        ]
        mock_service.generate_session_id.return_value = "deadbeef" * 8
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "German",
                "purpose": "digital_nomad",
                "duration": "short",
                "family": "no",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["visas"]) == 1
        assert data["visas"][0]["visa_name"] == "Digital Nomad Visa E33G"
        assert "session_id" in data

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_recommend_parses_family_yes(self, mock_get_service, mock_persist, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = []
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "family",
                "duration": "long",
                "family": "yes",
            },
        )

        mock_service.recommend_visas.assert_called_once_with(
            nationality="US",
            purpose="family",
            duration="long",
            family=True,
        )


# ---------------------------------------------------------------------------
# 4. Visa types endpoints (mocked service)
# ---------------------------------------------------------------------------


class TestVisaTypesEndpoints:
    """Tests for GET /api/v1/visa-oracle/visa-types."""

    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_get_all_visa_types(self, mock_get_service, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.get_all_visa_types.return_value = [
            {"name": "Tourist Visa C1", "category": "single_entry_visas", "price": "3.000.000 IDR"},
            {"name": "KITAS Working", "category": "kitas_permits", "price": "15.000.000 IDR"},
        ]
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/visa-oracle/visa-types")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 2
        assert len(data["visa_types"]) == 2

    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_get_visa_type_detail_found(self, mock_get_service, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.get_all_visa_types.return_value = [
            {"name": "Tourist Visa C1", "category": "single_entry_visas", "price": "3.000.000 IDR"},
        ]
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/visa-oracle/visa-types/tourist-visa-c1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["visa_type"]["name"] == "Tourist Visa C1"

    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_get_visa_type_detail_not_found(self, mock_get_service, client: TestClient) -> None:
        mock_service = MagicMock()
        mock_service.get_all_visa_types.return_value = []
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/visa-oracle/visa-types/nonexistent-visa")

        assert response.status_code == 404
