"""
HTTP-level tests for the typed request bodies on company_router.

Each test drives the real FastAPI route with a fake pool, so the assertions are
about what reaches the driver: a date string arrives as datetime.date, an
explicit null is written as NULL, and bad input stops at 422 before any SQL.
The pool is a fake: these tests do not prove the database round-trip. Read-back
is verified after deploy, on a TEST company.
"""

import os
from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock

import pytest

# Set env vars before imports (same block as test_company_router.py)
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

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.dependencies import get_current_user, get_database_pool  # noqa: E402
from backend.app.modules.crm import company_router as cr  # noqa: E402

COMPANIES = "/api/crm/companies"


class FakeConn:
    def __init__(self) -> None:
        self.fetchrow = AsyncMock()
        self.fetchval = AsyncMock(return_value=1)
        self.execute = AsyncMock()


class FakePool:
    def __init__(self, conn: FakeConn) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


@pytest.fixture
def conn() -> FakeConn:
    return FakeConn()


@pytest.fixture
def client(conn: FakeConn, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(cr, "is_crm_admin", lambda user: True)
    monkeypatch.setattr(cr, "verify_client_access", AsyncMock())
    app = FastAPI()
    app.include_router(cr.router)
    app.dependency_overrides[get_database_pool] = lambda: FakePool(conn)
    app.dependency_overrides[get_current_user] = lambda: {"email": "test@balizero.com"}
    return TestClient(app)


def _last_sql(conn: FakeConn) -> tuple[str, list]:
    args = conn.fetchrow.await_args.args
    return args[0], list(args[1:])


# ---------------------------------------------------------------- create


def test_create_empty_body_is_422_and_runs_no_sql(client, conn):
    r = client.post(COMPANIES, json={})
    assert r.status_code == 422
    conn.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("name", ["", "   ", None])
def test_create_blank_or_null_name_is_422(client, conn, name):
    r = client.post(COMPANIES, json={"company_name": name})
    assert r.status_code == 422
    conn.fetchrow.assert_not_awaited()


def test_create_binds_values_and_keeps_old_leniency(client, conn):
    conn.fetchrow.return_value = {
        "id": 7,
        "uuid": "u-7",
        "company_name": "PT Test",
        "company_type": "PT PMA",
        "status": "active",
    }
    r = client.post(
        COMPANIES,
        json={"company_name": "PT Test", "kbli_code": 62019, "unknown_key": "ignored"},
    )
    assert r.status_code == 200
    _, params = _last_sql(conn)
    assert params[0] == "PT Test"
    assert params[1] == "PT PMA"  # default company_type
    assert params[2] == "62019"  # number accepted as text, as before


def test_create_null_company_type_gets_default(client, conn):
    conn.fetchrow.return_value = {
        "id": 8,
        "uuid": "u-8",
        "company_name": "PT Test",
        "company_type": "PT PMA",
        "status": "active",
    }
    r = client.post(COMPANIES, json={"company_name": "PT Test", "company_type": None})
    assert r.status_code == 200
    _, params = _last_sql(conn)
    assert params[1] == "PT PMA"


# ---------------------------------------------------------------- update

UPDATED = {"id": 4157, "company_name": "PT Test"}


def test_update_date_string_is_bound_as_date(client, conn):
    conn.fetchrow.return_value = UPDATED
    r = client.patch(f"{COMPANIES}/4157", json={"akta_pendirian_date": "2026-09-01"})
    assert r.status_code == 200
    sql, params = _last_sql(conn)
    assert "akta_pendirian_date = $1" in sql
    assert params[0] == date(2026, 9, 1)


@pytest.mark.parametrize("value", [None, ""])
def test_update_null_or_empty_date_clears_the_column(client, conn, value):
    conn.fetchrow.return_value = UPDATED
    r = client.patch(f"{COMPANIES}/4157", json={"sk_menhumkam_date": value})
    assert r.status_code == 200
    sql, params = _last_sql(conn)
    assert "sk_menhumkam_date = $1" in sql
    assert params[0] is None


def test_update_writes_only_the_fields_sent(client, conn):
    conn.fetchrow.return_value = UPDATED
    r = client.patch(f"{COMPANIES}/4157", json={"city": "Denpasar"})
    assert r.status_code == 200
    sql, params = _last_sql(conn)
    assert "city = $1" in sql
    assert "akta_pendirian_date" not in sql
    assert params[0] == "Denpasar"
    assert params[-1] == 4157


@pytest.mark.parametrize(
    "body",
    [
        {"akta_pendirian_date": "01/09/2026"},
        {"company_name": ""},
        {"company_name": "   "},
        {"company_name": None},
        {"company_type": None},
        {"status": None},
    ],
)
def test_update_invalid_body_is_422_before_sql(client, conn, body):
    r = client.patch(f"{COMPANIES}/4157", json=body)
    assert r.status_code == 422
    conn.fetchrow.assert_not_awaited()


@pytest.mark.parametrize("body", [{}, {"not_a_column": 1}])
def test_update_with_no_known_fields_is_400(client, conn, body):
    r = client.patch(f"{COMPANIES}/4157", json=body)
    assert r.status_code == 400
    conn.fetchrow.assert_not_awaited()


# ---------------------------------------------------------------- link


def test_link_start_date_string_is_bound_as_date(client, conn):
    conn.fetchrow.side_effect = [None, {"id": 55}]  # no existing link, then INSERT
    r = client.post(f"{COMPANIES}/4157/clients/12414/link", json={"start_date": "2026-09-01"})
    assert r.status_code == 200
    params = list(conn.fetchrow.await_args_list[-1].args[1:])
    # client_id, company_id, role, is_primary, ownership_percentage, shares_count, start_date
    assert params[2] == "shareholder"
    assert params[3] is False
    assert params[6] == date(2026, 9, 1)


# ---------------------------------------------------------------- documents


def test_document_dates_are_bound_as_dates(client, conn):
    conn.fetchrow.return_value = {"id": 9, "uuid": "d-9"}
    r = client.post(
        f"{COMPANIES}/4157/documents",
        json={"document_type": "akta", "issue_date": "2026-09-01", "expiry_date": ""},
    )
    assert r.status_code == 200
    _, params = _last_sql(conn)
    # company_id, type, subtype, number, title, description, issue_date, expiry_date, ...
    assert params[6] == date(2026, 9, 1)
    assert params[7] is None


def test_document_bad_date_is_422_before_sql(client, conn):
    r = client.post(f"{COMPANIES}/4157/documents", json={"issue_date": "yesterday"})
    assert r.status_code == 422
    conn.fetchrow.assert_not_awaited()
