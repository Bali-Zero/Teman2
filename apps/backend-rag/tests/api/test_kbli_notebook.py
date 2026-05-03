from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_search_service():
    service = MagicMock()
    service.embedder = MagicMock()
    service.embedder.generate_query_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return service


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()

    # Mock for /inspect/01111
    conn.fetchrow.return_value = {
        "entity_id": "kbli:01111",
        "name": "KBLI 01111 Pertanian Jagung",
        "entity_type": "kbli",
        "description": "Deskripsi Jagung",
        "properties": '{"uraian": "Uraian Jagung", "pma_status": "TERBUKA", "licensing_status": "REGULATED"}',
    }
    conn.fetch.return_value = []  # No licenses for simple mock
    conn.fetchval.return_value = "sektor:I.A"

    pool.acquire.return_value.__aenter__.return_value = conn
    return pool


def test_search_kbli_endpoint(
    authenticated_client: TestClient, mock_search_service, monkeypatch: pytest.MonkeyPatch
):
    # Override dependency
    from backend.app.dependencies import get_search_service
    from backend.app.routers import kbli_notebook

    authenticated_client.app.dependency_overrides[get_search_service] = lambda: mock_search_service
    monkeypatch.setattr(
        kbli_notebook,
        "_search_kbli_qdrant",
        AsyncMock(
            return_value=[
                {
                    "payload": {
                        "kode_kbli": "01111",
                        "judul": "Pertanian Jagung",
                        "content": "Kelompok ini mencakup kegiatan pertanian jagung.",
                        "pma_status": "TERBUKA",
                        "kategori_risiko": "Rendah",
                    },
                    "score": 0.95,
                }
            ]
        ),
    )

    response = authenticated_client.get("/api/v1/kbli-notebook/search?query=jagung")

    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert data[0]["code"] == "01111"
    assert "Jagung" in data[0]["title"]

    # Cleanup
    authenticated_client.app.dependency_overrides.clear()


def test_inspect_kbli_endpoint(authenticated_client: TestClient, mock_db_pool):
    # Override dependency
    from backend.app.dependencies import get_optional_database_pool

    authenticated_client.app.dependency_overrides[get_optional_database_pool] = lambda: mock_db_pool

    response = authenticated_client.get("/api/v1/kbli-notebook/inspect/01111")

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "01111"
    assert data["pma_status"] == "TERBUKA"
    assert data["sector"] == "I.A"

    # Cleanup
    authenticated_client.app.dependency_overrides.clear()


def test_chat_kbli_endpoint(
    authenticated_client: TestClient, mock_search_service, monkeypatch: pytest.MonkeyPatch
):
    from backend.app.dependencies import get_search_service
    from backend.app.routers import kbli_notebook

    if hasattr(authenticated_client.app.state, "health_monitor"):
        authenticated_client.app.state.health_monitor.stop = AsyncMock()

    authenticated_client.app.dependency_overrides[get_search_service] = lambda: mock_search_service
    monkeypatch.setattr(
        kbli_notebook,
        "_search_kbli_qdrant",
        AsyncMock(
            return_value=[
                {
                    "payload": {
                        "kode_kbli": "56101",
                        "judul": "Restoran",
                        "content": "Aktivitas penyediaan makanan di bangunan tetap.",
                        "pma_status": "TERBUKA",
                        "kategori_risiko": "Menengah Rendah",
                    },
                    "score": 0.98,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        kbli_notebook, "_translate_query_for_kbli", AsyncMock(return_value="restoran")
    )
    monkeypatch.setattr(
        kbli_notebook,
        "_generate_kbli_explanation_gemini",
        AsyncMock(return_value="KBLI 56101 adalah kode restoran."),
    )
    monkeypatch.setattr(
        kbli_notebook, "_get_kbli_payload_from_qdrant", AsyncMock(return_value=None)
    )

    response = authenticated_client.post(
        "/api/v1/kbli-notebook/chat", json={"query": "Requirements for KBLI 56101"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "56101" in data["detected_kbli"]

    authenticated_client.app.dependency_overrides.clear()
