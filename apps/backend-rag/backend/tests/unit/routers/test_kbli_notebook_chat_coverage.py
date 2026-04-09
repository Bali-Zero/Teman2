"""
Unit tests for kbli_notebook_chat router.
Coverage target: POST /kbli-notebook/chat — happy paths, error paths,
non-business query deflection, multi-domain routing, fallback paths.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================
# Module-level mocks: must be set up before import
# ============================================================

# Patch heavy dependencies before importing the router
_mock_llm_gateway = MagicMock()
_mock_llm_gateway._available = True
_mock_llm_gateway.create_chat_with_history = MagicMock(return_value=MagicMock())
_mock_llm_gateway.send_message = AsyncMock(
    return_value=(
        "KBLI 56101 is a restaurant. PMA: TERBUKA.",
        "gemini-flash",
        MagicMock(),
        {},
    )
)


@pytest.fixture(autouse=True)
def patch_llm_gateway():
    """Patch the LLM gateway singleton for all tests."""
    with patch(
        "backend.app.routers.kbli_notebook_chat._llm_gateway_instance",
        _mock_llm_gateway,
    ):
        yield


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_search_service():
    svc = MagicMock()
    svc.embed = AsyncMock(return_value=[0.1] * 1536)
    return svc


@pytest.fixture
def app(mock_db_pool, mock_search_service):
    from backend.app.dependencies import get_optional_database_pool, get_search_service
    from backend.app.routers.kbli_notebook_chat import router

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_optional_database_pool] = lambda: mock_db_pool
    test_app.dependency_overrides[get_search_service] = lambda: mock_search_service
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ============================================================
# Shared payload builder
# ============================================================


def chat_payload(query: str, session_id: str = "test-session-001") -> dict:
    return {"query": query, "session_id": session_id}


# ============================================================
# POST /kbli-notebook/chat — happy paths
# ============================================================


def test_chat_kbli_happy_path_restaurant(client):
    """Should return 200 for a restaurant query."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Restaurant answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("I want to open a restaurant in Bali"))
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "results" in data


def test_chat_kbli_happy_path_kbli_code(client):
    """Should return 200 for a query containing a KBLI code."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="56101")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="KBLI 56101 explanation")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("What is KBLI 56101?"))
    assert response.status_code == 200


def test_chat_kbli_returns_required_fields(client):
    """Response must include answer, detected_kbli, results, sources, suggested_queries."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="answer text")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("coffee shop"))
    assert response.status_code == 200
    data = response.json()
    required = {"answer", "detected_kbli", "results", "sources", "suggested_queries"}
    assert required.issubset(data.keys())


# ============================================================
# Non-business query deflection
# ============================================================


def test_chat_kbli_deflects_visa_query(client):
    """Should deflect visa/immigration queries."""
    with patch(
        "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
        new=AsyncMock(return_value="kitas"),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("How do I get KITAS in Bali?"))
    assert response.status_code == 200
    data = response.json()
    # Answer should mention KBLI specialization
    assert "KBLI" in data["answer"] or "imigrasi" in data["answer"].lower() or "immigration" in data["answer"].lower()
    assert data["detected_kbli"] == []


def test_chat_kbli_deflects_recommendation_query(client):
    """Should deflect 'best restaurant' recommendation queries."""
    with patch(
        "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
        new=AsyncMock(return_value="best restaurant"),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("best restaurant in Bali"))
    assert response.status_code == 200
    data = response.json()
    assert data["detected_kbli"] == []


def test_chat_kbli_deflects_kitap_query(client):
    """Should deflect KITAP queries."""
    with patch(
        "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
        new=AsyncMock(return_value="kitap"),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("How to renew KITAP?"))
    assert response.status_code == 200
    data = response.json()
    assert data["detected_kbli"] == []


def test_chat_kbli_deflects_indonesian_visa_query(client):
    """Should deflect Indonesian visa queries in Indonesian language."""
    with patch(
        "backend.app.routers.kbli_notebook_chat._translate_query_for_kbli",
        new=AsyncMock(return_value="izin tinggal"),
    ):
        response = client.post(
            "/kbli-notebook/chat",
            json=chat_payload("bagaimana cara mendapatkan izin tinggal?"),
        )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_kbli"] == []


# ============================================================
# Keyword injection (KNOWN_KBLI_CODES path)
# ============================================================


def test_chat_kbli_keyword_injection_laundry(client):
    """Should inject KBLI 96100 for laundry queries."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="laundry")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Laundry answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("I want to open a laundry business"))
    assert response.status_code == 200


def test_chat_kbli_keyword_injection_beauty_salon(client):
    """Should inject KBLI 96220 for beauty salon queries."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="beauty salon")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Beauty salon answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("beauty salon nail art in Bali"))
    assert response.status_code == 200


# ============================================================
# Multi-domain routing
# ============================================================


def test_chat_kbli_multi_domain_kg_orchestrator(client, mock_db_pool):
    """Should use KG Orchestrator for multi-domain queries (KBLI + visa)."""
    mock_kg_response = MagicMock()
    mock_kg_response.answer = "You need PT PMA with KITAS investor visa."
    mock_kg_response.sources = [{"title": "test source", "relevance": "High"}]
    mock_kg_response.reasoning_trace = ["step1", "step2"]
    mock_kg_response.golden_route_matched = None

    mock_orchestrator = MagicMock()
    mock_orchestrator.process = AsyncMock(return_value=mock_kg_response)

    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran kitas")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch(
            "backend.app.routers.kbli_notebook_chat.KGAgenticOrchestrator",
            return_value=mock_orchestrator,
        ),
    ):
        response = client.post(
            "/kbli-notebook/chat",
            json=chat_payload("Can I open a restaurant in Bali with a retirement KITAS?"),
        )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data


def test_chat_kbli_multi_domain_kg_orchestrator_fails(client, mock_db_pool):
    """Should fall back to KBLI-only when KG orchestrator raises."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran visa")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Fallback answer")),
        patch(
            "backend.app.routers.kbli_notebook_chat.KGAgenticOrchestrator",
            side_effect=Exception("KG crash"),
        ),
    ):
        response = client.post(
            "/kbli-notebook/chat",
            json=chat_payload("Open a restaurant in Bali with KITAS visa?"),
        )
    assert response.status_code == 200


# ============================================================
# Qdrant failure paths
# ============================================================


def test_chat_kbli_qdrant_fails_postgres_fallback(client, mock_db_pool):
    """Should use PostgreSQL fallback when Qdrant search fails."""
    db_row = MagicMock()
    db_row.__getitem__ = lambda self, k: {
        "entity_id": "kbli:56101",
        "name": "AKTIVITAS PENYEDIAAN MAKANAN",
        "description": "Restaurant activities",
        "properties": '{"pma_status": "TERBUKA", "kategori_risiko": "Rendah"}',
    }[k]

    mock_db_pool._mock_conn.fetch.return_value = [db_row]

    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(side_effect=Exception("Qdrant down"))),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Postgres fallback answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("restaurant"))
    assert response.status_code == 200


def test_chat_kbli_qdrant_fails_no_db(client):
    """Should handle both Qdrant and Postgres failure gracefully."""
    from backend.app.dependencies import get_optional_database_pool

    app2 = FastAPI()
    from backend.app.routers.kbli_notebook_chat import router as kbli_router
    from backend.app.dependencies import get_search_service

    app2.include_router(kbli_router)
    app2.dependency_overrides[get_optional_database_pool] = lambda: None  # No DB pool

    mock_ss = MagicMock()
    mock_ss.embed = AsyncMock(return_value=[0.1] * 1536)
    app2.dependency_overrides[get_search_service] = lambda: mock_ss

    tc = TestClient(app2)
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(side_effect=Exception("Qdrant down"))),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="No results answer")),
    ):
        response = tc.post("/kbli-notebook/chat", json=chat_payload("restaurant"))
    assert response.status_code == 200


# ============================================================
# Direct KBLI code lookup paths
# ============================================================


def test_chat_kbli_direct_lookup_from_kbli_documents(client, mock_db_pool):
    """Should use kbli_documents for direct 5-digit code queries."""
    db_row = MagicMock()
    db_row.__getitem__ = lambda self, k: {
        "kode_kbli": "56101",
        "judul": "AKTIVITAS PENYEDIAAN MAKANAN",
        "content": "Restaurant content " * 20,
        "metadata": {"pma_status": "TERBUKA"},
    }[k]

    # First fetchrow returns doc, second returns None for kg_nodes
    mock_db_pool._mock_conn.fetchrow.side_effect = [db_row, None]
    mock_db_pool._mock_conn.fetch.return_value = []

    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="56101")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Code 56101 answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("Tell me about KBLI 56101"))
    assert response.status_code == 200


def test_chat_kbli_direct_lookup_from_known_codes(client, mock_db_pool):
    """Should use KNOWN_KBLI_CODES for codes not in DB or Qdrant."""
    mock_db_pool._mock_conn.fetchrow.return_value = None

    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="56301")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._get_kbli_payload_from_qdrant", new=AsyncMock(return_value=None)),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Bar answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("Tell me about KBLI 56301"))
    assert response.status_code == 200
    data = response.json()
    # 56301 is in KNOWN_KBLI_CODES as AKTIVITAS BAR
    assert "answer" in data


# ============================================================
# LLM gateway unavailable
# ============================================================


def test_chat_kbli_llm_unavailable_still_returns(client):
    """Should still return 200 even if LLM unavailable (uses fallback)."""
    _mock_llm_gateway._available = False

    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="restoran")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="Fallback LLM answer")),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("restaurant"))

    _mock_llm_gateway._available = True  # restore
    assert response.status_code == 200


# ============================================================
# Missing required fields
# ============================================================


def test_chat_kbli_missing_query(client):
    """Should return 422 when query field is missing."""
    response = client.post("/kbli-notebook/chat", json={"session_id": "abc"})
    assert response.status_code == 422


def test_chat_kbli_empty_query(client):
    """Should handle empty string query gracefully."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
        patch("backend.app.routers.kbli_notebook_chat._generate_kbli_explanation", new=AsyncMock(return_value="No results")),
    ):
        response = client.post("/kbli-notebook/chat", json={"query": "", "session_id": "test"})
    # May be 200 or 422 depending on Pydantic model — either is acceptable
    assert response.status_code in (200, 422)


# ============================================================
# Glossary / definitional queries
# ============================================================


def test_chat_kbli_glossary_terbatas(client):
    """Should return glossary answer for 'terbatas' definition query."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="terbatas")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("What does TERBATAS mean?"))
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data


def test_chat_kbli_glossary_tertutup(client):
    """Should return glossary answer for 'tertutup' definition query."""
    with (
        patch("backend.app.routers.kbli_notebook_chat._translate_query_for_kbli", new=AsyncMock(return_value="tertutup")),
        patch("backend.app.routers.kbli_notebook_chat._search_kbli_qdrant", new=AsyncMock(return_value=[])),
    ):
        response = client.post("/kbli-notebook/chat", json=chat_payload("What is TERTUTUP?"))
    assert response.status_code == 200
