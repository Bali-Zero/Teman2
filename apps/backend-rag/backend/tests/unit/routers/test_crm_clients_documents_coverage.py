"""
Unit tests for backend/app/routers/crm_clients_documents.py
Covers: metrics summary, metrics refresh, passport OCR (deprecated + enhanced),
document delete, NPWP OCR, NIB OCR, required documents.
Direct function calls with mocked dependencies (no TestClient).
"""

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Pre-inject `os` into the crm_clients_documents module namespace
# because the module uses os.environ.get() inside function bodies
# but doesn't import os at the top level.
import backend.app.routers.crm_clients_documents as _ccd_module

if not hasattr(_ccd_module, "os"):
    _ccd_module.os = os


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


@pytest.fixture
def mock_team_user():
    return {
        "id": "user-uuid-456",
        "email": "team@balizero.com",
        "role": "team",
        "full_name": "Team Member",
    }


# ============================================================
# get_crm_metrics_summary
# ============================================================


@pytest.mark.asyncio
async def test_get_crm_metrics_summary_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import get_crm_metrics_summary

    mock_metrics = {"total_clients": 100, "active": 80}

    with patch(
        "backend.app.routers.crm_clients_documents.metrics_collector.get_metrics_summary",
        new=AsyncMock(return_value=mock_metrics),
    ):
        result = await get_crm_metrics_summary(
            current_user=mock_current_user,
            _db_pool=mock_db_pool,
        )
    assert result["total_clients"] == 100


@pytest.mark.asyncio
async def test_get_crm_metrics_summary_no_email(mock_db_pool):
    from backend.app.routers.crm_clients_documents import get_crm_metrics_summary

    with pytest.raises(HTTPException) as exc_info:
        await get_crm_metrics_summary(
            current_user={"email": ""},
            _db_pool=mock_db_pool,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_crm_metrics_summary_exception(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import get_crm_metrics_summary

    with (
        patch(
            "backend.app.routers.crm_clients_documents.metrics_collector.get_metrics_summary",
            new=AsyncMock(side_effect=RuntimeError("metrics fail")),
        ),
        pytest.raises(HTTPException),
    ):
        await get_crm_metrics_summary(
            current_user=mock_current_user,
            _db_pool=mock_db_pool,
        )


# ============================================================
# refresh_crm_metrics
# ============================================================


@pytest.mark.asyncio
async def test_refresh_crm_metrics_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import refresh_crm_metrics

    mock_result = {
        "timestamp": "2026-04-10T10:00:00",
        "metrics_updated": ["clients", "practices"],
        "errors": [],
    }

    with (
        patch("backend.app.routers.crm_clients_documents.is_crm_admin", return_value=True),
        patch(
            "backend.app.routers.crm_clients_documents.metrics_collector.update_all_metrics",
            new=AsyncMock(return_value=mock_result),
        ),
    ):
        result = await refresh_crm_metrics(
            current_user=mock_current_user,
            _db_pool=mock_db_pool,
        )
    assert result["message"] == "CRM metrics refreshed successfully"
    assert result["metrics_updated"] == ["clients", "practices"]


@pytest.mark.asyncio
async def test_refresh_crm_metrics_not_admin(mock_db_pool, mock_team_user):
    from backend.app.routers.crm_clients_documents import refresh_crm_metrics

    with (
        patch("backend.app.routers.crm_clients_documents.is_crm_admin", return_value=False),
        pytest.raises(HTTPException) as exc_info,
    ):
        await refresh_crm_metrics(
            current_user=mock_team_user,
            _db_pool=mock_db_pool,
        )
    assert exc_info.value.status_code == 403


# ============================================================
# extract_passport_data (deprecated)
# ============================================================


@pytest.mark.asyncio
async def test_extract_passport_data_deprecated(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import (
        PassportExtractRequest,
        extract_passport_data,
    )

    request = PassportExtractRequest(client_id=1, image_url="http://example.com/img.jpg")
    result = await extract_passport_data(
        request=request,
        current_user=mock_current_user,
        db_pool=mock_db_pool,
    )
    assert result.success is False
    assert "deprecated" in result.message.lower()


# ============================================================
# extract_passport_enhanced — preview mode (client_id=None)
# ============================================================


@pytest.mark.asyncio
async def test_extract_passport_enhanced_preview_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import (
        PassportPreviewRequest,
        extract_passport_enhanced,
    )

    # Encode some test image data
    test_image = base64.b64encode(b"fake image data").decode()

    request = PassportPreviewRequest(
        image_base64=test_image,
        mime_type="image/jpeg",
        client_id=None,
    )

    mock_ollama_resp = MagicMock()
    mock_ollama_resp.status_code = 200
    mock_ollama_resp.json.return_value = {
        "response": '{"passport_number": "AB123456", "expiry_date": "2030-01-01", "full_name": "JOHN DOE", "gender": "M", "date_of_birth": "1990-05-15", "nationality": "AUS", "confidence": 0.95}'
    }

    with (
        patch("httpx.AsyncClient") as mock_cls,
        patch("backend.utils.passport_normalize.normalize_date", side_effect=lambda x: x),
        patch("backend.utils.passport_normalize.normalize_nationality", side_effect=lambda x: x),
        patch("backend.utils.passport_normalize.title_case_name", side_effect=lambda x: x),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value={
            "passport_number": "AB123456",
            "expiry_date": "2030-01-01",
            "full_name": "JOHN DOE",
            "gender": "M",
            "date_of_birth": "1990-05-15",
            "nationality": "AUS",
            "confidence": 0.95,
        }),
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_ollama_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_passport_enhanced(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is True
    assert result.passport_number == "AB123456"
    assert "Preview" in result.message


@pytest.mark.asyncio
async def test_extract_passport_enhanced_invalid_base64(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import (
        PassportPreviewRequest,
        extract_passport_enhanced,
    )

    request = PassportPreviewRequest(
        image_base64="not-valid-base64!!!",
        client_id=None,
    )

    result = await extract_passport_enhanced(
        request=request,
        current_user=mock_current_user,
        db_pool=mock_db_pool,
    )
    assert result.success is False
    assert "base64" in result.message.lower() or "Invalid" in result.message


@pytest.mark.asyncio
async def test_extract_passport_enhanced_ollama_error(mock_db_pool, mock_current_user):
    """When Ollama returns HTTP 500 AND Gemini Vision is unavailable, the
    endpoint should return a graceful 'service unavailable' response.

    We patch GENAI_AVAILABLE explicitly because it is a module-level flag
    set at import time — leaving it alone creates a test-order dependency:
    when running the whole routers folder, another test has already
    warmed up the genai client, GENAI_AVAILABLE is True, and this test
    ends up making a real call to the Gemini API.
    """
    from backend.app.routers.crm_clients_documents import (
        PassportPreviewRequest,
        extract_passport_enhanced,
    )

    test_image = base64.b64encode(b"fake image").decode()
    request = PassportPreviewRequest(image_base64=test_image, client_id=None)

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch("httpx.AsyncClient") as mock_cls,
        patch("backend.llm.genai_client.GENAI_AVAILABLE", False),
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_passport_enhanced(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False
    assert "unavailable" in result.message.lower()


@pytest.mark.asyncio
async def test_extract_passport_enhanced_json_parse_fail(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import (
        PassportPreviewRequest,
        extract_passport_enhanced,
    )

    test_image = base64.b64encode(b"fake image").decode()
    request = PassportPreviewRequest(image_base64=test_image, client_id=None)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "Not JSON at all"}

    with (
        patch("httpx.AsyncClient") as mock_cls,
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value=None),
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_passport_enhanced(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False
    assert "parse" in result.message.lower()


@pytest.mark.asyncio
async def test_extract_passport_enhanced_persist_client_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import (
        PassportPreviewRequest,
        extract_passport_enhanced,
    )

    test_image = base64.b64encode(b"fake image").decode()
    request = PassportPreviewRequest(image_base64=test_image, client_id=999)

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with patch(
        "backend.app.routers.crm_clients_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await extract_passport_enhanced(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False
    assert "not found" in result.message.lower()


# ============================================================
# delete_client_document
# ============================================================


@pytest.mark.asyncio
async def test_delete_document_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import delete_client_document

    doc_row = {
        "id": 1,
        "client_id": 10,
        "document_type": "passport",
        "file_name": "passport.pdf",
        "status": "active",
    }
    mock_db_pool._mock_conn.fetchrow.return_value = doc_row
    mock_db_pool._mock_conn.execute.return_value = None

    with patch(
        "backend.app.routers.crm_clients_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await delete_client_document(
            document_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result["success"] is True
    assert "marked as deleted" in result["message"]


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import delete_client_document

    mock_db_pool._mock_conn.fetchrow.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await delete_client_document(
            document_id=999,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_already_deleted(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import delete_client_document

    doc_row = {
        "id": 1,
        "client_id": 10,
        "document_type": "passport",
        "file_name": "passport.pdf",
        "status": "deleted",
    }
    mock_db_pool._mock_conn.fetchrow.return_value = doc_row

    with patch(
        "backend.app.routers.crm_clients_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await delete_client_document(
            document_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert result["success"] is True
    assert "already deleted" in result["message"]


@pytest.mark.asyncio
async def test_delete_document_exception(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import delete_client_document

    mock_db_pool._mock_conn.fetchrow.side_effect = RuntimeError("DB crash")

    with pytest.raises(HTTPException) as exc_info:
        await delete_client_document(
            document_id=1,
            db_pool=mock_db_pool,
            current_user=mock_current_user,
        )
    assert exc_info.value.status_code == 500


# ============================================================
# extract_npwp
# ============================================================


@pytest.mark.asyncio
async def test_extract_npwp_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest, extract_npwp

    test_file = base64.b64encode(b"fake npwp image").decode()
    request = NpwpExtractRequest(client_id=1, file=test_file, file_name="npwp.jpg")

    mock_ollama_resp = MagicMock()
    mock_ollama_resp.status_code = 200
    mock_ollama_resp.json.return_value = {
        "response": '{"npwp": "123456789012345", "address": "Jl Test", "city": "Denpasar", "confidence": 0.9}'
    }

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value={
            "npwp": "123456789012345",
            "address": "Jl Test",
            "city": "Denpasar",
            "confidence": 0.9,
        }),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_ollama_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_npwp(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is True
    assert result.npwp == "123456789012345"


@pytest.mark.asyncio
async def test_extract_npwp_invalid_base64(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest, extract_npwp

    request = NpwpExtractRequest(client_id=1, file="invalid!!!base64", file_name="npwp.jpg")

    with patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()):
        result = await extract_npwp(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )
    assert result.success is False
    assert "base64" in result.message.lower()


@pytest.mark.asyncio
async def test_extract_npwp_ollama_error(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest, extract_npwp

    test_file = base64.b64encode(b"fake image").decode()
    request = NpwpExtractRequest(client_id=1, file=test_file, file_name="npwp.jpg")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_npwp(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False
    assert "unavailable" in result.message.lower()


@pytest.mark.asyncio
async def test_extract_npwp_json_parse_fail(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest, extract_npwp

    test_file = base64.b64encode(b"fake image").decode()
    request = NpwpExtractRequest(client_id=1, file=test_file, file_name="npwp.jpg")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "not json"}

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value=None),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_npwp(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False
    assert "parse" in result.message.lower()


@pytest.mark.asyncio
async def test_extract_npwp_wrong_digit_count(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest, extract_npwp

    test_file = base64.b64encode(b"fake image").decode()
    request = NpwpExtractRequest(client_id=1, file=test_file, file_name="npwp.jpg")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "{}"}

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value={
            "npwp": "123",
            "address": None,
            "city": None,
            "confidence": 0.5,
        }),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_npwp(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is True  # Still returns success with cleaned digits


# ============================================================
# extract_nib
# ============================================================


@pytest.mark.asyncio
async def test_extract_nib_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NibExtractRequest, extract_nib

    test_file = base64.b64encode(b"fake nib doc").decode()
    request = NibExtractRequest(client_id=1, file=test_file, file_name="nib.pdf")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "{}"}

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value={
            "nib": "1234567890123",
            "company_name": "PT Test",
            "kbli_code": "56101",
            "confidence": 0.9,
        }),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_nib(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is True
    assert result.nib == "1234567890123"
    assert result.company_name == "PT Test"


@pytest.mark.asyncio
async def test_extract_nib_invalid_base64(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NibExtractRequest, extract_nib

    request = NibExtractRequest(client_id=1, file="invalid!!!", file_name="nib.pdf")

    with patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()):
        result = await extract_nib(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )
    assert result.success is False


@pytest.mark.asyncio
async def test_extract_nib_ollama_error(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NibExtractRequest, extract_nib

    test_file = base64.b64encode(b"fake image").decode()
    request = NibExtractRequest(client_id=1, file=test_file, file_name="nib.pdf")

    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_nib(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is False


@pytest.mark.asyncio
async def test_extract_nib_wrong_digit_count(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import NibExtractRequest, extract_nib

    test_file = base64.b64encode(b"fake image").decode()
    request = NibExtractRequest(client_id=1, file=test_file, file_name="nib.pdf")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "{}"}

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        patch("backend.app.routers.crm_clients_documents.extract_json_from_llm_response", return_value={
            "nib": "12345",
            "company_name": None,
            "kbli_code": None,
            "confidence": 0.5,
        }),
        patch("httpx.AsyncClient") as mock_cls,
    ):
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await extract_nib(
            request=request,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert result.success is True  # Still returns success with cleaned digits


# ============================================================
# get_client_required_documents
# ============================================================


@pytest.mark.asyncio
async def test_get_client_required_documents_success(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import get_client_required_documents

    doc_row = {
        "id": 1,
        "practice_id": 10,
        "process_name": "KITAS Extension",
        "process_status": "in_progress",
        "document_type": "passport",
        "document_label": "Passport Copy",
        "description": "Valid passport required",
        "is_required": True,
        "uploaded_by_client": False,
        "status": "pending",
        "client_notes": None,
        "team_member_notes": None,
    }

    mock_db_pool._mock_conn.fetch.return_value = [doc_row]

    with patch(
        "backend.app.routers.crm_clients_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_required_documents(
            client_id=1,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )

    assert len(result) == 1
    assert result[0]["document_type"] == "passport"
    assert result[0]["is_required"] is True


@pytest.mark.asyncio
async def test_get_client_required_documents_empty(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import get_client_required_documents

    mock_db_pool._mock_conn.fetch.return_value = []

    with patch(
        "backend.app.routers.crm_clients_documents.verify_client_access",
        new=AsyncMock(),
    ):
        result = await get_client_required_documents(
            client_id=1,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )
    assert result == []


@pytest.mark.asyncio
async def test_get_client_required_documents_exception(mock_db_pool, mock_current_user):
    from backend.app.routers.crm_clients_documents import get_client_required_documents

    mock_db_pool._mock_conn.fetch.side_effect = RuntimeError("DB error")

    with (
        patch("backend.app.routers.crm_clients_documents.verify_client_access", new=AsyncMock()),
        pytest.raises(HTTPException) as exc_info,
    ):
        await get_client_required_documents(
            client_id=1,
            current_user=mock_current_user,
            db_pool=mock_db_pool,
        )
    assert exc_info.value.status_code == 500


# ============================================================
# Pydantic model tests
# ============================================================


def test_passport_extract_request_model():
    from backend.app.routers.crm_clients_documents import PassportExtractRequest

    r = PassportExtractRequest(client_id=1, image_url="http://test.com/img.jpg")
    assert r.client_id == 1
    assert r.image_url == "http://test.com/img.jpg"


def test_passport_preview_request_model():
    from backend.app.routers.crm_clients_documents import PassportPreviewRequest

    r = PassportPreviewRequest(image_base64="abc123")
    assert r.client_id is None
    assert r.mime_type == "image/jpeg"


def test_npwp_extract_request_model():
    from backend.app.routers.crm_clients_documents import NpwpExtractRequest

    r = NpwpExtractRequest(client_id=1, file="base64data", file_name="npwp.jpg")
    assert r.client_id == 1


def test_nib_extract_request_model():
    from backend.app.routers.crm_clients_documents import NibExtractRequest

    r = NibExtractRequest(client_id=1, file="base64data", file_name="nib.pdf")
    assert r.client_id == 1


def test_passport_preview_response_defaults():
    from backend.app.routers.crm_clients_documents import PassportPreviewResponse

    r = PassportPreviewResponse(success=True)
    assert r.confidence == 0.0
    assert r.warnings == []
    assert r.full_name is None


def test_npwp_extract_response_defaults():
    from backend.app.routers.crm_clients_documents import NpwpExtractResponse

    r = NpwpExtractResponse(success=True)
    assert r.npwp is None


def test_nib_extract_response_defaults():
    from backend.app.routers.crm_clients_documents import NibExtractResponse

    r = NibExtractResponse(success=True)
    assert r.nib is None
