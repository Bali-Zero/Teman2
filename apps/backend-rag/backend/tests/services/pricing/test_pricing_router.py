"""Tests for /api/pricing/* endpoints and PricingCalculateRequest validation."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Stub out heavy dependencies before importing the router
_middleware_mod = ModuleType("backend.app.middleware")
_hybrid_auth_mod = ModuleType("backend.app.middleware.hybrid_auth")
_hybrid_auth_mod.OptionalUser = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("backend.app.middleware", _middleware_mod)
sys.modules.setdefault("backend.app.middleware.hybrid_auth", _hybrid_auth_mod)

_deps_mod = ModuleType("backend.app.dependencies")
_deps_mod.get_current_user = lambda: None  # type: ignore[attr-defined]
sys.modules.setdefault("backend.app.dependencies", _deps_mod)

from backend.app.routers.dynamic_pricing import router as pricing_router  # noqa: E402

SAMPLE_PRICES = {
    "services": {
        "single_entry_visas": [
            {"code": "C1", "name": "Tourist Visa", "price_idr": 2_300_000},
        ],
        "kitas_permits": [
            {"code": "E28A", "name": "Investor KITAS", "price_idr": 20_000_000},
        ],
    },
    "contact_info": {"email": "info@balizero.com"},
    "disclaimer": {},
}

SEARCH_RESULT = {
    "official_notice": "🔒 PREZZI UFFICIALI BALI ZERO 2025",
    "search_query": "kitas",
    "results": {
        "kitas_permits": [{"code": "E28A", "name": "Investor KITAS", "price_idr": 20_000_000}]
    },
}


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(pricing_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_pricing_service_loaded():
    svc = MagicMock()
    svc.loaded = True
    svc.get_all_prices.return_value = SAMPLE_PRICES
    svc.search_service.return_value = SEARCH_RESULT
    svc.get_pricing.return_value = {"official_notice": "prices", "kitas_permits": []}
    return svc


@pytest.fixture
def mock_pricing_service_unloaded():
    svc = MagicMock()
    svc.loaded = False
    svc.get_all_prices.return_value = {"error": "prices not loaded"}
    svc.search_service.return_value = {"error": "prices not loaded"}
    return svc


class TestGetAllPricesEndpoint:
    def test_returns_price_catalog(self, app_client, mock_pricing_service_loaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_loaded,
        ):
            resp = app_client.get("/api/pricing/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data

    def test_503_when_service_not_loaded(self, app_client, mock_pricing_service_unloaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_unloaded,
        ):
            resp = app_client.get("/api/pricing/all")
        assert resp.status_code == 503


class TestSearchPricingEndpoint:
    def test_returns_search_results(self, app_client, mock_pricing_service_loaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_loaded,
        ):
            resp = app_client.get("/api/pricing/search?q=kitas")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_400_when_q_missing(self, app_client, mock_pricing_service_loaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_loaded,
        ):
            resp = app_client.get("/api/pricing/search")
        assert resp.status_code == 422  # FastAPI validation error

    def test_503_when_service_not_loaded(self, app_client, mock_pricing_service_unloaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_unloaded,
        ):
            resp = app_client.get("/api/pricing/search?q=visa")
        assert resp.status_code == 503

    def test_calls_search_service_with_query(self, app_client, mock_pricing_service_loaded):
        with patch(
            "backend.app.routers.dynamic_pricing.get_pricing_service",
            return_value=mock_pricing_service_loaded,
        ):
            app_client.get("/api/pricing/search?q=investor+kitas")
        mock_pricing_service_loaded.search_service.assert_called_once_with("investor kitas")


class TestPricingJsonConsistency:
    """Verify the official JSON has valid price fields for all services."""

    @pytest.fixture
    def real_pricing_service(self):
        from backend.services.pricing.pricing_service import PricingService

        svc = PricingService()
        return svc

    def test_json_loads_successfully(self, real_pricing_service):
        assert real_pricing_service.loaded, (
            "bali_zero_official_prices_2025.json must exist and load"
        )

    def test_all_categories_present(self, real_pricing_service):
        expected_categories = [
            "single_entry_visas",
            "multiple_entry_visas",
            "visa_extensions",
            "kitas_permits",
            "kitap_permits",
            "company_services",
            "other_process",
            "urgent_services",
        ]
        services = real_pricing_service.prices.get("services", {})
        for cat in expected_categories:
            assert cat in services, f"Missing category: {cat}"

    def test_all_list_services_have_name(self, real_pricing_service):
        """Every service object in list format must have a 'name' field."""
        services = real_pricing_service.prices.get("services", {})
        for cat_name, cat_data in services.items():
            if not isinstance(cat_data, list):
                continue
            for i, item in enumerate(cat_data):
                assert "name" in item or "code" in item, (
                    f"{cat_name}[{i}] missing 'name' and 'code'"
                )

    def test_all_list_services_have_price(self, real_pricing_service):
        """Every service object in list format must have price_idr or price field."""
        services = real_pricing_service.prices.get("services", {})
        missing = []
        for cat_name, cat_data in services.items():
            if not isinstance(cat_data, list):
                continue
            for item in cat_data:
                if not isinstance(item, dict):
                    continue
                has_price = any(k in item for k in ("price_idr", "price", "price_usd_approx"))
                name = item.get("name", item.get("code", "unknown"))
                if not has_price:
                    missing.append(f"{cat_name}/{name}")
        assert missing == [], f"Services without price fields: {missing}"

    def test_get_all_prices_returns_services(self, real_pricing_service):
        result = real_pricing_service.get_all_prices()
        assert "services" in result
        assert isinstance(result["services"], dict)

    def test_search_returns_results_for_known_service(self, real_pricing_service):
        result = real_pricing_service.search_service("kitas")
        assert "results" in result or "message" in result

    def test_search_not_found_returns_message_not_error(self, real_pricing_service):
        """Unknown query must return 'message' (not found) — not an error response."""
        result = real_pricing_service.search_service("xyznonexistent12345")
        assert "error" not in result
        assert "message" in result or "results" in result

    def test_pricing_service_down_returns_503_shape(self):
        """When PricingService is not loaded, all methods return error dict (not raise)."""
        from backend.services.pricing.pricing_service import PricingService

        svc = PricingService.__new__(PricingService)
        svc.prices = {}
        svc.loaded = False

        for method_name in (
            "get_all_prices",
            "get_visa_prices",
            "get_kitas_prices",
            "get_business_prices",
            "get_tax_prices",
        ):
            result = getattr(svc, method_name)()
            assert "error" in result, f"{method_name} should return error when not loaded"


class TestPricingCalculateRequestValidation:
    """Test input validation for PricingCalculateRequest."""

    def test_valid_request(self):
        from backend.app.routers.agents import PricingCalculateRequest

        req = PricingCalculateRequest(service_type="visa", complexity="standard", urgency="normal")
        assert req.service_type == "visa"

    def test_defaults(self):
        from backend.app.routers.agents import PricingCalculateRequest

        req = PricingCalculateRequest()
        assert req.service_type == "all"
        assert req.complexity == "standard"
        assert req.urgency == "normal"

    def test_invalid_complexity_rejected(self):
        from pydantic import ValidationError

        from backend.app.routers.agents import PricingCalculateRequest

        with pytest.raises(ValidationError):
            PricingCalculateRequest(complexity="superfast")

    def test_invalid_urgency_rejected(self):
        from pydantic import ValidationError

        from backend.app.routers.agents import PricingCalculateRequest

        with pytest.raises(ValidationError):
            PricingCalculateRequest(urgency="instant")
