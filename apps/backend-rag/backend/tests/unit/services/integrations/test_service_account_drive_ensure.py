"""Tests for ServiceAccountDriveService.ensure_client_folder.

Regression suite for the duplicate-client-folder bug (2026-06-11): the POST
/api/clients background task and the passport-upload endpoint both saw
`clients.google_drive_folder_id IS NULL` and each created a root folder in
Drive. `ensure_client_folder` is the idempotent chokepoint: a per-client
pg advisory lock + re-check + Drive-side reuse guarantees at most one root.

The fake pool below emulates the two load-bearing Postgres behaviors:
  - `pg_advisory_lock/unlock($1, $2)` → an asyncio.Lock (serialization)
  - `SELECT/UPDATE clients.google_drive_folder_id` → shared dict (visibility)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.services.integrations.service_account_drive_service import (
    ServiceAccountDriveService,
)


class _FakeConn:
    def __init__(self, state: dict[str, Any], lock: asyncio.Lock) -> None:
        self._state = state
        self._lock = lock

    async def execute(self, sql: str, *args: Any) -> str:
        if "pg_advisory_lock" in sql:
            await self._lock.acquire()
            return "SELECT 1"
        if "pg_advisory_unlock" in sql:
            self._lock.release()
            return "SELECT 1"
        if "UPDATE clients SET google_drive_folder_id" in sql:
            self._state["google_drive_folder_id"] = args[0]
            return "UPDATE 1"
        return "OK"

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if "google_drive_folder_id" in sql:
            return self._state.get("google_drive_folder_id")
        return None


class _FakePool:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def _ctx(self):
        yield _FakeConn(self.state, self._lock)

    def acquire(self):
        return self._ctx()


def _make_service() -> ServiceAccountDriveService:
    """Build a service instance without touching real Google credentials."""
    svc = ServiceAccountDriveService.__new__(ServiceAccountDriveService)
    svc._parent_folder_for_client_type = lambda client_type: "PARENT_FOLDER"  # type: ignore[method-assign]
    svc.find_folder = AsyncMock(return_value=None)  # type: ignore[method-assign]
    svc._create_standard_subfolders = AsyncMock(return_value={})  # type: ignore[method-assign]

    async def _slow_create(name: str, parent_id: str | None = None, user_id: str | None = None):
        # Simulate Drive API latency so concurrent callers genuinely overlap.
        await asyncio.sleep(0.05)
        return {"id": "ROOT_1", "webViewLink": "https://drive.example/ROOT_1"}

    svc.create_folder = AsyncMock(side_effect=_slow_create)  # type: ignore[method-assign]
    return svc


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_ensure_creates_exactly_one_folder() -> None:
    """Two concurrent callers (create background task + passport upload) must
    produce ONE Drive root folder — the second waits on the lock and reuses."""
    svc = _make_service()
    pool = _FakePool()

    results = await asyncio.gather(
        svc.ensure_client_folder(
            client_id=11999, client_name="Mario Rossi", client_type="individual", db_pool=pool
        ),
        svc.ensure_client_folder(
            client_id=11999, client_name="Mario Rossi", client_type="individual", db_pool=pool
        ),
    )

    assert svc.create_folder.await_count == 1
    assert {r["root_folder_id"] for r in results} == {"ROOT_1"}
    assert sorted(r["created"] for r in results) == [False, True]
    assert pool.state["google_drive_folder_id"] == "ROOT_1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_returns_existing_without_drive_calls() -> None:
    svc = _make_service()
    pool = _FakePool()
    pool.state["google_drive_folder_id"] = "ALREADY_THERE"

    result = await svc.ensure_client_folder(
        client_id=42, client_name="Alice", client_type="individual", db_pool=pool
    )

    assert result["created"] is False
    assert result["root_folder_id"] == "ALREADY_THERE"
    svc.create_folder.assert_not_awaited()
    svc.find_folder.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_reuses_orphan_twin_found_in_drive() -> None:
    """If a twin "{id}_{name}" folder already exists in Drive (orphan from the
    pre-fix era), ensure must adopt it instead of creating another one."""
    svc = _make_service()
    svc.find_folder = AsyncMock(  # type: ignore[method-assign]
        return_value={"id": "ORPHAN_TWIN", "webViewLink": "https://drive.example/ORPHAN_TWIN"}
    )
    pool = _FakePool()

    result = await svc.ensure_client_folder(
        client_id=7, client_name="Bob", client_type="company", db_pool=pool
    )

    assert result["created"] is False
    assert result["root_folder_id"] == "ORPHAN_TWIN"
    assert pool.state["google_drive_folder_id"] == "ORPHAN_TWIN"
    svc.create_folder.assert_not_awaited()
    # Adopting an existing root must NOT rebuild subfolders blindly.
    svc._create_standard_subfolders.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_creates_and_builds_subfolders_when_missing() -> None:
    svc = _make_service()
    pool = _FakePool()

    result = await svc.ensure_client_folder(
        client_id=8, client_name="Carla", client_type="individual", db_pool=pool
    )

    assert result["created"] is True
    assert result["root_folder_id"] == "ROOT_1"
    assert pool.state["google_drive_folder_id"] == "ROOT_1"
    svc._create_standard_subfolders.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lock_released_when_drive_create_fails() -> None:
    """A Drive failure must not leave the advisory lock held."""
    svc = _make_service()
    svc.create_folder = AsyncMock(side_effect=RuntimeError("drive down"))  # type: ignore[method-assign]
    pool = _FakePool()

    with pytest.raises(RuntimeError):
        await svc.ensure_client_folder(
            client_id=9, client_name="Dora", client_type="individual", db_pool=pool
        )

    assert not pool._lock.locked()
