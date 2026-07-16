"""
Tests for Visa Oracle Router

Covers:
- Router exists and exposes expected routes
- Request model validation (RecommendRequest, ChatRequest, HandoffRequest)
- Response model shapes
"""

from typing import Any
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
from backend.app.setup.route_walk import iter_leaf_routes

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
        paths = [route.path for route in iter_leaf_routes(router)]
        assert any("recommend" in p for p in paths)

    def test_router_has_chat_route(self) -> None:
        paths = [route.path for route in iter_leaf_routes(router)]
        assert any("chat" in p for p in paths)

    def test_router_has_handoff_route(self) -> None:
        paths = [route.path for route in iter_leaf_routes(router)]
        assert any("handoff" in p for p in paths)

    def test_router_has_visa_types_route(self) -> None:
        paths = [route.path for route in iter_leaf_routes(router)]
        assert any("visa-types" in p for p in paths)

    def test_router_has_visa_type_detail_route(self) -> None:
        paths = [route.path for route in iter_leaf_routes(router)]
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
    def test_recommend_parses_family_yes(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
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
# 3b. PR0 safety freeze — five-state /recommend contract (W1)
# ---------------------------------------------------------------------------


class TestRecommendStateHelpers:
    """Unit tests for the pure PR0 five-state mapping helpers."""

    def test_missing_facts_all_present(self) -> None:
        from backend.app.routers.visa_oracle import _missing_recommend_facts

        assert _missing_recommend_facts("German", "work", "long") == []

    def test_missing_facts_detects_blank_nationality(self) -> None:
        from backend.app.routers.visa_oracle import _missing_recommend_facts

        assert _missing_recommend_facts("   ", "work", "long") == ["nationality"]

    def test_missing_facts_detects_multiple_blank_fields(self) -> None:
        from backend.app.routers.visa_oracle import _missing_recommend_facts

        assert _missing_recommend_facts("", "", "long") == ["nationality", "purpose"]

    def test_state_needs_input_when_missing_facts(self) -> None:
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(
            visas=[{"visa_name": "X", "score": 4.0}],
            missing_facts=["nationality"],
        )
        assert state == "NEEDS_INPUT"
        assert reasons == []

    def test_state_temporarily_unavailable_when_no_candidates(self) -> None:
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(visas=[], missing_facts=[])
        assert state == "TEMPORARILY_UNAVAILABLE"
        assert reasons == ["catalog_no_candidates"]

    def test_state_needs_input_when_all_scores_zero(self) -> None:
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(
            visas=[
                {"visa_name": "A", "score": 0.0},
                {"visa_name": "B", "score": 0.0},
            ],
            missing_facts=[],
        )
        assert state == "NEEDS_INPUT"
        assert reasons == ["low_confidence_match"]

    def test_state_supported_candidates_when_positive_score(self) -> None:
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(
            visas=[{"visa_name": "A", "score": 2.0}],
            missing_facts=[],
        )
        assert state == "SUPPORTED_CANDIDATES"
        # FIX-2: every SUPPORTED_CANDIDATES response declares this
        # truthful limitation — the legacy scorer never evaluates
        # nationality at all.
        assert reasons == ["nationality_not_evaluated"]

    def test_state_needs_input_when_purpose_not_in_vocabulary(self) -> None:
        """FIX-1 (Codex red-team P1 #1): even a positive-scoring candidate
        must not reach SUPPORTED_CANDIDATES when `purpose` itself is
        nonsense — the vocabulary gate takes precedence over the score."""
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(
            visas=[{"visa_name": "A", "score": 2.0}],
            missing_facts=[],
            invalid_vocabulary_reasons=["invalid_purpose:banana"],
        )
        assert state == "NEEDS_INPUT"
        assert reasons == ["invalid_purpose:banana"]

    def test_state_temporarily_unavailable_when_catalog_degraded(self) -> None:
        """FIX-3 (Codex red-team P1 #2): raw candidates existed but every
        row was incomplete (dropped by `_filter_complete_visas`) — this is
        a catalog data problem, not a "no match" or "no input" problem."""
        from backend.app.routers.visa_oracle import _determine_recommend_state

        state, reasons = _determine_recommend_state(
            visas=[],
            missing_facts=[],
            invalid_vocabulary_reasons=[],
            catalog_degraded=True,
        )
        assert state == "TEMPORARILY_UNAVAILABLE"
        assert reasons == ["catalog_degraded"]


class TestInvalidRecommendVocabulary:
    """Unit tests for the FIX-1 vocabulary gate helper."""

    def test_known_purpose_and_duration_are_valid(self) -> None:
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        assert _invalid_recommend_vocabulary("work", "long") == []

    def test_unknown_purpose_flagged(self) -> None:
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        assert _invalid_recommend_vocabulary("banana", "long") == ["invalid_purpose:banana"]

    def test_unknown_duration_flagged(self) -> None:
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        assert _invalid_recommend_vocabulary("work", "nonsense") == ["invalid_duration:nonsense"]

    def test_both_unknown_flagged(self) -> None:
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        assert _invalid_recommend_vocabulary("banana", "nonsense") == [
            "invalid_purpose:banana",
            "invalid_duration:nonsense",
        ]

    def test_case_and_whitespace_insensitive(self) -> None:
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        assert _invalid_recommend_vocabulary("  Work  ", " LONG ") == []

    def test_echoed_value_is_sanitized_and_truncated(self) -> None:
        """Newlines collapse to spaces and the value truncates to 40 chars
        — this string flows into API responses and logs."""
        from backend.app.routers.visa_oracle import _invalid_recommend_vocabulary

        raw = "line1\nline2\t" + ("x" * 60)
        reasons = _invalid_recommend_vocabulary(raw, "long")
        assert len(reasons) == 1
        echoed = reasons[0].split(":", 1)[1]
        assert "\n" not in echoed
        assert "\t" not in echoed
        assert len(echoed) <= 40


class TestFilterCompleteVisas:
    """Unit tests for the FIX-3 / R2-A candidate-completeness filter.

    R2-A (Codex re-review, F2 residue): completeness requires BOTH a
    non-empty `visa_name` AND a non-empty `price` — `price` is the
    consequential field /handoff renders into the WhatsApp deep-link and
    the Telegram lead, so a named row with no price is exactly as unusable
    a "candidate" as a nameless one."""

    def test_keeps_rows_with_name_and_price(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        visas = [{"visa_name": "C1 Tourism", "price": "1.500.000 IDR", "score": 2.0}]
        assert _filter_complete_visas(visas) == visas

    def test_drops_row_missing_visa_name(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        assert _filter_complete_visas([{"price": "1 IDR", "score": 2}]) == []

    def test_drops_row_with_blank_visa_name(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        assert _filter_complete_visas([{"visa_name": "   ", "price": "1 IDR", "score": 2}]) == []

    def test_drops_row_missing_price(self) -> None:
        """R2-A guilt (probe from the task spec): a name with no price at
        all must NOT be treated as complete."""
        from backend.app.routers.visa_oracle import _filter_complete_visas

        assert _filter_complete_visas([{"visa_name": "X", "score": 2}]) == []

    def test_drops_row_with_blank_price(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        assert _filter_complete_visas([{"visa_name": "X", "price": "   ", "score": 2}]) == []

    def test_drops_row_with_none_price(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        assert _filter_complete_visas([{"visa_name": "X", "price": None, "score": 2}]) == []

    def test_keeps_row_with_numeric_zero_price(self) -> None:
        """Innocence: `price` may legitimately be a non-string (a numeric
        0, e.g.) — the spec is "non-empty/non-null", not "truthy/non-zero"."""
        from backend.app.routers.visa_oracle import _filter_complete_visas

        visas = [{"visa_name": "Free Consultation", "price": 0, "score": 1.0}]
        assert _filter_complete_visas(visas) == visas

    def test_mixed_list_keeps_only_complete_rows(self) -> None:
        from backend.app.routers.visa_oracle import _filter_complete_visas

        good = {"visa_name": "C1 Tourism", "price": "1 IDR", "score": 2.0}
        bad_name = {"visa_name": "", "price": "1 IDR", "score": 1.0}
        bad_price = {"visa_name": "Y", "price": "", "score": 1.0}
        assert _filter_complete_visas([good, bad_name, bad_price, {"score": 5}]) == [good]


class TestRecommendEndpointFiveState:
    """Integration-style tests for the additive five-state /recommend contract."""

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_supported_candidates(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
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
        assert data["state"] == "SUPPORTED_CANDIDATES"
        assert data["missing_facts"] == []
        # FIX-2: every SUPPORTED_CANDIDATES response must truthfully
        # declare that nationality was never evaluated by the scorer.
        assert data["review_reasons"] == ["nationality_not_evaluated"]
        assert len(data["visas"]) == 1

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_temporarily_unavailable_when_service_returns_no_candidates(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = []
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "family",
                "duration": "long",
                "family": "yes",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "TEMPORARILY_UNAVAILABLE"
        assert data["visas"] == []

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_needs_input_when_all_candidates_score_zero(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        """Isolates the low_confidence_match path: purpose/duration are
        BOTH valid vocabulary (FIX-1's gate must NOT fire here) and the row
        has a real `price` (R2-A's completeness gate must NOT fire either)
        — the only reason this drops to NEEDS_INPUT is the zero score."""
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = [
            {
                "visa_name": "Irrelevant Visa",
                "category": "single_entry_visas",
                "price": "1.000.000 IDR",
                "duration": "",
                "validity": "",
                "notes": "",
                "score": 0.0,
            },
        ]
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "work",
                "duration": "short",
                "family": "no",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "NEEDS_INPUT"
        assert data["visas"] == []
        assert data["review_reasons"] == ["low_confidence_match"]

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_needs_input_when_required_fact_blank(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = [
            {
                "visa_name": "Tourism",
                "category": "single_entry_visas",
                "price": "",
                "duration": "",
                "validity": "",
                "notes": "",
                "score": 3.0,
            },
        ]
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "   ",
                "purpose": "visit",
                "duration": "short",
                "family": "no",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "NEEDS_INPUT"
        assert data["missing_facts"] == ["nationality"]
        assert data["visas"] == []

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_temporarily_unavailable_on_scoring_exception(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        mock_service = MagicMock()
        mock_service.recommend_visas.side_effect = RuntimeError("pricing catalog unavailable")
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "work",
                "duration": "long",
                "family": "no",
            },
        )

        # Degraded (200 + honest state), not a fatal 500 — the frontend must
        # be able to render this without special-casing an HTTP error.
        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "TEMPORARILY_UNAVAILABLE"
        assert data["visas"] == []
        # FIX-8: a scoring exception is a real failure — success must be
        # False so the frontend parser never mistakes this for a clean
        # "here's what fits" outcome.
        assert data["success"] is False

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_temporarily_unavailable_when_catalog_degraded(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        """FIX-3 (Codex red-team P1 #2): the scorer ran fine and returned
        rows, but EVERY row is missing `visa_name` — a catalog data problem,
        distinct from both 'no match' (empty list) and 'bad input'."""
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = [
            {"score": 4.0},
            {"visa_name": "   ", "score": 3.0},
        ]
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "work",
                "duration": "long",
                "family": "no",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] == "TEMPORARILY_UNAVAILABLE"
        assert data["visas"] == []
        assert data["review_reasons"] == ["catalog_degraded"]
        assert data["success"] is True  # scorer ran fine — this isn't an exception

    @patch("backend.app.routers.visa_oracle._persist_session_create")
    @patch("backend.app.routers.visa_oracle.get_visa_oracle_service")
    def test_state_temporarily_unavailable_when_row_has_name_but_no_price(
        self, mock_get_service, mock_persist, client: TestClient
    ) -> None:
        """R2-A (Codex re-review, F2 residue): the exact probe from the
        finding — a row with `visa_name` + `score` but NO `price` at all
        must NOT reach SUPPORTED_CANDIDATES. `price` is what /handoff
        renders; a named-but-priceless row is a catalog gap, same class as
        a nameless one."""
        mock_service = MagicMock()
        mock_service.recommend_visas.return_value = [{"visa_name": "X", "score": 2}]
        mock_service.generate_session_id.return_value = "abc123"
        mock_service.hash_ip.return_value = "hashed_ip"
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/visa-oracle/recommend",
            json={
                "nationality": "US",
                "purpose": "work",
                "duration": "long",
                "family": "no",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] != "SUPPORTED_CANDIDATES"
        assert data["state"] == "TEMPORARILY_UNAVAILABLE"
        assert data["visas"] == []
        assert data["review_reasons"] == ["catalog_degraded"]


class TestRecommendEndpointRealService:
    """FIX-1 guilt/innocence tests exercised through the REAL
    `VisaOracleService` (only `PricingService` is stubbed — the scorer
    itself, `_score_visa`/`recommend_visas`, runs unmocked). The earlier
    coverage mocked `recommend_visas` directly and never exercised the
    real +1.5 duration-fit / +1.0 family bonuses that let a nonsense
    purpose like "banana" still reach a positive score and, pre-FIX-1,
    SUPPORTED_CANDIDATES — confirmed live via direct service invocation
    during the red-team round (banana/long/false → 3 candidates score 1.5)."""

    _SAMPLE_PRICES: dict[str, Any] = {
        "services": {
            "single_entry_visas": {},
            "multiple_entry_visas": {},
            "kitas_permits": {
                "Working KITAS (Altus/Onshore)": {
                    "price": "40.000.000 IDR",
                    "duration": "1 year",
                    "validity": "1 year",
                    "notes": "Work permit KITAS",
                },
                "Investor KITAS 2 Years (Altus/Onshore)": {
                    "price": "45.000.000 IDR",
                    "duration": "2 years",
                    "validity": "2 years",
                    "notes": "Investor KITAS",
                },
                "Spouse 2 Years (Altus/Onshore)": {
                    "price": "50.000.000 IDR",
                    "duration": "2 years",
                    "validity": "2 years",
                    "notes": "Spouse KITAS",
                },
                "Dependent 2 Years (Altus/Onshore)": {
                    "price": "48.000.000 IDR",
                    "duration": "2 years",
                    "validity": "2 years",
                    "notes": "Dependent KITAS",
                },
            },
            "visa_extensions": {},
            "kitap_permits": {},
            "company_services": {},
            "other_process": {},
            "urgent_services": {},
        }
    }

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        import backend.services.visa_oracle.visa_oracle_service as svc_module

        svc_module._visa_oracle_service = None
        yield
        svc_module._visa_oracle_service = None

    def _post(self, client: TestClient, **overrides: Any) -> dict[str, Any]:
        import backend.services.visa_oracle.visa_oracle_service as svc_module

        mock_pricing = MagicMock()
        mock_pricing.prices = self._SAMPLE_PRICES
        body = {
            "nationality": "US",
            "purpose": "work",
            "duration": "long",
            "family": "no",
        }
        body.update(overrides)
        with (
            patch.object(svc_module, "get_pricing_service", return_value=mock_pricing),
            patch("backend.app.routers.visa_oracle._persist_session_create"),
        ):
            response = client.post("/api/v1/visa-oracle/recommend", json=body)
        assert response.status_code == 200
        return response.json()

    def test_banana_purpose_long_duration_needs_input(self, client: TestClient) -> None:
        """Guilt: nonsense purpose="banana" paired with a VALID duration —
        pre-FIX-1 this scored 1.5 (duration-fit bonus alone) and reached
        SUPPORTED_CANDIDATES despite the purpose being meaningless."""
        data = self._post(client, purpose="banana", duration="long", family="no")
        assert data["state"] == "NEEDS_INPUT"
        assert data["visas"] == []
        assert any(r.startswith("invalid_purpose:banana") for r in data["review_reasons"])

    def test_banana_purpose_nonsense_duration_needs_input(self, client: TestClient) -> None:
        """Guilt: BOTH purpose="banana" and duration="nonsense" — pre-FIX-1
        this scored 1.0 (family bonus alone, matched via family=True) and
        still reached SUPPORTED_CANDIDATES."""
        data = self._post(client, purpose="banana", duration="nonsense", family="yes")
        assert data["state"] == "NEEDS_INPUT"
        assert data["visas"] == []
        reasons = data["review_reasons"]
        assert any(r.startswith("invalid_purpose:banana") for r in reasons)
        assert any(r.startswith("invalid_duration:nonsense") for r in reasons)

    def test_work_long_valid_vocabulary_still_supported(self, client: TestClient) -> None:
        """Innocence: a legitimate purpose+duration pair must still reach
        SUPPORTED_CANDIDATES through the real, unmocked scorer — the
        vocabulary gate must not collaterally block honest requests."""
        data = self._post(client, purpose="work", duration="long", family="no")
        assert data["state"] == "SUPPORTED_CANDIDATES"
        assert len(data["visas"]) > 0
        assert data["review_reasons"] == ["nationality_not_evaluated"]


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
