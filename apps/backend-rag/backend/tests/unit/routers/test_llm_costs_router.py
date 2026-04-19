"""Tests for POST /api/admin/llm-costs/record endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.llm_costs import require_admin, router


# ---------------------------------------------------------------------------
# Shared app fixture — isolated FastAPI instance (no global middleware)
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal FastAPI app with only the llm_costs router."""
    _app = FastAPI()
    _app.include_router(router)
    _app.dependency_overrides[require_admin] = lambda: "zero@balizero.com"
    return _app


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Happy-path test
# ---------------------------------------------------------------------------


def test_post_record_accepts_valid_payload(app, client):
    with patch(
        "backend.app.routers.llm_costs.record_llm_call",
        new=AsyncMock(return_value={"prometheus": True, "postgres": True, "jsonl": True}),
    ):
        r = client.post(
            "/api/admin/llm-costs/record",
            json={
                "provider": "gemini",
                "model": "gemini-flash-3.0-preview",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.001,
                "success": True,
                "latency_ms": 300,
                "endpoint": "cron.intel_scraper",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["postgres"] is True
    assert body["prometheus"] is True
    assert body["jsonl"] is True


# ---------------------------------------------------------------------------
# Validation failure: missing required fields → 422
# ---------------------------------------------------------------------------


def test_post_record_422_on_missing_required_fields(client):
    r = client.post(
        "/api/admin/llm-costs/record",
        json={"provider": "gemini"},  # missing most fields
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Validation failure: negative tokens → 422
# ---------------------------------------------------------------------------


def test_post_record_rejects_negative_tokens(client):
    r = client.post(
        "/api/admin/llm-costs/record",
        json={
            "provider": "gemini",
            "model": "test",
            "input_tokens": -1,   # invalid — must be >= 0
            "output_tokens": 10,
            "cost_usd": 0.01,
            "success": True,
            "latency_ms": 100,
        },
    )
    assert r.status_code == 422
