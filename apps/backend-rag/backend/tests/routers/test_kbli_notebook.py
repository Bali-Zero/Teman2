"""Tests for KBLI notebook search and chat routers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.app.routers.kbli_notebook as kbli_notebook_module
import backend.app.routers.kbli_notebook_chat as kbli_chat_module
from backend.app.dependencies import get_optional_database_pool, get_search_service


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()
    application.include_router(kbli_notebook_module.router)
    application.include_router(kbli_chat_module.router)
    application.dependency_overrides[get_search_service] = lambda: MagicMock(embedder=MagicMock())
    application.dependency_overrides[get_optional_database_pool] = lambda: None
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestRouterStructure:
    @pytest.mark.unit
    def test_both_routers_use_kbli_prefix(self) -> None:
        assert kbli_notebook_module.router.prefix == "/kbli-notebook"
        assert kbli_chat_module.router.prefix == "/kbli-notebook"


class TestSearchEndpoint:
    @pytest.mark.integration
    def test_search_kbli_returns_results(self, client: TestClient) -> None:
        results = [{
            "payload": {
                "kode_kbli": "56101",
                "judul": "Restaurant Services",
                "content": "Restaurant activities in fixed buildings",
                "pma_status": "TERBUKA",
                "kategori_risiko": "Menengah Rendah",
            },
            "score": 0.98,
        }]

        with (
            patch("backend.app.routers.kbli_notebook._resolve_embedding", AsyncMock(return_value=[0.1, 0.2])),
            patch("backend.app.routers.kbli_notebook._search_kbli_qdrant", AsyncMock(return_value=results)),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["code"] == "56101"
        assert payload[0]["pma_status"] == "TERBUKA"

    @pytest.mark.integration
    def test_search_kbli_returns_503_on_timeout(self, client: TestClient) -> None:
        with (
            patch("backend.app.routers.kbli_notebook._resolve_embedding", AsyncMock(return_value=[0.1, 0.2])),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(side_effect=httpx.TimeoutException("timeout")),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 503


class TestChatEndpoint:
    @pytest.mark.integration
    def test_chat_kbli_returns_answer(self, client: TestClient) -> None:
        results = [{
            "payload": {
                "kode_kbli": "56101",
                "judul": "Restaurant Services",
                "content": "Restaurant activities in fixed buildings",
                "pma_status": "TERBUKA",
                "kategori_risiko": "Menengah Rendah",
            },
            "score": 0.98,
        }]

        gateway = MagicMock()
        gateway._available = True

        with (
            patch("backend.app.routers.kbli_notebook_chat._get_llm_gateway", return_value=gateway),
            patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", AsyncMock(return_value="restoran")),
            patch("backend.app.routers.kbli_notebook_chat._resolve_embedding", AsyncMock(return_value=[0.1, 0.2])),
            patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", AsyncMock(return_value=results)),
            patch("backend.app.routers.kbli_notebook_chat._fetch_parent_documents_from_kbli_table", AsyncMock(return_value={"56101": "full content"})),
            patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation_gemini", AsyncMock(return_value="KBLI 56101 is open to PMA.")),
        ):
            response = client.post("/kbli-notebook/chat", json={"query": "Can a foreigner own a restaurant?"})

        assert response.status_code == 200
        payload = response.json()
        assert "KBLI 56101" in payload["answer"]
        assert payload["detected_kbli"] == ["56101"]

    @pytest.mark.integration
    def test_chat_kbli_returns_500_on_engine_error(self, client: TestClient) -> None:
        gateway = MagicMock()
        gateway._available = True

        with (
            patch("backend.app.routers.kbli_notebook_chat._get_llm_gateway", return_value=gateway),
            patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", AsyncMock(return_value="restoran")),
            patch("backend.app.routers.kbli_notebook_chat._resolve_embedding", AsyncMock(return_value=[0.1, 0.2])),
            patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", AsyncMock(return_value=[])),
            patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation_gemini", AsyncMock(side_effect=RuntimeError("boom"))),
        ):
            response = client.post("/kbli-notebook/chat", json={"query": "Tell me about restaurants"})

        assert response.status_code == 500

