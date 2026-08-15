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
        assert payload[0]["pma_status"] == "NOT_VERIFIED"
        assert payload[0]["pma_max_asing"] is None
        assert payload[0]["pma_verification_status"] == "declared_gap"

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
                    "official_description": "Real BPS description of the restaurant activity",
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

    @pytest.mark.unit
    def test_real_01111_shape_withholds_raw_terbuka_100_without_provenance(self) -> None:
        result = kbli_notebook_module._result_from_payload(
            {
                "kode_kbli": "01111",
                "judul": "Pertanian Jagung",
                "description": "Official BPS corn farming scope",
                "pma_status": "TERBUKA",
                "pma_max_asing": 100,
                "pma_verification_status": "declared_gap",
                "bali_blocked": False,
                "bali_status": "OK_or_HIGHER_RISK",
                "bali_reason": "Nationally open to 100% foreign ownership.",
            },
            score=0.9,
        )

        assert result.pma_status == "NOT_VERIFIED"
        assert result.pma_max_asing is None
        assert result.pma_official_basis is None
        assert result.pma_source_vintage is None
        assert result.bali_blocked is None
        assert result.bali_status is None
        assert result.bali_reason == ""

    @pytest.mark.unit
    def test_declared_gap_withholds_expert_legal_editorial_atomically(self) -> None:
        result = kbli_notebook_module.KBLISearchResult(
            code="01111",
            title="Pertanian Jagung",
            description="Official BPS scope",
            score=0.9,
            pma_status="TERBUKA",
            pma_max_asing=100,
            pma_verification_status="declared_gap",
            bali_blocked=True,
            bali_status="CHIUSO_MORATORIA_BALI",
            bali_reason="Nationally open to 100% foreign ownership.",
            expert_legal={"summary": "Foreign ownership is unrestricted."},
        )

        assert result.pma_status == "NOT_VERIFIED"
        assert result.bali_blocked is None
        assert result.bali_status is None
        assert result.bali_reason == ""
        assert result.expert_legal is None

    @pytest.mark.unit
    def test_declared_gap_detail_model_withholds_cached_expert_editorial(self) -> None:
        detail = kbli_notebook_module.KBLIDetail(
            code="01111",
            title="Pertanian Jagung",
            description="Official BPS scope",
            licensing_status="REGULATED",
            sector="A",
            risk_profile="Unknown",
            licenses=[],
            pma_status="TERBUKA",
            pma_max_asing=100,
            pma_verification_status="declared_gap",
            expert_legal={"summary": "Foreign ownership is unrestricted."},
        )

        assert detail.pma_status == "NOT_VERIFIED"
        assert detail.pma_max_asing is None
        assert detail.expert_legal is None

    @pytest.mark.unit
    def test_located_tuple_preserves_status_cap_and_provenance(self) -> None:
        result = kbli_notebook_module._result_from_payload(
            {
                "kode_kbli": "16221",
                "judul": "Industri Barang dari Rotan",
                "description": "Official BPS scope",
                "pma_status": "TERBATAS",
                "pma_max_asing": 49,
                "pma_verification_status": "located",
                "pma_official_basis": "Perpres 49/2021 Lampiran III entry 3",
                "pma_source_vintage": "2021-05-25",
                "pma_cap_verified": True,
                "expert_legal": {"summary": "Unbound legacy ownership prose."},
            },
            score=0.9,
        )

        assert result.pma_status == "TERBATAS"
        assert result.pma_max_asing == 49
        assert result.pma_verification_status == "located"
        assert result.pma_official_basis
        assert result.pma_source_vintage == "2021-05-25"
        assert result.pma_verdict_verified is True
        assert result.expert_legal is None

        # These response models are mutable because the chat router enriches
        # them after retrieval.  The decision property must therefore re-check
        # the entire tuple instead of trusting a stale ``located`` marker.
        result.pma_official_basis = None
        assert result.pma_verdict_verified is False

    @pytest.mark.unit
    def test_located_detail_still_withholds_cross_store_expert_editorial(self) -> None:
        detail = kbli_notebook_module.KBLIDetail(
            code="16221",
            title="Industri Barang dari Rotan",
            description="Official BPS scope",
            licensing_status="REGULATED",
            sector="C",
            risk_profile="Unknown",
            licenses=[],
            pma_status="TERBATAS",
            pma_max_asing=49,
            pma_verification_status="located",
            pma_official_basis="Perpres 49/2021 Lampiran III entry 3",
            pma_source_vintage="2021-05-25",
            pma_cap_verified=True,
            expert_legal={"summary": "Unbound legacy ownership prose."},
        )

        assert detail.pma_verdict_verified is True
        assert detail.expert_legal is None

    @pytest.mark.unit
    def test_generated_content_never_becomes_public_search_description(self) -> None:
        result = kbli_notebook_module._result_from_payload(
            {
                "kode_kbli": "16291",
                "judul": "Industri Anyaman Rotan dan Bambu",
                "content": "Nationally this activity is 100% open to foreign ownership.",
                "official_description": "Official BPS woven-rattan scope.",
                "pma_status": "TERBUKA",
                "pma_max_asing": 100,
                "pma_verification_status": "declared_gap",
            },
            score=0.9,
        )

        assert result.description.startswith("Official BPS woven-rattan scope")
        assert "100%" not in result.description

    @pytest.mark.unit
    def test_legacy_gold_description_is_not_treated_as_official_scope(self) -> None:
        result = kbli_notebook_module._result_from_payload(
            {
                "kode_kbli": "16291",
                "judul": "Industri Anyaman Rotan dan Bambu",
                "description": "This business is open to 100% foreign ownership.",
                "pma_verification_status": "declared_gap",
            },
            score=0.9,
        )

        assert result.description == "Official BPS description unavailable for KBLI 16291."
        assert "100%" not in result.description


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
    def test_search_exact_code_not_found_falls_back_to_semantic(self, client: TestClient) -> None:
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


def _condition_matches(payload: dict, condition: dict) -> bool:
    """Evaluate ONE Qdrant filter condition against a fake payload.

    Handles the two shapes `_get_kbli_payload_from_qdrant` actually sends: a plain
    FieldCondition (`{"key": ..., "match": {"value": ...}}`, with dotted keys read
    as one level of nested dict access, mirroring `metadata.doc_type`), and a
    nested Filter used as a condition (`{"should": [...]}` / `{"must": [...]}`).
    """
    if "key" in condition:
        key = condition["key"]
        if "." in key:
            top, _, rest = key.partition(".")
            value = (payload.get(top) or {}).get(rest)
        else:
            value = payload.get(key)
        match = condition.get("match", {})
        return "value" in match and value == match["value"]
    return _filter_matches(payload, condition)


def _filter_matches(payload: dict, qdrant_filter: dict) -> bool:
    """Evaluate a Qdrant `Filter` (must/should/must_not) against a fake payload.

    A real, if simplified, evaluator of the wire filter body the router sends --
    not a canned response keyed on the request's shape -- per W114 (fake at the
    HTTP boundary, speak the real vocabulary, don't let the fixture assume what
    the code under test assumes).
    """
    musts = qdrant_filter.get("must", [])
    shoulds = qdrant_filter.get("should", [])
    must_nots = qdrant_filter.get("must_not", [])
    if not all(_condition_matches(payload, c) for c in musts):
        return False
    if any(_condition_matches(payload, c) for c in must_nots):
        return False
    if shoulds and not any(_condition_matches(payload, c) for c in shoulds):
        return False
    return True


class _FakeQdrantScrollClient:
    """Fakes the Qdrant `/points/scroll` HTTP endpoint at the wire boundary.

    `storage` is an ORDERED list of payload dicts standing in for the collection's
    real (arbitrary, ID-ordered) scroll traversal order -- the guilt fixtures below
    deliberately put the gold twin FIRST, reproducing the 2026-08-09 incident's
    observed ordering for 56101/47721/85312, so a passing test proves the doc_type
    selection filters it out rather than proving nothing because gold never came
    first in the fixture.
    """

    def __init__(self, storage: list[dict]) -> None:
        self.storage = storage
        self.requests: list[dict] = []

    async def post(self, url: str, json: dict, headers: dict | None = None):
        self.requests.append(json)
        qdrant_filter = json["filter"]
        limit = json.get("limit", 1)
        matches = [p for p in self.storage if _filter_matches(p, qdrant_filter)]
        response = httpx.Response(
            200,
            json={"result": {"points": [{"payload": p} for p in matches[:limit]]}},
            request=httpx.Request("POST", url),
        )
        return response


class TestExactCodeFastPathSelectsCanonicalBPS:
    """Guilt+innocence for the 2026-08-09 gold-twin coin-flip fix.

    Tests `_get_kbli_payload_from_qdrant` directly at the HTTP boundary (fakes
    `_get_kbli_client()`'s `.post()`), never the higher-level `/search` route --
    the defect lives entirely inside this one function's filter body.
    """

    # Real forms of the 3 codes the 2026-08-09 incident confirmed flip to
    # gold-first under the un-fixed filter (10/10 UUID-order correlation).
    _GUILT_CODES = {
        "56101": {
            "judul": "Aktivitas Penyediaan Makanan di Bangunan Tetap",
            "content": "Restaurant activities in fixed buildings",
        },
        "47721": {
            "judul": "Perdagangan Eceran Sediaan Farmasi untuk Manusia di Apotek",
            "content": "Pharmacy retail activities",
        },
        "85312": {
            "judul": "Pendidikan Menengah Pertama Umum Swasta",
            "content": "Private junior secondary education",
        },
    }

    def _twin_storage(self, code: str, fields: dict) -> list[dict]:
        gold_first = {
            "kode_kbli": code,
            "doc_type": "kbli_gold",
            "judul": fields["judul"],
            "content": "## Quick Answer\n" + fields["content"],
        }
        bps = {
            "kode_kbli": code,
            "doc_type": "kbli_bps",
            "judul": fields["judul"],
            "content": fields["content"],
        }
        return [gold_first, bps]  # gold deliberately first in storage order

    @pytest.mark.unit
    @pytest.mark.parametrize("code", ["56101", "47721", "85312"])
    async def test_guilt_bare_code_returns_bps_even_when_gold_sorts_first(self, code: str) -> None:
        fields = self._GUILT_CODES[code]
        fake_client = _FakeQdrantScrollClient(self._twin_storage(code, fields))
        with patch(
            "backend.app.routers.kbli_notebook._get_kbli_client",
            return_value=fake_client,
        ):
            result = await kbli_notebook_module._get_kbli_payload_from_qdrant(code)

        assert result is not None
        assert result["doc_type"] == "kbli_bps"
        assert result["kode_kbli"] == code
        assert not result["content"].startswith("## Quick Answer")

    @pytest.mark.unit
    async def test_innocence_bps_only_code_resolves_identically(self) -> None:
        storage = [
            {
                "kode_kbli": "68111",
                "doc_type": "kbli_bps",
                "judul": "Real Estat Yang Dimiliki Sendiri Atau Disewa",
                "content": "Real estate activities",
            }
        ]
        fake_client = _FakeQdrantScrollClient(storage)
        with patch(
            "backend.app.routers.kbli_notebook._get_kbli_client",
            return_value=fake_client,
        ):
            result = await kbli_notebook_module._get_kbli_payload_from_qdrant("68111")

        assert result is not None
        assert result["doc_type"] == "kbli_bps"

    @pytest.mark.unit
    async def test_innocence_no_points_at_all_returns_none(self) -> None:
        fake_client = _FakeQdrantScrollClient(storage=[])
        with patch(
            "backend.app.routers.kbli_notebook._get_kbli_client",
            return_value=fake_client,
        ):
            result = await kbli_notebook_module._get_kbli_payload_from_qdrant("99999")

        assert result is None

    @pytest.mark.unit
    async def test_honest_edge_gold_only_orphan_falls_through_to_not_found(self) -> None:
        """A code with ONLY a gold point (no BPS twin) must NOT serve gold content
        as if it were the canonical record -- it must fall through to not-found,
        same as any other unresolvable code (the router's semantic fallback then
        takes over), per the 2026-08-09 design decision (positive selection, not
        exclusion)."""
        storage = [
            {
                "kode_kbli": "64921",
                "doc_type": "kbli_gold",
                "judul": "Orphan gold-only entry",
                "content": "## Quick Answer\nno BPS twin exists for this code",
            }
        ]
        fake_client = _FakeQdrantScrollClient(storage)
        with patch(
            "backend.app.routers.kbli_notebook._get_kbli_client",
            return_value=fake_client,
        ):
            result = await kbli_notebook_module._get_kbli_payload_from_qdrant("64921")

        assert result is None


class TestChatAbstainThreshold:
    @pytest.mark.unit
    def test_min_relevance_score_calibrated_range(self) -> None:
        # Calibrated 2026-07-08 against the live prod score battery (embedding
        # text-embedding-3-small, enriched 6k-char docs): legit sentences 0.28-0.52,
        # legit single keywords 0.18-0.32, off-domain noise 0.11-0.16. The previous
        # 0.40 (tuned on the pre-enrichment collection) abstained on EVERY natural
        # question. Guard the calibrated band against silent re-raising.
        assert 0.15 <= kbli_chat_module.MIN_RELEVANCE_SCORE <= 0.25
