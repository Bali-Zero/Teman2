"""Unit tests for the scoped Drive intake adapter (drain_drive, m227).

PURE unit (no Postgres, no Drive): pool/conn faked, Drive API + download +
enqueue monkeypatched. Locked behaviours:

  * fail-safe: INTAKE_DRIVE_SCOPE_FOLDER_ID missing -> zero ingestion (the
    changes API is account-wide; unscoped would swallow the codebase mirror).
  * in-scope file -> enqueued with source='drive' + source_path relative to
    the scope root (folder-name signal for FASE-4 routing).
  * out-of-scope file (ancestor chain never reaches the scope id) -> skipped.
  * direct child of the scope root -> source_path is the bare file name.
  * google-native mime (incl. folders) -> skipped, no download.
  * cursor: new_page_token persisted via system_settings upsert.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.intake import drive_adapter as da
from backend.services.intake.enqueue import EnqueueResult


class FakeConn:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, query: str, *args: Any) -> Any:
        return None  # no stored cursor

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "INSERT 0 1"


class FakePool:
    def __init__(self) -> None:
        self.conn = FakeConn()

    def acquire(self) -> Any:
        conn = self.conn

        class _Ctx:
            async def __aenter__(self) -> FakeConn:
                return conn

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _Ctx()


class FakeDriveService:
    """Stands in for ServiceAccountDriveService (changes API only)."""

    def __init__(self, changes: list[dict[str, Any]], folders: dict[str, dict[str, Any]]) -> None:
        self._changes = changes
        self.folders = folders  # folder_id -> {id, name, parents}

    async def get_start_page_token(self) -> str:
        return "tok1"

    async def list_changes_since(self, page_token: str) -> dict[str, Any]:
        return {"changes": self._changes, "new_page_token": "tok2"}


def _patch_io(monkeypatch: pytest.MonkeyPatch, svc: FakeDriveService) -> list[dict[str, Any]]:
    """Patch download + folder lookup + enqueue; return the enqueue-call log."""
    calls: list[dict[str, Any]] = []

    async def _fake_download(drive_service: Any, file_id: str, dest: Any) -> int:
        return 123

    async def _fake_folder_meta(drive_service: Any, folder_id: str) -> dict[str, Any]:
        meta = svc.folders.get(folder_id)
        if meta is None:
            raise FileNotFoundError(folder_id)
        return meta

    async def _fake_enqueue(pool: Any, **kwargs: Any) -> EnqueueResult:
        calls.append(kwargs)
        return EnqueueResult(instance_id=1, queue_id=len(calls), was_new=True)

    monkeypatch.setattr(da, "_download_file", _fake_download)
    monkeypatch.setattr(da, "_folder_meta", _fake_folder_meta)
    monkeypatch.setattr(da, "enqueue", _fake_enqueue)
    return calls


def _change(file_id: str, name: str, parents: list[str], mime: str = "application/pdf") -> dict:
    return {"fileId": file_id, "removed": False,
            "file": {"id": file_id, "name": name, "mimeType": mime, "parents": parents}}


@pytest.mark.asyncio
async def test_no_scope_env_refuses_to_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", raising=False)
    svc = FakeDriveService([_change("f1", "passport.jpg", ["A"])], {})
    calls = _patch_io(monkeypatch, svc)
    counters = await da.drain_drive(FakePool(), drive_service=svc)
    assert counters["changes"] == 0
    assert counters["enqueued_new"] == 0
    assert calls == []


@pytest.mark.asyncio
async def test_in_scope_file_enqueued_with_source_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", "SCOPE")
    svc = FakeDriveService(
        [_change("f1", "passport.jpg", ["folderA"])],
        {"folderA": {"id": "folderA", "name": "BUDI", "parents": ["SCOPE"]}},
    )
    calls = _patch_io(monkeypatch, svc)
    counters = await da.drain_drive(FakePool(), drive_service=svc)
    assert counters["enqueued_new"] == 1
    assert counters["skipped_out_of_scope"] == 0
    assert calls[0]["source"] == "drive"
    assert calls[0]["source_ref"] == "drive:f1"
    assert calls[0]["source_path"] == "BUDI/passport.jpg"


@pytest.mark.asyncio
async def test_direct_child_of_scope_has_bare_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", "SCOPE")
    svc = FakeDriveService([_change("f2", "loose.pdf", ["SCOPE"])], {})
    calls = _patch_io(monkeypatch, svc)
    counters = await da.drain_drive(FakePool(), drive_service=svc)
    assert counters["enqueued_new"] == 1
    assert calls[0]["source_path"] == "loose.pdf"


@pytest.mark.asyncio
async def test_out_of_scope_file_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", "SCOPE")
    svc = FakeDriveService(
        [_change("f3", "repo-file.py", ["folderB"])],
        {
            "folderB": {"id": "folderB", "name": "repo", "parents": ["ROOT"]},
            "ROOT": {"id": "ROOT", "name": "My Drive", "parents": []},
        },
    )
    calls = _patch_io(monkeypatch, svc)
    counters = await da.drain_drive(FakePool(), drive_service=svc)
    assert counters["skipped_out_of_scope"] == 1
    assert counters["enqueued_new"] == 0
    assert calls == []


@pytest.mark.asyncio
async def test_google_native_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", "SCOPE")
    svc = FakeDriveService(
        [_change("d1", "BUDI", ["SCOPE"], mime="application/vnd.google-apps.folder")],
        {},
    )
    calls = _patch_io(monkeypatch, svc)
    counters = await da.drain_drive(FakePool(), drive_service=svc)
    assert counters["skipped_native"] == 1
    assert calls == []


@pytest.mark.asyncio
async def test_cursor_advanced_after_drain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTAKE_DRIVE_SCOPE_FOLDER_ID", "SCOPE")
    svc = FakeDriveService([_change("f4", "x.pdf", ["SCOPE"])], {})
    _patch_io(monkeypatch, svc)
    pool = FakePool()
    await da.drain_drive(pool, drive_service=svc)
    upserts = [q for q, _ in pool.conn.executed if "system_settings" in q]
    assert len(upserts) == 1
