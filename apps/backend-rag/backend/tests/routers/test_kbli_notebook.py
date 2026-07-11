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
        results = [
            {
                "payload": {
                    "kode_kbli": "56101",
                    "judul": "Restaurant Services",
                    "content": "Restaurant activities in fixed buildings",
                    "pma_status": "TERBUKA",
                    "kategori_risiko": "Menengah Rendah",
                },
                "score": 0.98,
            }
        ]

        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=results),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["code"] == "56101"
        assert payload[0]["pma_status"] == "TERBUKA"

    @pytest.mark.integration
    def test_search_kbli_returns_503_on_timeout(self, client: TestClient) -> None:
        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(side_effect=httpx.TimeoutException("timeout")),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 503

    @pytest.mark.integration
    def test_search_kbli_rejects_oversized_query(self, client: TestClient) -> None:
        response = client.get(
            "/kbli-notebook/search",
            params={"query": "x" * 1025, "limit": 10},
        )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_search_kbli_rejects_unbounded_limit(self, client: TestClient) -> None:
        response = client.get(
            "/kbli-notebook/search",
            params={"query": "restaurant", "limit": 100000},
        )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_search_kbli_rejects_zero_limit(self, client: TestClient) -> None:
        response = client.get(
            "/kbli-notebook/search",
            params={"query": "restaurant", "limit": 0},
        )

        assert response.status_code == 422


class TestChatEndpoint:
    @pytest.mark.integration
    def test_chat_kbli_returns_answer(self, client: TestClient) -> None:
        results = [
            {
                "payload": {
                    "kode_kbli": "56101",
                    "judul": "Restaurant Services",
                    "content": "Restaurant activities in fixed buildings",
                    "pma_status": "TERBUKA",
                    "kategori_risiko": "Menengah Rendah",
                },
                "score": 0.98,
            }
        ]

        gateway = MagicMock()
        gateway._available = True

        with (
            patch("backend.app.routers.kbli_notebook_chat._get_llm_gateway", return_value=gateway),
            patch(
                "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
                AsyncMock(return_value="restoran"),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._search_kbli_qdrant",
                AsyncMock(return_value=results),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._fetch_parent_documents_from_kbli_table",
                AsyncMock(return_value={"56101": "full content"}),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._generate_kbli_explanation_gemini",
                AsyncMock(return_value="KBLI 56101 is open to PMA."),
            ),
        ):
            response = client.post(
                "/kbli-notebook/chat", json={"query": "Can a foreigner own a restaurant?"}
            )

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
            patch(
                "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
                AsyncMock(return_value="restoran"),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._search_kbli_qdrant",
                AsyncMock(return_value=[]),
            ),
            patch(
                "backend.app.routers.kbli_notebook_chat._generate_kbli_explanation_gemini",
                AsyncMock(side_effect=RuntimeError("boom")),
            ),
        ):
            response = client.post(
                "/kbli-notebook/chat", json={"query": "Tell me about restaurants"}
            )

        assert response.status_code == 500

    @pytest.mark.integration
    def test_chat_kbli_rejects_oversized_query(self, client: TestClient) -> None:
        response = client.post(
            "/kbli-notebook/chat",
            json={"query": "x" * 1025, "session_id": "bounds-test"},
        )

        assert response.status_code == 422

    @pytest.mark.integration
    def test_chat_kbli_rejects_oversized_session_id(self, client: TestClient) -> None:
        response = client.post(
            "/kbli-notebook/chat",
            json={"query": "restaurant", "session_id": "x" * 129},
        )

        assert response.status_code == 422


class TestSnippetCleaning:
    @pytest.mark.unit
    def test_clean_snippet_strips_context_header(self) -> None:
        raw = (
            "[CONTEXT: KBLI 2025 - BPS 7/2025 + PP28/2025 - Kode 56101 - "
            "Aktivitas Penyediaan Makanan di Bangunan Tetap]\n\n"
            "# KBLI 56101: Aktivitas Penyediaan Makanan di Bangunan Tetap"
        )
        cleaned = kbli_notebook_module._clean_snippet(raw)
        assert cleaned.startswith("# KBLI 56101")
        assert "[CONTEXT:" not in cleaned

    @pytest.mark.unit
    def test_clean_snippet_passthrough_without_header(self) -> None:
        assert kbli_notebook_module._clean_snippet("Plain description") == "Plain description"

    @pytest.mark.unit
    def test_clean_snippet_handles_empty_and_none(self) -> None:
        assert kbli_notebook_module._clean_snippet("") == ""
        assert kbli_notebook_module._clean_snippet(None) == ""

    @pytest.mark.integration
    def test_search_strips_context_header_from_description(self, client: TestClient) -> None:
        results = [
            {
                "payload": {
                    "kode_kbli": "56101",
                    "judul": "Aktivitas Penyediaan Makanan di Bangunan Tetap",
                    "content": (
                        "[CONTEXT: KBLI 2025 - BPS 7/2025 + PP28/2025 - Kode 56101 - "
                        "Aktivitas Penyediaan Makanan di Bangunan Tetap]\n\n"
                        "Real BPS description of the restaurant activity"
                    ),
                    "pma_status": "TERBUKA",
                    "kategori_risiko": "Menengah Rendah",
                },
                "score": 0.5,
            }
        ]

        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=results),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 200
        description = response.json()[0]["description"]
        assert not description.startswith("[CONTEXT:")
        assert description.startswith("Real BPS description")


class TestExactCodeFastPath:
    _EXACT_PAYLOAD = {
        "kode_kbli": "68111",
        "judul": "Real Estat Yang Dimiliki Sendiri Atau Disewa",
        "content": "[CONTEXT: KBLI 2025 - Kode 68111 - Real Estat]\n\nReal estate activities",
        "pma_status": "TERBUKA",
        "kategori_risiko": "Menengah Rendah",
    }
    _SEMANTIC = [
        {
            "payload": {
                "kode_kbli": "41019",
                "judul": "Konstruksi Konvensional Gedung Lainnya",
                "content": "Construction of other buildings",
                "pma_status": "TERBUKA",
                "kategori_risiko": "Menengah Rendah",
            },
            "score": 0.2,
        }
    ]

    @pytest.mark.integration
    def test_search_exact_code_returns_code_first(self, client: TestClient) -> None:
        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=list(self._SEMANTIC)),
            ),
            patch(
                "backend.app.routers.kbli_notebook._get_kbli_payload_from_qdrant",
                AsyncMock(return_value=dict(self._EXACT_PAYLOAD)),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=68111")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["code"] == "68111"
        assert payload[0]["score"] == 1.0
        assert not payload[0]["description"].startswith("[CONTEXT:")
        assert payload[1]["code"] == "41019"

    @pytest.mark.integration
    def test_search_exact_code_dedupes_semantic_duplicate(self, client: TestClient) -> None:
        semantic_with_dup = list(self._SEMANTIC) + [
            {"payload": dict(self._EXACT_PAYLOAD), "score": 0.3}
        ]
        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=semantic_with_dup),
            ),
            patch(
                "backend.app.routers.kbli_notebook._get_kbli_payload_from_qdrant",
                AsyncMock(return_value=dict(self._EXACT_PAYLOAD)),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=68111")

        codes = [r["code"] for r in response.json()]
        assert codes.count("68111") == 1
        assert codes[0] == "68111"

    @pytest.mark.integration
    def test_search_exact_code_not_found_falls_back_to_semantic(
        self, client: TestClient
    ) -> None:
        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=list(self._SEMANTIC)),
            ),
            patch(
                "backend.app.routers.kbli_notebook._get_kbli_payload_from_qdrant",
                AsyncMock(return_value=None),
            ),
        ):
            response = client.get("/kbli-notebook/search?query=68100")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["code"] == "41019"

    @pytest.mark.integration
    def test_search_non_numeric_query_skips_exact_lookup(self, client: TestClient) -> None:
        exact_mock = AsyncMock(return_value=dict(self._EXACT_PAYLOAD))
        with (
            patch(
                "backend.app.routers.kbli_notebook._resolve_embedding",
                AsyncMock(return_value=[0.1, 0.2]),
            ),
            patch(
                "backend.app.routers.kbli_notebook._search_kbli_qdrant",
                AsyncMock(return_value=list(self._SEMANTIC)),
            ),
            patch(
                "backend.app.routers.kbli_notebook._get_kbli_payload_from_qdrant",
                exact_mock,
            ),
        ):
            response = client.get("/kbli-notebook/search?query=restaurant")

        assert response.status_code == 200
        exact_mock.assert_not_awaited()


class TestChatAbstainThreshold:
    @pytest.mark.unit
    def test_min_relevance_score_calibrated_range(self) -> None:
        # Calibrated 2026-07-08 against the live prod score battery (embedding
        # text-embedding-3-small, enriched 6k-char docs): legit sentences 0.28-0.52,
        # legit single keywords 0.18-0.32, off-domain noise 0.11-0.16. The previous
        # 0.40 (tuned on the pre-enrichment collection) abstained on EVERY natural
        # question. Guard the calibrated band against silent re-raising.
        assert 0.15 <= kbli_chat_module.MIN_RELEVANCE_SCORE <= 0.25
