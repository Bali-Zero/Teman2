"""
Coverage tests for backend/app/routers/crm_enhanced.py

Targeting uncovered endpoints and edge cases:
- GET  /api/crm/clients/{id}/profile — enhanced profile (async, edge cases)
- PATCH /api/crm/clients/{id}/profile — update edge cases
- GET  /api/crm/companies/by-client/{id}
- GET  /api/crm/companies/{id}/documents
- GET  /api/crm/clients/{id}/family — list family members
- POST /api/crm/clients/{id}/family — create family member
- PATCH /api/crm/clients/{id}/family/{member_id}
- DELETE /api/crm/clients/{id}/family/{member_id}
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client(mock_current_user, mock_db_pool):
    """FastAPI app with dependency overrides for crm_enhanced router."""
    from backend.app.dependencies import get_current_user, get_database_pool
    from backend.app.main_cloud import app

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def sample_client_db():
    """Mock client row as returned by asyncpg fetchrow."""
    return {
        "id": 42,
        "uuid": "uuid-42",
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+62812345678",
        "whatsapp": "+62812345678",
        "nationality": "US",
        "passport_number": "C12345678",
        "passport_expiry": datetime(2028, 6, 15).date(),
        "date_of_birth": datetime(1985, 3, 20).date(),
        "gender": "M",
        "avatar_url": None,
        "company_name": "PT Example",
        "google_drive_folder_id": "folder-123",
        "status": "active",
        "client_type": "individual",
        "assigned_to": "test@balizero.com",
        "address": "Jl. Sunset Rd, Bali",
        "notes": None,
        "tags": [],
        "custom_fields": {},
        "first_contact_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_interaction_date": datetime(2026, 3, 15, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 15, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# GET /clients/{id}/profile — enhanced profile
# ---------------------------------------------------------------------------


class TestGetClientProfile:
    @pytest.mark.asyncio
    async def test_profile_success_full(self, app_client, mock_db_conn, sample_client_db):
        """Returns full profile with family, documents, alerts, practices, company links."""
        # verify_client_access → fetchrow for admin check
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"assigned_to": "test@balizero.com"},  # verify_client_access
                sample_client_db,  # main client query
            ]
        )
        # fetch calls: family, documents, alerts, practices, company_links, company_documents
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/42/profile")

        assert response.status_code == 200
        data = response.json()
        assert "client" in data
        assert "family_members" in data
        assert "documents" in data
        assert "expiry_alerts" in data
        assert "practices" in data
        assert "stats" in data

    @pytest.mark.asyncio
    async def test_profile_client_not_found(self, app_client, mock_db_conn):
        """Returns 404 when client does not exist."""
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"assigned_to": "test@balizero.com"},  # verify_client_access passes for admin
                None,  # main client query returns nothing
            ]
        )
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/999/profile")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_profile_stats_counts(self, app_client, mock_db_conn, sample_client_db):
        """Stats section correctly counts family, documents, etc."""
        mock_db_conn.fetchrow = AsyncMock(
            side_effect=[
                {"assigned_to": "test@balizero.com"},
                sample_client_db,
            ]
        )
        family_row = {
            "id": 1,
            "full_name": "Jane Doe",
            "relationship": "spouse",
            "date_of_birth": None,
            "nationality": "US",
            "passport_number": "A123",
            "passport_expiry": None,
            "current_visa_type": None,
            "visa_expiry": None,
            "email": None,
            "phone": None,
            "notes": None,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        # 6 fetch calls: family, documents, alerts, practices, company_links, company_docs
        mock_db_conn.fetch = AsyncMock(
            side_effect=[
                [family_row],  # family_members
                [],            # documents
                [],            # expiry_alerts
                [],            # practices
                [],            # company_links
                [],            # company_documents
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/42/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["family_count"] == 1
        assert data["stats"]["documents_count"] == 0


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/profile — update client profile
# ---------------------------------------------------------------------------


class TestUpdateClientProfile:
    @pytest.mark.asyncio
    async def test_update_avatar_success(self, app_client, mock_db_conn):
        """Updates avatar_url field."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/api/crm/clients/42/profile",
                    json={"avatar_url": "https://example.com/new-avatar.jpg"},
                )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_update_drive_folder(self, app_client, mock_db_conn):
        """Updates google_drive_folder_id."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/api/crm/clients/42/profile",
                    json={"google_drive_folder_id": "new-folder-id-xyz"},
                )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_no_fields(self, app_client, mock_db_conn):
        """Empty update body → 400 (no fields to update)."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.patch("/api/crm/clients/42/profile", json={})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_multiple_fields(self, app_client, mock_db_conn):
        """Updates multiple profile fields at once."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/api/crm/clients/42/profile",
                    json={
                        "date_of_birth": "1985-03-20",
                        "passport_expiry": "2030-01-01",
                        "company_name": "PT New Co",
                    },
                )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /companies/by-client/{id} and GET /companies/{id}/documents
# These routes also exist in the company_router module (prefix /api/crm/companies),
# which takes precedence in main_cloud.app. Test via isolated FastAPI app instead.
# ---------------------------------------------------------------------------


class TestCompaniesByClientIsolated:
    """Test crm_enhanced company endpoints via isolated FastAPI app (no conflict with company_router)."""

    @pytest.fixture
    def isolated_app(self, mock_current_user, mock_db_pool):
        from fastapi import FastAPI

        from backend.app.dependencies import get_current_user, get_database_pool
        from backend.app.routers.crm_enhanced import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        return app

    @pytest.mark.asyncio
    async def test_companies_by_client_success(self, isolated_app, mock_db_conn):
        """Returns companies linked to a client via isolated router."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        company_link = {
            "link_id": 1,
            "company_id": 10,
            "role": "director",
            "is_primary": True,
            "ownership_percentage": 60,
            "shares_count": 600,
            "start_date": None,
            "status": "active",
            "notes": None,
            "company_name": "PT Example Bali",
            "company_type": "PT PMA",
            "brand_name": None,
            "kbli_code": "55203",
            "kbli_description": "Villa",
            "nib": "1234567890",
            "npwp_company": None,
            "akta_pendirian_no": None,
            "akta_pendirian_date": None,
            "akta_perubahan_no": None,
            "akta_perubahan_date": None,
            "sk_menhumkam_no": None,
            "sk_menhumkam_date": None,
            "registered_address": "Bali",
            "office_address": None,
            "city": "Badung",
            "province": "Bali",
            "company_phone": None,
            "company_email": None,
            "company_status": "active",
            "setup_progress": 80,
            "custom_fields": {},
        }
        mock_db_conn.fetch = AsyncMock(return_value=[company_link])

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/by-client/42")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["company_name"] == "PT Example Bali"

    @pytest.mark.asyncio
    async def test_companies_by_client_empty(self, isolated_app, mock_db_conn):
        """Returns empty list when no companies linked."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/by-client/42")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_companies_by_client_not_found(self, isolated_app, mock_db_conn):
        """Returns 404 when client does not exist."""
        from fastapi import HTTPException

        mock_db_conn.fetchrow = AsyncMock(
            side_effect=HTTPException(status_code=404, detail="Client not found")
        )

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/by-client/999")

        assert response.status_code == 404


class TestCompanyDocumentsIsolated:
    """Test company documents endpoint via isolated FastAPI app."""

    @pytest.fixture
    def isolated_app(self, mock_current_user, mock_db_pool):
        from fastapi import FastAPI

        from backend.app.dependencies import get_current_user, get_database_pool
        from backend.app.routers.crm_enhanced import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        return app

    @pytest.mark.asyncio
    async def test_company_documents_success(self, isolated_app, mock_db_conn):
        """Returns documents for a company via isolated router."""
        doc_row = {
            "id": 1,
            "uuid": "doc-uuid-1",
            "company_id": 10,
            "document_type": "akta",
            "document_subtype": "pendirian",
            "document_number": "01/2024",
            "document_title": "Akta Pendirian",
            "description": None,
            "issue_date": None,
            "expiry_date": None,
            "status": "active",
            "google_drive_file_id": "gdrive-123",
            "google_drive_file_url": "https://drive.google.com/file/gdrive-123",
            "file_name": "akta.pdf",
            "file_size_kb": 512,
            "mime_type": "application/pdf",
            "is_verified": False,
            "verified_by": None,
            "verified_at": None,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        }
        mock_db_conn.fetch = AsyncMock(return_value=[doc_row])

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/10/documents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["document_type"] == "akta"

    @pytest.mark.asyncio
    async def test_company_documents_with_filter(self, isolated_app, mock_db_conn):
        """doc_type query param filters by document type."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/10/documents?doc_type=nib")

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_company_documents_empty(self, isolated_app, mock_db_conn):
        """Returns empty list when no documents found."""
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=isolated_app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/companies/10/documents")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /clients/{id}/family — list family members
# ---------------------------------------------------------------------------


class TestGetFamilyMembers:
    @pytest.mark.asyncio
    async def test_family_members_success(self, app_client, mock_db_conn):
        """Returns list of family members with alert fields."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        member_row = {
            "id": 1,
            "full_name": "Jane Doe",
            "relationship": "spouse",
            "date_of_birth": datetime(1987, 5, 10).date(),
            "nationality": "US",
            "passport_number": "B98765",
            "passport_expiry": datetime(2029, 12, 31).date(),
            "current_visa_type": "KITAS",
            "visa_expiry": datetime(2027, 6, 30).date(),
            "email": "jane@example.com",
            "phone": "+62811",
            "notes": None,
            "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "passport_alert": "green",
            "visa_alert": "green",
        }
        mock_db_conn.fetch = AsyncMock(return_value=[member_row])

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/42/family")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["relationship"] == "spouse"

    @pytest.mark.asyncio
    async def test_family_members_empty(self, app_client, mock_db_conn):
        """Returns empty list when client has no family members."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.fetch = AsyncMock(return_value=[])

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/42/family")

        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# POST /clients/{id}/family — create family member
# ---------------------------------------------------------------------------


class TestCreateFamilyMember:
    @pytest.mark.asyncio
    async def test_create_family_member_success(self, app_client, mock_db_conn):
        """Creates a family member and returns id."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.fetchval = AsyncMock(return_value=99)

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/crm/clients/42/family",
                    json={
                        "full_name": "Jane Doe",
                        "relationship": "spouse",
                        "nationality": "US",
                    },
                )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 99
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_create_family_member_with_dates(self, app_client, mock_db_conn):
        """Creates a family member with date fields."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.fetchval = AsyncMock(return_value=100)

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.post(
                    "/api/crm/clients/42/family",
                    json={
                        "full_name": "Child One",
                        "relationship": "child",
                        "date_of_birth": "2015-08-22",
                        "passport_expiry": "2030-01-01",
                        "visa_expiry": "2027-06-30",
                    },
                )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_create_family_member_missing_name(self, app_client):
        """Missing required full_name → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/clients/42/family",
                json={"relationship": "child"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_family_member_missing_relationship(self, app_client):
        """Missing required relationship → 422."""
        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/crm/clients/42/family",
                json={"full_name": "Jane"},
            )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /clients/{id}/family/{member_id}
# ---------------------------------------------------------------------------


class TestUpdateFamilyMember:
    @pytest.mark.asyncio
    async def test_update_family_member_success(self, app_client, mock_db_conn):
        """Updates a family member field."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/api/crm/clients/42/family/1",
                    json={"passport_number": "NEW123", "nationality": "AU"},
                )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_update_family_member_not_found(self, app_client, mock_db_conn):
        """Returns 404 when member doesn't exist."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 0")

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.patch(
                "/api/crm/clients/42/family/999",
                json={"passport_number": "NEW123"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_family_member_no_fields(self, app_client, mock_db_conn):
        """Empty body → 400 (no fields to update)."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.patch("/api/crm/clients/42/family/1", json={})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_family_member_date_field(self, app_client, mock_db_conn):
        """Date string field is correctly converted."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="UPDATE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.patch(
                    "/api/crm/clients/42/family/1",
                    json={"passport_expiry": "2032-12-31"},
                )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /clients/{id}/family/{member_id}
# ---------------------------------------------------------------------------


class TestDeleteFamilyMember:
    @pytest.mark.asyncio
    async def test_delete_family_member_success(self, app_client, mock_db_conn):
        """Successfully deletes a family member."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="DELETE 1")

        with patch("backend.app.routers.crm_enhanced.invalidate_cache", new=AsyncMock()):
            async with AsyncClient(
                transport=ASGITransport(app=app_client), base_url="http://test"
            ) as ac:
                response = await ac.delete("/api/crm/clients/42/family/1")

        assert response.status_code == 200
        assert response.json()["success"] is True

    @pytest.mark.asyncio
    async def test_delete_family_member_not_found(self, app_client, mock_db_conn):
        """Returns 404 when member doesn't exist."""
        mock_db_conn.fetchrow = AsyncMock(
            return_value={"assigned_to": "test@balizero.com"}
        )
        mock_db_conn.execute = AsyncMock(return_value="DELETE 0")

        async with AsyncClient(
            transport=ASGITransport(app=app_client), base_url="http://test"
        ) as ac:
            response = await ac.delete("/api/crm/clients/42/family/999")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Access Control: non-admin user without access → 403/404
# ---------------------------------------------------------------------------


class TestAccessControl:
    @pytest.mark.asyncio
    async def test_profile_non_admin_no_access(self):
        """Non-admin user without assignment to client gets 403/404."""
        from backend.app.dependencies import get_current_user, get_database_pool
        from backend.app.main_cloud import app

        other_user = {
            "id": "other-uuid",
            "email": "other@example.com",
            "role": "team",
            "full_name": "Other User",
        }

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        # verify_client_access: client exists but assigned to someone else
        mock_conn.fetchrow = AsyncMock(
            return_value={"id": 42, "assigned_to": "different@balizero.com"}
        )
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire = MagicMock(return_value=acquire_cm)

        app.dependency_overrides[get_current_user] = lambda: other_user
        app.dependency_overrides[get_database_pool] = lambda: mock_pool

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/crm/clients/42/profile")

        app.dependency_overrides.clear()
        # Either 403 (forbidden) or 404 (not found) depending on verify_client_access
        assert response.status_code in (403, 404)
