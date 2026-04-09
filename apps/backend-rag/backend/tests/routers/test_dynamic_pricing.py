"""Tests for the dynamic pricing router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.dynamic_pricing as dynamic_pricing_module
from backend.app.dependencies import get_current_user


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(dynamic_pricing_module.router)
    application.dependency_overrides[get_current_user] = lambda: {"id": "1", "role": "admin"}
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_prefix_and_tags(self) -> None:
        assert dynamic_pricing_module.router.prefix == "/api/pricing"
        assert dynamic_pricing_module.router.tags == ["pricing"]


class TestCatalogEndpoints:
    @pytest.mark.integration
    def test_get_all_prices_success(self, client: TestClient) -> None:
        service = MagicMock()
        service.get_all_prices.return_value = {"items": [{"service": "kitas", "price": 100}]}

        with patch("backend.app.routers.dynamic_pricing.get_pricing_service", return_value=service):
            response = client.get("/api/pricing/all")

        assert response.status_code == 200
        assert response.json()["items"][0]["service"] == "kitas"

    @pytest.mark.integration
    def test_get_all_prices_returns_503_on_service_error(self, client: TestClient) -> None:
        service = MagicMock()
        service.get_all_prices.return_value = {"error": "pricing unavailable"}

        with patch("backend.app.routers.dynamic_pricing.get_pricing_service", return_value=service):
            response = client.get("/api/pricing/all")

        assert response.status_code == 503

    @pytest.mark.integration
    def test_search_pricing_validates_query_param(self, client: TestClient) -> None:
        response = client.get("/api/pricing/search")
        assert response.status_code == 422


class TestScenarioPricing:
    @pytest.mark.integration
    def test_scenario_pricing_success(self, app: FastAPI, client: TestClient) -> None:
        app.state.cross_oracle_synthesis_service = object()
        app.state.search_service = object()

        result = SimpleNamespace(
            scenario="PT PMA restaurant",
            total_setup_cost=1000.0,
            total_recurring_cost=100.0,
            currency="IDR",
            breakdown_by_category={"legal": 500.0},
            timeline_estimate="30 days",
            key_assumptions=["1 director"],
            confidence=0.9,
            cost_items=[
                SimpleNamespace(
                    category="legal",
                    description="Incorporation",
                    amount=500.0,
                    currency="IDR",
                    is_recurring=False,
                    frequency=None,
                    source_oracle="pricing",
                ),
            ],
        )

        service = MagicMock()
        service.calculate_pricing = AsyncMock(return_value=result)

        with patch("backend.services.pricing.dynamic_pricing_service.DynamicPricingService", return_value=service):
            response = client.post(
                "/api/pricing/scenario",
                json={"scenario": "PT PMA restaurant", "user_level": 3},
            )

        assert response.status_code == 200
        assert response.json()["total_setup_cost"] == 1000.0

    @pytest.mark.integration
    def test_scenario_pricing_requires_initialized_dependencies(
        self,
        client: TestClient,
    ) -> None:
        response = client.post(
            "/api/pricing/scenario",
            json={"scenario": "PT PMA restaurant", "user_level": 3},
        )

        assert response.status_code == 503

