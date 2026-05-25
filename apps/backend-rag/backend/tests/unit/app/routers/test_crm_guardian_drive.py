from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from backend.app.routers import crm_guardian_drive


class FakeAcquire:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def __aenter__(self) -> Any:
        return self.conn

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


class FakePool:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(self) -> None:
        self.fetch_calls = 0

    async def fetchval(self, sql: str, table_name: str) -> str | None:
        assert "to_regclass" in sql
        return table_name

    async def fetchrow(self, sql: str) -> dict[str, int]:
        assert "crm_guardian_drive_metadata_snapshot" in sql
        return {"total": 3, "ok": 2, "errors": 1}

    async def fetch(self, sql: str, *args: object) -> list[dict[str, Any]]:
        self.fetch_calls += 1
        if "owner_domain" in sql:
            return [{"owner_domain": "gmail.com", "count": 2}]
        if "mime_type" in sql:
            return [{"mime_type": "application/pdf", "count": 2}]
        if "validation_status" in sql:
            return [{"validation_status": "ok", "count": 2}]
        return []


def fake_request(conn: Any) -> Any:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db_pool=FakePool(conn))))


@pytest.fixture(autouse=True)
def admin_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        crm_guardian_drive,
        "settings",
        SimpleNamespace(admin_emails_set={"admin@example.com"}),
    )


def test_require_admin_rejects_non_admin() -> None:
    with pytest.raises(HTTPException) as exc:
        crm_guardian_drive._require_admin({"email": "operator@example.com"})

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_validation_summary_returns_counts() -> None:
    response = await crm_guardian_drive.get_drive_validation_summary(
        fake_request(FakeConn()),
        current_user={"email": "admin@example.com"},
    )

    assert response.total == 3
    assert response.ok == 2
    assert response.errors == 1
    assert response.owner_domains[0].key == "gmail.com"
    assert response.mime_types[0].key == "application/pdf"
    assert response.statuses[0].key == "ok"


@pytest.mark.asyncio
async def test_require_table_reports_unmigrated_table() -> None:
    class MissingConn:
        async def fetchval(self, sql: str, table_name: str) -> None:
            return None

    with pytest.raises(HTTPException) as exc:
        await crm_guardian_drive._require_table(MissingConn(), "missing_table")

    assert exc.value.status_code == 503
    assert "missing_table" in exc.value.detail
