"""Tests for the intel scraper router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.intel_scraper as intel_scraper_module


def _submission_payload() -> dict[str, object]:
    return {
        "title": "Visa update",
        "content": "Important visa update content",
        "source_url": "https://example.com/article",
        "source_name": "scraper",
        "category": "visa",
        "relevance_score": 80,
        "tier": "T1",
    }


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(intel_scraper_module.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_router_has_submit_endpoint(self) -> None:
        paths = {route.path for route in intel_scraper_module.router.routes}
        assert "/api/intel/scraper/submit" in paths


class TestSubmitFromScraper:
    @pytest.mark.integration
    def test_submit_job_success(self, client: TestClient) -> None:
        with (
            patch("backend.app.utils.internal_api_auth.api_key_auth.validate_api_key", return_value={"role": "internal"}),
            patch.object(intel_scraper_module.classification_service, "classify_intel_type", return_value="news"),
            patch.object(intel_scraper_module.staging_service, "generate_item_id", return_value="news_123"),
            patch.object(intel_scraper_module.staging_service, "check_duplicate", return_value=None),
            patch.object(intel_scraper_module.staging_service, "save_staging_item", return_value=Path("/tmp/news_123.json")),
            patch.object(intel_scraper_module.staging_service, "update_staging_queue_metrics"),
        ):
            response = client.post(
                "/api/intel/scraper/submit",
                headers={"X-API-Key": "test_api_key_1"},
                json=_submission_payload(),
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["item_id"] == "news_123"
        assert body["duplicate"] is False

    @pytest.mark.integration
    def test_submit_job_rejects_missing_api_key(self, client: TestClient) -> None:
        response = client.post("/api/intel/scraper/submit", json=_submission_payload())
        assert response.status_code == 401

    @pytest.mark.integration
    def test_submit_job_returns_duplicate_result(self, client: TestClient) -> None:
        with (
            patch("backend.app.utils.internal_api_auth.api_key_auth.validate_api_key", return_value={"role": "internal"}),
            patch.object(intel_scraper_module.classification_service, "classify_intel_type", return_value="news"),
            patch.object(intel_scraper_module.staging_service, "generate_item_id", return_value="news_123"),
            patch.object(intel_scraper_module.staging_service, "check_duplicate", return_value={"item_id": "existing_1"}),
        ):
            response = client.post(
                "/api/intel/scraper/submit",
                headers={"X-API-Key": "test_api_key_1"},
                json=_submission_payload(),
            )

        assert response.status_code == 200
        assert response.json()["duplicate"] is True

