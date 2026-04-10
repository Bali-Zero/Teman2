"""
Unit tests for backend/app/routers/crm_enhanced_documents.py

Covers: get_client_documents, create_document, create_documents_bulk,
        update_document, archive_document, get_document_categories,
        get_client_ocr_status, extract_visa_data, delete_document,
        upload_document_base64
Tests: happy path + error path for HTTP contract.
"""

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from httpx import AsyncClient, ASGITransport
from backend.app.main_cloud import app
from backend.app.dependencies import get_current_user, get_database_pool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(mock_current_user, mock_db_pool, disable_auth_middleware):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_client_user(mock_client_user, mock_db_pool, disable_auth_middleware):
    """Client-role user fixture."""
    app.dependency_overrides[get_current_user] = lambda: mock_client_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: GET /api/crm/clients/{client_id}/documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_client_documents_success(client, mock_db_conn):
    """Happy path: returns list of documents."""
    mock_db_conn.fetchrow = AsyncMock(return_value=None)  # verify_client_access
    mock_db_conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "document_type": "passport",
                "document_category": "immigration",
                "file_name": "passport.pdf",
                "file_id": "drive-id-123",
                "file_url": "https://drive.google.com/file/1",
                "google_drive_file_url": "https://drive.google.com/file/1",
                "status": "active",
                "expiry_date": None,
                "notes": None,
                "is_archived": False,
                "family_member_id": None,
                "practice_id": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "family_member_name": None,
                "alert_color": "green",
            }
        ]
    )

    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/crm/clients/1/documents")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["document_type"] == "passport"


@pytest.mark.asyncio
async def test_get_client_documents_with_category_filter(client, mock_db_conn):
    """Category filter is applied."""
    mock_db_conn.fetch = AsyncMock(return_value=[])

    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/crm/clients/1/documents?category=immigration")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_client_documents_include_archived(client, mock_db_conn):
    """include_archived=true passes through."""
    mock_db_conn.fetch = AsyncMock(return_value=[])

    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/crm/clients/1/documents?include_archived=true")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: POST /api/crm/clients/{client_id}/documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_document_success(client, mock_db_conn):
    """Happy path: creates document, returns id."""
    mock_db_conn.fetchval = AsyncMock(return_value=42)
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    doc_payload = {
        "document_type": "passport",
        "document_category": "immigration",
        "file_name": "passport.pdf",
        "file_id": "drive-abc123",
        "file_url": "https://drive.google.com/file/1",
        "google_drive_file_url": "https://drive.google.com/file/1",
        "expiry_date": "2028-01-01",
        "notes": None,
        "family_member_id": None,
        "practice_id": None,
    }

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents._dispatch_ocr_by_folder"),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.asyncio.create_task"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/crm/clients/1/documents", json=doc_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 42
    assert data["success"] is True


@pytest.mark.asyncio
async def test_create_document_invalid_expiry_date(client, mock_db_conn):
    """Invalid expiry_date string is handled gracefully (defaults to None)."""
    mock_db_conn.fetchval = AsyncMock(return_value=55)
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    doc_payload = {
        "document_type": "visa",
        "document_category": "immigration",
        "file_name": "visa.pdf",
        "file_id": "drive-xyz",
        "file_url": None,
        "google_drive_file_url": None,
        "expiry_date": "not-a-date",  # invalid
    }

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents._dispatch_ocr_by_folder"),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.asyncio.create_task"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/crm/clients/1/documents", json=doc_payload)

    assert response.status_code == 200
    assert response.json()["success"] is True


# ---------------------------------------------------------------------------
# Tests: POST /api/crm/clients/{client_id}/documents/bulk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_documents_bulk_success(client, mock_db_conn):
    """Bulk insert 2 documents → inserted=2."""
    mock_db_conn.fetchval = AsyncMock(side_effect=[101, 102])
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    # Support transaction context manager
    mock_transaction = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=False)
    mock_db_conn.transaction = MagicMock(return_value=mock_transaction)

    docs = [
        {
            "document_type": "passport",
            "document_category": "immigration",
            "file_name": "p1.pdf",
            "file_id": None,
        },
        {
            "document_type": "kitas",
            "document_category": "immigration",
            "file_name": "k1.pdf",
            "file_id": None,
        },
    ]

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents._dispatch_ocr_by_folder"),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/crm/clients/1/documents/bulk", json=docs)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["inserted"] == 2


@pytest.mark.asyncio
async def test_create_documents_bulk_empty(client, mock_db_conn):
    """Empty list → 400."""
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/crm/clients/1/documents/bulk", json=[])

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_documents_bulk_exceeds_limit(client, mock_db_conn):
    """More than 100 documents → 400."""
    docs = [{"document_type": f"doc{i}", "file_name": f"f{i}.pdf"} for i in range(101)]

    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/crm/clients/1/documents/bulk", json=docs)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: PATCH /api/crm/clients/{client_id}/documents/{doc_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_document_success(client, mock_db_conn):
    """Happy path: update notes field."""
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                "/api/crm/clients/1/documents/10",
                json={"notes": "Updated note"},
            )

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_update_document_not_found(client, mock_db_conn):
    """No rows updated → 404."""
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 0")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch(
                "/api/crm/clients/1/documents/999",
                json={"notes": "Should fail"},
            )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_document_no_fields(client, mock_db_conn):
    """Empty update body → 400."""
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.patch("/api/crm/clients/1/documents/10", json={})

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: DELETE /api/crm/clients/{client_id}/documents/{doc_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_document_success(client, mock_db_conn):
    """Soft delete (archive) → 200."""
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/clients/1/documents/10")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "archived"


@pytest.mark.asyncio
async def test_archive_document_permanent(client, mock_db_conn):
    """Permanent delete → 200 with action=deleted."""
    mock_db_conn.execute = AsyncMock(return_value="DELETE 1")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/clients/1/documents/10?permanent=true")

    assert response.status_code == 200
    assert response.json()["action"] == "deleted"


@pytest.mark.asyncio
async def test_archive_document_not_found(client, mock_db_conn):
    """No rows deleted → 404."""
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 0")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/clients/1/documents/999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: GET /api/crm/document-categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_document_categories_success(client, mock_db_conn):
    """Returns list of categories."""
    mock_db_conn.fetch = AsyncMock(
        return_value=[
            {
                "code": "passport",
                "name": "Passport",
                "category_group": "immigration",
                "description": "International passport",
                "has_expiry": True,
            }
        ]
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/crm/document-categories")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["code"] == "passport"


# ---------------------------------------------------------------------------
# Tests: GET /api/crm/clients/{client_id}/ocr-status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ocr_status_success(client, mock_db_conn):
    """Returns OCR status counts."""
    mock_db_conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 1,
                "document_type": "passport",
                "file_name": "passport.pdf",
                "ocr_status": "completed",
                "ocr_completed_at": "2026-01-01T12:00:00Z",
                "ocr_extracted_data": None,
            },
            {
                "id": 2,
                "document_type": "visa",
                "file_name": "visa.pdf",
                "ocr_status": "pending",
                "ocr_completed_at": None,
                "ocr_extracted_data": None,
            },
        ]
    )

    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/crm/clients/1/ocr-status")

    assert response.status_code == 200
    data = response.json()
    assert data["client_id"] == 1
    assert data["pending_ocr"] == 1
    assert data["completed_ocr"] == 1
    assert len(data["documents"]) == 2


# ---------------------------------------------------------------------------
# Tests: POST /api/crm/clients/{client_id}/extract-visa
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_visa_data_missing_file_id(client, mock_db_conn):
    """Missing file_id → 400."""
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/crm/clients/1/extract-visa",
                json={"doc_id": 123},  # no file_id
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_extract_visa_data_success(client, mock_db_conn):
    """Happy path: delegates to _auto_ocr_visa."""
    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch(
            "backend.app.routers.crm_enhanced_documents._auto_ocr_visa",
            new_callable=AsyncMock,
            return_value={"success": True, "ocr_data": {}},
        ),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/crm/clients/1/extract-visa",
                json={"file_id": "drive-abc", "doc_id": 10},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ---------------------------------------------------------------------------
# Tests: DELETE /api/crm/documents/{doc_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document_success(client, mock_db_conn):
    """Soft delete document by doc_id → 200."""
    mock_db_conn.fetchrow = AsyncMock(return_value={"client_id": 1})
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/documents/10")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["action"] == "archived"


@pytest.mark.asyncio
async def test_delete_document_permanent(client, mock_db_conn):
    """Permanent delete by doc_id → 200 with action=deleted."""
    mock_db_conn.fetchrow = AsyncMock(return_value={"client_id": 1})
    mock_db_conn.execute = AsyncMock(return_value="DELETE 1")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/documents/10?permanent=true")

    assert response.status_code == 200
    assert response.json()["action"] == "deleted"


@pytest.mark.asyncio
async def test_delete_document_not_found(client, mock_db_conn):
    """Document not found → 404."""
    mock_db_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_conn.execute = AsyncMock(return_value="UPDATE 0")

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new_callable=AsyncMock),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete("/api/crm/documents/9999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: POST /api/crm/clients/{client_id}/documents/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_document_invalid_base64(client, mock_db_conn):
    """Invalid base64 content → 400."""
    with patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/crm/clients/1/documents/upload",
                json={
                    "file": "not-valid-base64!!!!",
                    "file_name": "test.pdf",
                    "document_type": "passport",
                    "mime_type": "application/pdf",
                },
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_document_client_not_found(client, mock_db_conn):
    """Client not found in DB → 404."""
    mock_db_conn.fetchrow = AsyncMock(return_value=None)

    file_b64 = base64.b64encode(b"fake pdf content").decode()

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new_callable=AsyncMock),
        patch("backend.app.routers.crm_enhanced_documents.auto_categorize_document", return_value={"document_category": "immigration"}),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/crm/clients/1/documents/upload",
                json={
                    "file": file_b64,
                    "file_name": "passport.pdf",
                    "document_type": "passport",
                },
            )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: _parse_date_or_none helper
# ---------------------------------------------------------------------------


def test_parse_date_valid():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none
    from datetime import date
    result = _parse_date_or_none("2028-12-31")
    assert result == date(2028, 12, 31)


def test_parse_date_none():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none
    assert _parse_date_or_none(None) is None


def test_parse_date_invalid():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none
    assert _parse_date_or_none("not-a-date") is None
