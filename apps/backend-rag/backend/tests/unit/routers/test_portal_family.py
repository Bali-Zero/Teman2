"""Tests for portal family endpoint."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.routers.portal_family import _is_adult, _shape_member, router


def test_is_adult_with_dob_18_plus() -> None:
    assert _is_adult(date(1990, 5, 10)) is True


def test_is_adult_with_minor_dob() -> None:
    assert _is_adult(date(date.today().year - 10, 1, 1)) is False


def test_is_adult_none_dob_defaults_true() -> None:
    assert _is_adult(None) is True


def test_shape_member_serializes_dates() -> None:
    row = {
        "id": 1,
        "full_name": "Jane",
        "relationship": "spouse",
        "date_of_birth": date(1992, 4, 5),
        "nationality": "IT",
        "passport_number": "AB123",
        "passport_expiry": date(2030, 1, 1),
        "current_visa_type": "KITAS",
        "visa_expiry": date(2027, 6, 1),
        "email": "j@example.com",
        "phone": "628111",
    }
    shaped = _shape_member(row)
    assert shaped["is_adult"] is True
    assert shaped["date_of_birth"] == "1992-04-05"
    assert shaped["visa_expiry"] == "2027-06-01"


@pytest.mark.asyncio
async def test_list_family_splits_adults_and_minors() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": 1,
            "full_name": "Jane",
            "relationship": "spouse",
            "date_of_birth": date(1992, 4, 5),
            "nationality": "IT",
            "passport_number": "AB",
            "passport_expiry": None,
            "current_visa_type": None,
            "visa_expiry": None,
            "email": None,
            "phone": None,
        },
        {
            "id": 2,
            "full_name": "Kid",
            "relationship": "child",
            "date_of_birth": date(date.today().year - 8, 1, 1),
            "nationality": "IT",
            "passport_number": "KP",
            "passport_expiry": None,
            "current_visa_type": None,
            "visa_expiry": None,
            "email": None,
            "phone": None,
        },
    ]

    class _PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _PoolCtx()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[get_database_pool] = lambda: _Pool()

    tc = TestClient(app)
    r = tc.get("/api/portal/family")
    assert r.status_code == 200
    body = r.json()
    assert len(body["adults"]) == 1
    assert body["adults"][0]["full_name"] == "Jane"
    assert len(body["minors"]) == 1
    assert body["minors"][0]["full_name"] == "Kid"


@pytest.mark.asyncio
async def test_list_family_graceful_on_missing_table() -> None:
    mock_conn = AsyncMock()
    mock_conn.fetch.side_effect = Exception(
        "relation 'client_family_members' does not exist"
    )

    class _PoolCtx:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, *a):
            return False

    class _Pool:
        def acquire(self):
            return _PoolCtx()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_client] = lambda: {"client_id": 42}
    app.dependency_overrides[get_database_pool] = lambda: _Pool()

    tc = TestClient(app)
    r = tc.get("/api/portal/family")
    assert r.status_code == 200
    assert r.json() == {"adults": [], "minors": []}
