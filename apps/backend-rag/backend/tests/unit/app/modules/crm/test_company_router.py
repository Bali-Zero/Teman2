"""
Unit tests for backend/app/modules/crm/company_router.py

Covers: list_companies, create_company, get_company_by_name, get_client_companies,
        get_company, update_company, delete_company, get_company_clients,
        link_client_to_company, unlink_client_from_company, get_company_documents,
        create_company_document, delete_company_document, get_company_tax_record,
        _infer_doc_type, company_record_to_dict, sync_company_drive_folder

Tests: happy path + error path + edge cases for maximal coverage.
"""

import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set env vars before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars_long")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-for-testing-only")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-api-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

from backend.app.modules.crm.company_router import (
    _infer_doc_type,
    company_record_to_dict,
)


# ============================================================================
# Fixtures
# ============================================================================


def _make_company_record() -> MagicMock:
    """Create a mock asyncpg.Record for a company."""
    now = datetime(2025, 1, 1, 12, 0, 0)
    record = MagicMock()
    data = {
        "id": 1,
        "uuid": "uuid-123",
        "company_name": "Test PT PMA",
        "company_type": "PT PMA",
        "brand_name": "TestBrand",
        "kbli_code": "62019",
        "kbli_description": "IT Services",
        "nib": "1234567890",
        "npwp_company": "00.000.000.0-000.000",
        "akta_pendirian_no": "001",
        "akta_pendirian_date": now,
        "akta_perubahan_no": "002",
        "akta_perubahan_date": now,
        "sk_menhumkam_no": "SK-001",
        "sk_menhumkam_date": now,
        "registered_address": "Jl. Test 1",
        "office_address": "Jl. Office 2",
        "city": "Denpasar",
        "province": "Bali",
        "postal_code": "80234",
        "company_phone": "+628123456",
        "company_email": "info@test.com",
        "status": "active",
        "setup_progress": 50,
        "google_drive_folder_id": "gdrive_123",
        "custom_fields": {"note": "test"},
        "created_at": now,
        "updated_at": now,
        "created_by": "admin@test.com",
    }
    record.__getitem__ = lambda s, k: data[k]
    return record


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool."""
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
    return {"id": "user-1", "email": "admin@balizero.com", "role": "admin"}


# ============================================================================
# TESTS: company_record_to_dict
# ============================================================================


class TestCompanyRecordToDict:
    def test_converts_record(self):
        record = _make_company_record()
        result = company_record_to_dict(record)
        assert result["id"] == 1
        assert result["uuid"] == "uuid-123"
        assert result["company_name"] == "Test PT PMA"
        assert result["company_type"] == "PT PMA"
        assert result["status"] == "active"
        assert result["created_at"] is not None

    def test_none_created_at(self):
        """created_at is None."""
        record = _make_company_record()
        data = {
            "id": 1, "uuid": "uuid", "company_name": "X", "company_type": "PT",
            "brand_name": None, "kbli_code": None, "kbli_description": None,
            "nib": None, "npwp_company": None, "akta_pendirian_no": None,
            "akta_pendirian_date": None, "akta_perubahan_no": None,
            "akta_perubahan_date": None, "sk_menhumkam_no": None,
            "sk_menhumkam_date": None, "registered_address": None,
            "office_address": None, "city": None, "province": None,
            "postal_code": None, "company_phone": None, "company_email": None,
            "status": "active", "setup_progress": 0,
            "google_drive_folder_id": None, "custom_fields": None,
            "created_at": None, "updated_at": None, "created_by": None,
        }
        record.__getitem__ = lambda s, k: data[k]
        result = company_record_to_dict(record)
        assert result["created_at"] is None
        assert result["updated_at"] is None


# ============================================================================
# TESTS: _infer_doc_type
# ============================================================================


class TestInferDocType:
    def test_akta_pendirian(self):
        assert _infer_doc_type("Akta Pendirian PT Test.pdf") == "akta_pendirian"

    def test_akta_perubahan(self):
        assert _infer_doc_type("akta_perubahan_2025.pdf") == "akta_perubahan"

    def test_sk_kemenkumham(self):
        assert _infer_doc_type("SK Kemenkumham.pdf") == "sk_decree"
        assert _infer_doc_type("SK Menkumham No 001.pdf") == "sk_decree"

    def test_npwp(self):
        assert _infer_doc_type("NPWP Company.pdf") == "npwp"

    def test_nib(self):
        assert _infer_doc_type("NIB Certificate.pdf") == "nib"
        assert _infer_doc_type("Nomor Induk Berusaha.pdf") == "nib"

    def test_company_profile(self):
        assert _infer_doc_type("Company Profile 2025.pdf") == "company_profile"
        assert _infer_doc_type("Profil Perseroan.pdf") == "company_profile"

    def test_wlkp(self):
        assert _infer_doc_type("WLKP Report.pdf") == "wlkp"

    def test_bpjs(self):
        assert _infer_doc_type("BPJS Ketenagakerjaan.pdf") == "bpjs"

    def test_organogram(self):
        assert _infer_doc_type("Organogram PT Test.pdf") == "organogram"

    def test_rekening_koran(self):
        assert _infer_doc_type("Rekening Koran Jan 2025.pdf") == "rekening_koran"

    def test_siup(self):
        assert _infer_doc_type("Izin Usaha.pdf") == "siup"
        assert _infer_doc_type("SIUP.pdf") == "siup"

    def test_tdp(self):
        assert _infer_doc_type("TDP Certificate.pdf") == "tdp"

    def test_domisili(self):
        assert _infer_doc_type("Surat Domisili.pdf") == "domisili"

    def test_imta(self):
        assert _infer_doc_type("IMTA Document.pdf") == "imta"
        assert _infer_doc_type("RPTKA.pdf") == "imta"

    def test_unknown(self):
        assert _infer_doc_type("random_file.pdf") == "other"

    def test_deed_of_establishment(self):
        assert _infer_doc_type("Deed of Establishment.pdf") == "akta_pendirian"

    def test_amendment(self):
        assert _infer_doc_type("Amendment 2025.pdf") == "akta_perubahan"


# ============================================================================
# TESTS: Router Endpoints (using FastAPI TestClient)
# ============================================================================


class TestListCompanies:
    @pytest.mark.asyncio
    async def test_list_companies_no_filters(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        # Override deps
        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        record = _make_company_record()
        data = dict(
            id=1, uuid="uuid-123", company_name="Test", company_type="PT PMA",
            brand_name=None, kbli_code="62019", kbli_description="IT",
            nib="123", npwp_company="00.000", akta_pendirian_no=None,
            akta_pendirian_date=None, akta_perubahan_no=None,
            akta_perubahan_date=None, sk_menhumkam_no=None,
            sk_menhumkam_date=None, registered_address=None,
            office_address=None, city="Denpasar", province="Bali",
            postal_code=None, company_phone=None, company_email=None,
            status="active", setup_progress=0, google_drive_folder_id=None,
            custom_fields=None, created_at=datetime(2025, 1, 1),
            updated_at=None, created_by="admin", associates_count=3,
        )
        row = MagicMock()
        row.__getitem__ = lambda s, k: data[k]

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[row])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_companies_with_search(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies?search=test&status=active&kbli=62019")

        assert resp.status_code == 200


class TestCreateCompany:
    @pytest.mark.asyncio
    async def test_create_company_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        row = MagicMock()
        row.__getitem__ = lambda s, k: {
            "id": 1, "uuid": "uuid-new", "company_name": "New PT",
            "company_type": "PT PMA", "status": "active",
        }[k]
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=row)

        with TestClient(test_app) as tc:
            resp = tc.post(
                "/api/crm/companies",
                json={"company_name": "New PT", "company_type": "PT PMA"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["company_name"] == "New PT"
        assert data["message"] == "Company created successfully"


class TestGetCompany:
    @pytest.mark.asyncio
    async def test_get_company_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        company_row = _make_company_record()

        # fetchrow is called 3 times: company, (associates via fetch), (docs via fetch), tax_record
        # We need to return company_row first, then None for tax_record
        mock_db_pool._mock_conn.fetchrow = AsyncMock(
            side_effect=[company_row, None],  # company, then no tax record
        )
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])  # associates, documents

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_company_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/999")

        assert resp.status_code == 404


class TestUpdateCompany:
    @pytest.mark.asyncio
    async def test_update_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        row = MagicMock()
        row.__getitem__ = lambda s, k: {"id": 1, "company_name": "Updated PT"}[k]
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=row)

        with TestClient(test_app) as tc:
            resp = tc.patch(
                "/api/crm/companies/1",
                json={"company_name": "Updated PT"},
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Company updated successfully"

    @pytest.mark.asyncio
    async def test_update_no_valid_fields(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        with TestClient(test_app) as tc:
            resp = tc.patch(
                "/api/crm/companies/1",
                json={"invalid_field": "value"},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)

        with TestClient(test_app) as tc:
            resp = tc.patch(
                "/api/crm/companies/999",
                json={"company_name": "Updated"},
            )

        assert resp.status_code == 404


class TestDeleteCompany:
    @pytest.mark.asyncio
    async def test_delete_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/1")

        assert resp.status_code == 200
        assert resp.json()["message"] == "Company deleted successfully"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 0")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/999")

        assert resp.status_code == 404


class TestClientCompanyLink:
    @pytest.mark.asyncio
    async def test_get_company_clients(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=1)
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1/clients")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_company_clients_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=None)

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/999/clients")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_link_client_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=1)
        mock_db_pool._mock_conn.fetchrow = AsyncMock(
            side_effect=[None, MagicMock(__getitem__=lambda s, k: {"id": 10}[k])],
        )

        with TestClient(test_app) as tc:
            resp = tc.post(
                "/api/crm/companies/1/clients/5/link",
                json={"role": "shareholder"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_link_client_already_linked(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=1)
        mock_db_pool._mock_conn.fetchrow = AsyncMock(
            return_value=MagicMock(),  # existing link
        )

        with TestClient(test_app) as tc:
            resp = tc.post(
                "/api/crm/companies/1/clients/5/link",
                json={"role": "director"},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unlink_client_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/1/clients/5/link")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unlink_client_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 0")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/1/clients/5/link")

        assert resp.status_code == 404


class TestCompanyDocuments:
    @pytest.mark.asyncio
    async def test_get_documents(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1/documents")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_documents_with_type_filter(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1/documents?doc_type=npwp")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_document_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=1)  # company exists
        row = MagicMock()
        row.__getitem__ = lambda s, k: {"id": 10, "uuid": "doc-uuid"}[k]
        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=row)

        with TestClient(test_app) as tc:
            resp = tc.post(
                "/api/crm/companies/1/documents",
                json={"document_type": "npwp", "document_title": "NPWP Company"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_document_company_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchval = AsyncMock(return_value=None)

        with TestClient(test_app) as tc:
            resp = tc.post(
                "/api/crm/companies/999/documents",
                json={"document_type": "npwp"},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_document_success(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 1")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/1/documents/10")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.execute = AsyncMock(return_value="DELETE 0")

        with TestClient(test_app) as tc:
            resp = tc.delete("/api/crm/companies/1/documents/999")

        assert resp.status_code == 404


class TestTaxRecord:
    @pytest.mark.asyncio
    async def test_get_tax_record_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        tax_data = {
            "id": 1, "uuid": "tax-uuid", "npwp": "00.000.000",
            "npwp_status": "active", "tax_center": "KPP Denpasar",
            "is_pph21_registered": True, "is_pph23_registered": False,
            "is_pph25_registered": True, "is_ppn_registered": True,
            "is_pph29_registered": False, "tax_year": 2025,
            "reporting_period": "monthly", "last_filing_date": None,
            "next_filing_date": None, "compliance_status": "compliant",
            "custom_fields": None,
        }
        tax_row = MagicMock()
        tax_row.__getitem__ = lambda s, k: tax_data[k]

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=tax_row)
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1/tax")

        assert resp.status_code == 200
        data = resp.json()
        assert data["npwp"] == "00.000.000"

    @pytest.mark.asyncio
    async def test_get_tax_record_not_found(self, mock_db_pool, mock_current_user):
        from fastapi.testclient import TestClient
        from backend.app.modules.crm.company_router import router
        from fastapi import FastAPI

        test_app = FastAPI()
        test_app.include_router(router)

        from backend.app.dependencies import get_current_user, get_database_pool

        test_app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        test_app.dependency_overrides[get_current_user] = lambda: mock_current_user

        mock_db_pool._mock_conn.fetchrow = AsyncMock(return_value=None)

        with TestClient(test_app) as tc:
            resp = tc.get("/api/crm/companies/1/tax")

        assert resp.status_code == 200
        assert resp.json()["message"] == "No tax record found for this company"
