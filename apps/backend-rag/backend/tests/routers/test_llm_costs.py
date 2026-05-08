"""Tests for the LLM cost recording admin router."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.routers.llm_costs as llm_costs_module


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(llm_costs_module.router)
    application.dependency_overrides[llm_costs_module.require_admin] = lambda: "admin@balizero.com"
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def _valid_payload() -> dict[str, object]:
    return {
        "provider": "openai",
        "model": "gpt-5.5",
        "input_tokens": 1200,
        "output_tokens": 300,
        "cost_usd": 0.42,
        "success": True,
        "latency_ms": 850,
        "endpoint": "cron-agent",
        "request_id": "req-1",
        "error_class": None,
        "cache_hit_tokens": 200,
    }


class TestLLMCostRecord:
    @pytest.mark.unit
    def test_model_rejects_negative_tokens(self) -> None:
        payload = _valid_payload()
        payload["input_tokens"] = -1

        with pytest.raises(ValueError):
            llm_costs_module.LLMCostRecord.model_validate(payload)


class TestRequireAdmin:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_admin_accepts_admin_role(self, mock_db_pool) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"role": "admin"})
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))

        email = await llm_costs_module.require_admin("admin@balizero.com", request)

        assert email == "admin@balizero.com"
        conn.fetchrow.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_admin_rejects_non_admin_role(self, mock_db_pool) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"role": "member"})
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))

        with pytest.raises(HTTPException) as exc_info:
            await llm_costs_module.require_admin("member@balizero.com", request)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Only admins and founders can record LLM cost events"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_require_admin_wraps_database_errors(self, mock_db_pool) -> None:
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=RuntimeError("db unavailable"))
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=pool)))

        with pytest.raises(HTTPException) as exc_info:
            await llm_costs_module.require_admin("admin@balizero.com", request)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"


class TestLLMCostEndpoint:
    @pytest.mark.integration
    def test_record_remote_delegates_to_observability_recorder(self, client: TestClient) -> None:
        recorder = AsyncMock(return_value={"recorded": True, "jsonl": True})

        with patch("backend.app.routers.llm_costs.record_llm_call", recorder):
            response = client.post("/api/admin/llm-costs/record", json=_valid_payload())

        assert response.status_code == 200
        assert response.json() == {"recorded": True, "jsonl": True}
        recorder.assert_awaited_once_with(**_valid_payload())

    @pytest.mark.integration
    def test_record_remote_validates_payload_before_recording(self, client: TestClient) -> None:
        payload = _valid_payload()
        payload["latency_ms"] = -10
        recorder = AsyncMock(return_value={"recorded": True})

        with patch("backend.app.routers.llm_costs.record_llm_call", recorder):
            response = client.post("/api/admin/llm-costs/record", json=payload)

        assert response.status_code == 422
        recorder.assert_not_awaited()
