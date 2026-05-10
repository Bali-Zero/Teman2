"""
Unit tests for backend/app/routers/crm_enhanced_documents.py
Covers: get_client_documents, create_document, create_documents_bulk,
update_document, archive_document, get_document_categories,
get_client_ocr_status, extract_visa_data, upload_document_base64,
delete_document, _parse_date_or_none.
Direct function calls with mocked dependencies (no TestClient).
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

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
def mock_current_user():
    return {
        "id": "user-uuid-123",
        "email": "zero@balizero.com",
        "role": "admin",
        "full_name": "Test Admin",
    }


# ============================================================
# _parse_date_or_none helper
# ============================================================


def test_parse_date_or_none_valid():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none

    result = _parse_date_or_none("2026-06-15")
    assert result == date(2026, 6, 15)


def test_parse_date_or_none_empty():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none

    assert _parse_date_or_none(None) is None
    assert _parse_date_or_none("") is None


def test_parse_date_or_none_invalid():
    from backend.app.routers.crm_enhanced_documents import _parse_date_or_none

    assert _parse_date_or_none("not-a-date") is None
    assert _parse_date_or_none("2026/06/15") is None


# ============================================================
# get_client_documents
# ============================================================


@pytest.mark.asyncio
async def test_get_client_documents_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import get_client_documents

    doc_row = MagicMock()
    doc_row.__iter__ = MagicMock(return_value=iter([
        ("id", 1), ("document_type", "passport"), ("file_name", "pass.pdf"),
    ]))
    doc_row.keys = MagicMock(return_value=["id", "document_type", "file_name"])
    doc_row.__getitem__ = lambda self, k: {"id": 1, "document_type": "passport", "file_name": "pass.pdf"}[k]

    # Use a simple dict list since dict(d) is called
    mock_db_pool._mock_conn.fetch.return_value = [
        {"id": 1, "document_type": "passport", "file_name": "pass.pdf"},
    ]

    with patch(
        "backend.app.routers.crm_enhanced_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_documents(
            client_id=1,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_client_documents_with_category(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import get_client_documents

    mock_db_pool._mock_conn.fetch.return_value = []

    with patch(
        "backend.app.routers.crm_enhanced_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_documents(
            client_id=1,
            category="immigration",
            include_archived=True,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result == []


# ============================================================
# create_document
# ============================================================


@pytest.mark.asyncio
async def test_create_document_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import create_document

    mock_doc_create = MagicMock()
    mock_doc_create.document_type = "passport"
    mock_doc_create.document_category = "immigration"
    mock_doc_create.file_name = "pass.pdf"
    mock_doc_create.file_id = "drive-file-id-123"
    mock_doc_create.file_url = "http://example.com/pass.pdf"
    mock_doc_create.google_drive_file_url = "http://drive.google.com/file"
    mock_doc_create.expiry_date = "2030-01-01"
    mock_doc_create.notes = "Test doc"
    mock_doc_create.family_member_id = None
    mock_doc_create.practice_id = None

    mock_db_pool._mock_conn.fetchval.return_value = 42
    mock_db_pool._mock_conn.execute.return_value = None

    background_tasks = MagicMock()

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents._dispatch_ocr_by_folder", new=AsyncMock()),
        patch("backend.services.portal.portal_notification_service.PortalNotificationService", side_effect=Exception("skip")),
    ):
        result = await create_document(
            client_id=1,
            data=mock_doc_create,
            background_tasks=background_tasks,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["id"] == 42
    assert result["ocr_triggered"] is True


@pytest.mark.asyncio
async def test_create_document_no_file_id_no_ocr(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import create_document

    mock_doc_create = MagicMock()
    mock_doc_create.document_type = "other"
    mock_doc_create.document_category = None
    mock_doc_create.file_name = "doc.pdf"
    mock_doc_create.file_id = None
    mock_doc_create.file_url = None
    mock_doc_create.google_drive_file_url = None
    mock_doc_create.expiry_date = None
    mock_doc_create.notes = None
    mock_doc_create.family_member_id = None
    mock_doc_create.practice_id = None

    mock_db_pool._mock_conn.fetchval.return_value = 43

    background_tasks = MagicMock()

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        patch("backend.services.portal.portal_notification_service.PortalNotificationService", side_effect=Exception("skip")),
    ):
        result = await create_document(
            client_id=1,
            data=mock_doc_create,
            background_tasks=background_tasks,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["ocr_triggered"] is False


# ============================================================
# create_documents_bulk
# ============================================================


@pytest.mark.asyncio
async def test_create_documents_bulk_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import create_documents_bulk

    doc1 = MagicMock()
    doc1.document_type = "passport"
    doc1.document_category = "immigration"
    doc1.file_name = "pass.pdf"
    doc1.file_id = "file-1"
    doc1.file_url = None
    doc1.google_drive_file_url = None
    doc1.expiry_date = "2030-01-01"
    doc1.notes = None
    doc1.family_member_id = None
    doc1.practice_id = None

    mock_db_pool._mock_conn.fetchval.return_value = 100
    mock_db_pool._mock_conn.execute.return_value = None

    # Mock transaction context manager
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock()
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    mock_db_pool._mock_conn.transaction = MagicMock(return_value=tx_cm)

    background_tasks = MagicMock()

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents._dispatch_ocr_by_folder", new=AsyncMock()),
    ):
        result = await create_documents_bulk(
            client_id=1,
            documents=[doc1],
            background_tasks=background_tasks,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["inserted"] == 1


@pytest.mark.asyncio
async def test_create_documents_bulk_empty(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import create_documents_bulk

    background_tasks = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await create_documents_bulk(
            client_id=1,
            documents=[],
            background_tasks=background_tasks,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_documents_bulk_too_many(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import create_documents_bulk

    docs = [MagicMock() for _ in range(101)]
    background_tasks = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await create_documents_bulk(
            client_id=1,
            documents=docs,
            background_tasks=background_tasks,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 400
    assert "100" in str(exc_info.value.detail)


# ============================================================
# update_document
# ============================================================


@pytest.mark.asyncio
async def test_update_document_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import update_document

    mock_update_data = MagicMock()
    mock_update_data.model_dump.return_value = {"notes": "Updated notes"}

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await update_document(
            client_id=1,
            doc_id=10,
            data=mock_update_data,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_update_document_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import update_document

    mock_update_data = MagicMock()
    mock_update_data.model_dump.return_value = {"notes": "test"}

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 0"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_document(
            client_id=1,
            doc_id=999,
            data=mock_update_data,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_document_no_fields(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import update_document

    mock_update_data = MagicMock()
    mock_update_data.model_dump.return_value = {}

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await update_document(
            client_id=1,
            doc_id=10,
            data=mock_update_data,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_update_document_with_date_field(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import update_document

    mock_update_data = MagicMock()
    mock_update_data.model_dump.return_value = {"expiry_date": "2030-01-01"}

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await update_document(
            client_id=1,
            doc_id=10,
            data=mock_update_data,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_update_document_with_empty_date(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import update_document

    mock_update_data = MagicMock()
    mock_update_data.model_dump.return_value = {"expiry_date": "", "notes": "test"}

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await update_document(
            client_id=1,
            doc_id=10,
            data=mock_update_data,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True


# ============================================================
# archive_document (DELETE endpoint with client_id)
# ============================================================


@pytest.mark.asyncio
async def test_archive_document_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import archive_document

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await archive_document(
            client_id=1,
            doc_id=10,
            permanent=False,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["action"] == "archived"


@pytest.mark.asyncio
async def test_archive_document_permanent(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import archive_document

    mock_db_pool._mock_conn.execute.return_value = "DELETE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await archive_document(
            client_id=1,
            doc_id=10,
            permanent=True,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["action"] == "deleted"


@pytest.mark.asyncio
async def test_archive_document_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import archive_document

    mock_db_pool._mock_conn.execute.return_value = "UPDATE 0"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await archive_document(
            client_id=1,
            doc_id=999,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# get_document_categories
# ============================================================


@pytest.mark.asyncio
async def test_get_document_categories_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import get_document_categories

    mock_db_pool._mock_conn.fetch.return_value = [
        {"code": "passport", "name": "Passport", "category_group": "immigration", "description": "Travel doc", "has_expiry": True},
    ]

    result = await get_document_categories(
        pool=mock_db_pool,
        _current_user=mock_current_user,
    )

    assert len(result) == 1
    assert result[0]["code"] == "passport"


# ============================================================
# get_client_ocr_status
# ============================================================


@pytest.mark.asyncio
async def test_get_client_ocr_status_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import get_client_ocr_status

    mock_db_pool._mock_conn.fetch.return_value = [
        {"id": 1, "document_type": "passport", "file_name": "pass.pdf", "ocr_status": "completed", "ocr_completed_at": None, "ocr_extracted_data": None},
        {"id": 2, "document_type": "npwp", "file_name": "npwp.jpg", "ocr_status": "pending", "ocr_completed_at": None, "ocr_extracted_data": None},
    ]

    with patch(
        "backend.app.routers.crm_enhanced_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_ocr_status(
            client_id=1,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["client_id"] == 1
    assert result["pending_ocr"] == 1
    assert result["completed_ocr"] == 1
    assert len(result["documents"]) == 2


@pytest.mark.asyncio
async def test_get_client_ocr_status_empty(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import get_client_ocr_status

    mock_db_pool._mock_conn.fetch.return_value = []

    with patch(
        "backend.app.routers.crm_enhanced_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_ocr_status(
            client_id=1,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["pending_ocr"] == 0
    assert result["completed_ocr"] == 0


# ============================================================
# extract_visa_data
# ============================================================


@pytest.mark.asyncio
async def test_extract_visa_data_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import extract_visa_data

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch(
            "backend.app.routers.crm_enhanced_documents._auto_ocr_visa",
            new=AsyncMock(return_value={"success": True, "fields_extracted": ["expiry_date"]}),
        ),
    ):
        result = await extract_visa_data(
            client_id=1,
            body={"file_id": "drive-file-123", "doc_id": 42},
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_extract_visa_data_no_file_id(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import extract_visa_data

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await extract_visa_data(
            client_id=1,
            body={"doc_id": 42},
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 400


# ============================================================
# delete_document (standalone, by doc_id only)
# ============================================================


@pytest.mark.asyncio
async def test_delete_document_soft(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import delete_document

    mock_db_pool._mock_conn.fetchrow.return_value = {"client_id": 1}
    mock_db_pool._mock_conn.execute.return_value = "UPDATE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await delete_document(
            doc_id=10,
            permanent=False,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["action"] == "archived"


@pytest.mark.asyncio
async def test_delete_document_permanent(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import delete_document

    mock_db_pool._mock_conn.fetchrow.return_value = {"client_id": 1}
    mock_db_pool._mock_conn.execute.return_value = "DELETE 1"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
    ):
        result = await delete_document(
            doc_id=10,
            permanent=True,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )

    assert result["success"] is True
    assert result["action"] == "deleted"


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import delete_document

    mock_db_pool._mock_conn.fetchrow.return_value = {"client_id": 1}
    mock_db_pool._mock_conn.execute.return_value = "DELETE 0"

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await delete_document(
            doc_id=999,
            permanent=True,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_no_doc_row(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_enhanced_documents import delete_document

    # Document not found in DB — fetchrow returns None
    mock_db_pool._mock_conn.fetchrow.return_value = None
    mock_db_pool._mock_conn.execute.return_value = "UPDATE 0"

    with (
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await delete_document(
            doc_id=999,
            permanent=False,
            pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


# ============================================================
# DocumentUploadBase64 model
# ============================================================


def test_document_upload_base64_model():
    from backend.app.routers.crm_enhanced_documents import DocumentUploadBase64

    d = DocumentUploadBase64(
        file="base64data",
        file_name="test.pdf",
        document_type="passport",
        company_id=10,
        practice_id=20,
    )
    assert d.file == "base64data"
    assert d.mime_type is None
    assert d.subfolder_hint is None
    assert d.family_member_id is None
    assert d.company_id == 10
    assert d.practice_id == 20


@pytest.mark.asyncio
async def test_upload_document_base64_mirrors_company_upload_to_company_documents(
    mock_db_pool,
    mock_current_user,
):
    from fastapi import BackgroundTasks

    from backend.app.routers.crm_enhanced_documents import (
        DocumentUploadBase64,
        upload_document_base64,
    )

    conn = mock_db_pool._mock_conn
    conn.fetchrow.side_effect = [
        {
            "id": 1,
            "full_name": "Client One",
            "google_drive_folder_id": "client-root-folder",
            "client_type": "individual",
        },
        {"company_id": 10},
    ]
    conn.fetchval.side_effect = [
        701,  # documents.id
        None,  # no existing company_documents row for this Drive file
        301,  # company_documents.id
    ]

    drive_service = AsyncMock()
    drive_service.get_folder_structure.return_value = {
        "folders": [{"id": "company-folder", "name": "02_Company"}],
    }
    drive_service.upload_file_to_folder.return_value = {
        "id": "drive-file-company",
        "webViewLink": "https://drive.test/company-doc",
    }

    with (
        patch("backend.app.routers.crm_enhanced_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_enhanced_documents.invalidate_cache", new=AsyncMock()),
        patch(
            "backend.app.routers.crm_enhanced_documents.ServiceAccountDriveService",
            return_value=drive_service,
        ),
    ):
        result = await upload_document_base64(
            client_id=1,
            data=DocumentUploadBase64(
                file="ZmlsZQ==",
                file_name="nib.pdf",
                document_type="nib",
                document_category="pma",
                mime_type="application/pdf",
                company_id=10,
            ),
            pool=mock_db_pool,
            current_user=mock_current_user,
            background_tasks=BackgroundTasks(),
        )

    assert result["success"] is True
    assert result["company_document_id"] == 301
    assert any(
        "INSERT INTO company_documents" in call.args[0]
        for call in conn.fetchval.await_args_list
    )
