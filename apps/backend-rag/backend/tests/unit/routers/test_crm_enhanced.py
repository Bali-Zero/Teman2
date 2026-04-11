"""
Unit tests for backend/app/routers/crm_enhanced.py

Tests route handler functions directly (no TestClient) with mocked dependencies.
Covers all endpoints and helper functions:
- GET  /clients/{id}/profile       -> get_client_profile
- PATCH /clients/{id}/profile      -> update_client_profile
- GET  /companies/by-client/{id}   -> get_client_companies
- GET  /companies/{id}/documents   -> get_company_documents
- GET  /clients/{id}/family        -> get_family_members
- POST /clients/{id}/family        -> create_family_member
- PATCH /clients/{id}/family/{mid} -> update_family_member
- DELETE /clients/{id}/family/{mid}-> delete_family_member

Plus helper functions:
- _auto_ocr_passport
- _auto_ocr_visa
- _auto_ocr_nib
- _auto_ocr_npwp
- _auto_ocr_company_profile
- _dispatch_ocr_by_folder
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_user() -> dict[str, Any]:
    return {
        "id": "admin-uuid-1",
        "email": "zero@balizero.com",
        "role": "admin",
        "full_name": "Admin User",
    }


@pytest.fixture
def client_row() -> dict[str, Any]:
    return {
        "id": 42, "uuid": "test-uuid", "full_name": "Test Client",
        "email": "client@example.com", "phone": "+628123456", "whatsapp": "+628123456",
        "nationality": "Australian", "passport_number": "PA123456",
        "passport_expiry": "2028-01-01", "date_of_birth": "1990-01-01",
        "gender": "M", "avatar_url": None, "company_name": None,
        "google_drive_folder_id": None, "status": "active", "client_type": "individual",
        "assigned_to": "team@balizero.com", "address": "Bali, Indonesia",
        "notes": None, "tags": None, "custom_fields": None,
        "first_contact_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "last_interaction_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# GET /clients/{id}/profile
# ---------------------------------------------------------------------------


class TestGetClientProfile:
    @pytest.mark.asyncio
    async def test_profile_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict, client_row: dict) -> None:
        from backend.app.routers.crm_enhanced import get_client_profile

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            mock_db_conn.fetchrow = AsyncMock(return_value=client_row)
            mock_db_conn.fetch = AsyncMock(return_value=[])
            result = await get_client_profile(client_id=42, pool=mock_db_pool, current_user=admin_user)

        assert "client" in result
        assert "family_members" in result
        assert "stats" in result
        assert result["stats"]["family_count"] == 0

    @pytest.mark.asyncio
    async def test_profile_not_found(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import get_client_profile

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            mock_db_conn.fetchrow = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc_info:
                await get_client_profile(client_id=999, pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_profile_access_denied(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import get_client_profile

        user = {"id": "u1", "email": "nobody@example.com", "role": "team", "full_name": "Nobody"}
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock(side_effect=HTTPException(403, "Forbidden"))):
            with pytest.raises(HTTPException) as exc_info:
                await get_client_profile(client_id=42, pool=mock_db_pool, current_user=user)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_profile_stats_counts(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict, client_row: dict) -> None:
        from backend.app.routers.crm_enhanced import get_client_profile

        alerts = [
            {"alert_color": "expired", "entity_type": "p", "entity_id": 1, "entity_name": "X", "document_type": "pp", "expiry_date": "2025-01-01", "days_until_expiry": -100},
            {"alert_color": "red", "entity_type": "v", "entity_id": 2, "entity_name": "Y", "document_type": "v", "expiry_date": "2026-06-01", "days_until_expiry": 60},
            {"alert_color": "yellow", "entity_type": "p", "entity_id": 3, "entity_name": "Z", "document_type": "pp", "expiry_date": "2027-01-01", "days_until_expiry": 270},
        ]
        fetch_calls = [[], [], alerts, [], [], []]
        idx = [0]

        async def mock_fetch(*a, **k):
            i = idx[0]; idx[0] += 1
            return fetch_calls[i] if i < len(fetch_calls) else []

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            mock_db_conn.fetchrow = AsyncMock(return_value=client_row)
            mock_db_conn.fetch = AsyncMock(side_effect=mock_fetch)
            result = await get_client_profile(client_id=42, pool=mock_db_pool, current_user=admin_user)

        assert result["stats"]["expired_count"] == 1
        assert result["stats"]["red_alerts"] == 1
        assert result["stats"]["yellow_alerts"] == 1


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/profile
# ---------------------------------------------------------------------------


class TestUpdateClientProfile:
    @pytest.mark.asyncio
    async def test_update_avatar(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import ClientProfileUpdate, update_client_profile

        mock_db_conn.execute = AsyncMock(return_value=None)
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            result = await update_client_profile(client_id=42, data=ClientProfileUpdate(avatar_url="https://x.com/a.png"), pool=mock_db_pool, current_user=admin_user)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import ClientProfileUpdate, update_client_profile

        mock_db_conn.execute = AsyncMock(return_value=None)
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            data = ClientProfileUpdate(avatar_url="x", google_drive_folder_id="d", date_of_birth="1990-01-01", passport_expiry="2028-01-01", company_name="Test Co")
            result = await update_client_profile(client_id=42, data=data, pool=mock_db_pool, current_user=admin_user)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_update_no_fields(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import ClientProfileUpdate, update_client_profile

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            with pytest.raises(HTTPException) as exc_info:
                await update_client_profile(client_id=42, data=ClientProfileUpdate(), pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# GET /companies/by-client/{id}
# ---------------------------------------------------------------------------


class TestGetClientCompanies:
    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_client_companies

        mock_db_conn.fetch = AsyncMock(return_value=[{"link_id": 1, "company_name": "PT X"}])
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            result = await get_client_companies(client_id=42, pool=mock_db_pool, current_user=admin_user)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_client_companies

        mock_db_conn.fetch = AsyncMock(return_value=[])
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            result = await get_client_companies(client_id=42, pool=mock_db_pool, current_user=admin_user)
        assert result == []


# ---------------------------------------------------------------------------
# GET /companies/{id}/documents
# ---------------------------------------------------------------------------


class TestGetCompanyDocuments:
    @pytest.mark.asyncio
    async def test_all_docs(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_company_documents

        mock_db_conn.fetch = AsyncMock(return_value=[{"id": 1, "document_type": "akta"}])
        result = await get_company_documents(company_id=10, doc_type=None, pool=mock_db_pool, current_user=admin_user)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filtered(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_company_documents

        mock_db_conn.fetch = AsyncMock(return_value=[])
        result = await get_company_documents(company_id=10, doc_type="nib", pool=mock_db_pool, current_user=admin_user)
        assert result == []


# ---------------------------------------------------------------------------
# GET /clients/{id}/family
# ---------------------------------------------------------------------------


class TestGetFamilyMembers:
    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_family_members

        mock_db_conn.fetch = AsyncMock(return_value=[{"id": 1, "full_name": "Spouse"}])
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            result = await get_family_members(client_id=42, pool=mock_db_pool, current_user=admin_user)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_empty(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import get_family_members

        mock_db_conn.fetch = AsyncMock(return_value=[])
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            result = await get_family_members(client_id=42, pool=mock_db_pool, current_user=admin_user)
        assert result == []


# ---------------------------------------------------------------------------
# POST /clients/{id}/family
# ---------------------------------------------------------------------------


class TestCreateFamilyMember:
    @pytest.mark.asyncio
    async def test_create_basic(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberCreate, create_family_member

        mock_db_conn.fetchval = AsyncMock(return_value=99)
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            result = await create_family_member(client_id=42, data=FamilyMemberCreate(full_name="Jane", relationship="spouse"), pool=mock_db_pool, current_user=admin_user)
        assert result["id"] == 99 and result["success"]

    @pytest.mark.asyncio
    async def test_create_with_dates(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberCreate, create_family_member

        mock_db_conn.fetchval = AsyncMock(return_value=100)
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            data = FamilyMemberCreate(full_name="Kid", relationship="child", date_of_birth="2020-06-15", passport_expiry="2030-01-01", visa_expiry="2027-06-01")
            result = await create_family_member(client_id=42, data=data, pool=mock_db_pool, current_user=admin_user)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_create_invalid_dates(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberCreate, create_family_member

        mock_db_conn.fetchval = AsyncMock(return_value=101)
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            data = FamilyMemberCreate(full_name="P", relationship="sibling", date_of_birth="bad", passport_expiry="bad", visa_expiry="bad")
            result = await create_family_member(client_id=42, data=data, pool=mock_db_pool, current_user=admin_user)
        assert result["success"]


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/family/{mid}
# ---------------------------------------------------------------------------


class TestUpdateFamilyMember:
    @pytest.mark.asyncio
    async def test_update_name(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate, update_family_member

        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            result = await update_family_member(client_id=42, member_id=1, data=FamilyMemberUpdate(full_name="New"), pool=mock_db_pool, current_user=admin_user)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate, update_family_member

        mock_db_conn.execute = AsyncMock(return_value="UPDATE 0")
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await update_family_member(client_id=42, member_id=999, data=FamilyMemberUpdate(full_name="X"), pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_no_fields(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate, update_family_member

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            with pytest.raises(HTTPException) as exc_info:
                await update_family_member(client_id=42, member_id=1, data=FamilyMemberUpdate(), pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_with_dates(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate, update_family_member

        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            data = FamilyMemberUpdate(date_of_birth="1990-01-01", passport_expiry="2030-01-01", visa_expiry="2027-06-01")
            result = await update_family_member(client_id=42, member_id=1, data=data, pool=mock_db_pool, current_user=admin_user)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_update_empty_date(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate, update_family_member

        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            with pytest.raises(HTTPException) as exc_info:
                await update_family_member(client_id=42, member_id=1, data=FamilyMemberUpdate(date_of_birth=""), pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /clients/{id}/family/{mid}
# ---------------------------------------------------------------------------


class TestDeleteFamilyMember:
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from backend.app.routers.crm_enhanced import delete_family_member

        mock_db_conn.execute = AsyncMock(return_value="DELETE 1")
        with (
            patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()),
            patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()),
        ):
            result = await delete_family_member(client_id=42, member_id=1, pool=mock_db_pool, current_user=admin_user)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock, admin_user: dict) -> None:
        from fastapi import HTTPException
        from backend.app.routers.crm_enhanced import delete_family_member

        mock_db_conn.execute = AsyncMock(return_value="DELETE 0")
        with patch("backend.app.routers.crm_enhanced.verify_client_access", new=AsyncMock()):
            with pytest.raises(HTTPException) as exc_info:
                await delete_family_member(client_id=42, member_id=999, pool=mock_db_pool, current_user=admin_user)
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# OCR helpers
# ---------------------------------------------------------------------------


class TestAutoOCRPassport:
    @pytest.mark.asyncio
    async def test_client_not_found(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_passport
        mock_db_conn.fetchrow = AsyncMock(return_value=None)
        result = await _auto_ocr_passport(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_parse_fail(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_passport
        mock_db_conn.fetchrow = AsyncMock(return_value={"full_name": "X"})
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="bad")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=None),
        ):
            result = await _auto_ocr_passport(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_passport
        mock_db_conn.fetchrow = AsyncMock(return_value={"full_name": "X"})
        mock_db_conn.execute = AsyncMock()
        ext = {"passport_number": "P1", "expiry_date": "2028-01-01", "full_name": "X", "gender": "MALE", "date_of_birth": "1990-01-01", "birthplace": "Y", "nationality": "AU", "confidence": 0.9}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_passport(mock_db_pool, 42, "f1")
        assert result["success"]

    @pytest.mark.asyncio
    async def test_date_normalization(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_passport
        mock_db_conn.fetchrow = AsyncMock(return_value={"full_name": "X"})
        mock_db_conn.execute = AsyncMock()
        ext = {"passport_number": "P1", "expiry_date": "01-06-2028", "full_name": "X", "gender": "F", "date_of_birth": "15-03-1990", "confidence": 0.9}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_passport(mock_db_pool, 42, "f1")
        assert result["extracted"]["expiry_date"] == "2028-06-01"

    @pytest.mark.asyncio
    async def test_exception(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_passport
        mock_db_conn.fetchrow = AsyncMock(return_value={"full_name": "X"})
        with patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(side_effect=RuntimeError("err"))):
            result = await _auto_ocr_passport(mock_db_pool, 42, "f1")
        assert not result["success"]


class TestAutoOCRVisa:
    @pytest.mark.asyncio
    async def test_parse_fail(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_visa
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="bad")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=None),
        ):
            result = await _auto_ocr_visa(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_visa
        mock_db_conn.execute = AsyncMock()
        ext = {"visa_type": "KITAS", "visa_number": "V1", "expiry_date": "2027-12-31", "issue_date": "2026-01-01", "sponsor": "PT T", "confidence": 0.9}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_visa(mock_db_pool, 42, "f1", doc_id=5)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_exception(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_visa
        with patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(side_effect=RuntimeError("e"))):
            result = await _auto_ocr_visa(mock_db_pool, 42, "f1")
        assert not result["success"]


class TestAutoOCRNIB:
    @pytest.mark.asyncio
    async def test_parse_fail(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_nib
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="bad")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=None),
        ):
            result = await _auto_ocr_nib(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_nib
        mock_db_conn.execute = AsyncMock()
        mock_db_conn.fetchrow = AsyncMock(return_value={"id": 10})
        ext = {"nib_number": "NIB1", "company_name": "PT T"}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_nib(mock_db_pool, 42, "f1", doc_id=5)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_exception(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_nib
        with patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(side_effect=RuntimeError("e"))):
            result = await _auto_ocr_nib(mock_db_pool, 42, "f1")
        assert not result["success"]


class TestAutoOCRNPWP:
    @pytest.mark.asyncio
    async def test_parse_fail(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_npwp
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="bad")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=None),
        ):
            result = await _auto_ocr_npwp(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_company_update(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_npwp
        mock_db_conn.execute = AsyncMock()
        mock_db_conn.fetchrow = AsyncMock(return_value={"id": 10})
        ext = {"npwp_number": "N1", "kpp_name": "KPP B"}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_npwp(mock_db_pool, 42, "f1", doc_id=5)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_personal_update(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_npwp
        mock_db_conn.execute = AsyncMock()
        mock_db_conn.fetchrow = AsyncMock(return_value=None)
        ext = {"npwp_number": "N1"}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_npwp(mock_db_pool, 42, "f1")
        assert result["success"]


class TestAutoOCRCompanyProfile:
    @pytest.mark.asyncio
    async def test_parse_fail(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_company_profile
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="bad")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=None),
        ):
            result = await _auto_ocr_company_profile(mock_db_pool, 42, "f1")
        assert not result["success"]

    @pytest.mark.asyncio
    async def test_success(self, mock_db_pool: MagicMock, mock_db_conn: AsyncMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_company_profile
        mock_db_conn.execute = AsyncMock()
        mock_db_conn.fetchval = AsyncMock(side_effect=[10, "{}"])
        ext = {"company_name": "PT T", "akta_no": "AK1", "sk_no": "SK1", "registered_address": "Jl X", "shareholders": [{"name": "J"}], "authorized_capital": 1000000000}
        with (
            patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(return_value=(b"x", "image/jpeg"))),
            patch("backend.app.routers.crm_enhanced._gemini_ocr", new=AsyncMock(return_value="{}")),
            patch("backend.app.routers.crm_enhanced.extract_json_from_llm_response", return_value=ext),
            patch("backend.app.routers.crm_enhanced.to_jsonb", return_value="{}"),
        ):
            result = await _auto_ocr_company_profile(mock_db_pool, 42, "f1", doc_id=5)
        assert result["success"]

    @pytest.mark.asyncio
    async def test_exception(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _auto_ocr_company_profile
        with patch("backend.app.routers.crm_enhanced._download_drive_file", new=AsyncMock(side_effect=RuntimeError("e"))):
            result = await _auto_ocr_company_profile(mock_db_pool, 42, "f1")
        assert not result["success"]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TestPydanticModels:
    def test_family_create(self) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberCreate
        assert FamilyMemberCreate(full_name="T", relationship="spouse").full_name == "T"

    def test_family_update(self) -> None:
        from backend.app.routers.crm_enhanced import FamilyMemberUpdate
        assert FamilyMemberUpdate(full_name="U").full_name == "U"

    def test_doc_create(self) -> None:
        from backend.app.routers.crm_enhanced import DocumentCreate
        assert DocumentCreate(document_type="passport").document_type == "passport"

    def test_doc_update(self) -> None:
        from backend.app.routers.crm_enhanced import DocumentUpdate
        assert DocumentUpdate(status="verified").status == "verified"

    def test_profile_update(self) -> None:
        from backend.app.routers.crm_enhanced import ClientProfileUpdate
        assert ClientProfileUpdate(avatar_url="x").avatar_url == "x"


# ---------------------------------------------------------------------------
# _dispatch_ocr_by_folder
# ---------------------------------------------------------------------------


class TestDispatchOCR:
    @pytest.mark.asyncio
    async def test_delegates(self, mock_db_pool: MagicMock) -> None:
        from backend.app.routers.crm_enhanced import _dispatch_ocr_by_folder

        with patch("backend.services.documents.ocr_dispatcher_service.dispatch_ocr_by_folder", new=AsyncMock(return_value={"success": True})):
            result = await _dispatch_ocr_by_folder(db_pool=mock_db_pool, client_id=42, file_id="a", folder_name="P", filename="p.jpg", doc_id=1, document_type="passport")
        assert result["success"]
