"""Drive-registered notes-type text files land hidden; every other file stays visible."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks

from backend.services.crm.drive_registration_visibility import drive_default_client_visible


class TestPredicate:
    @pytest.mark.parametrize("name", ["chat.txt", "CHAT.TXT", "Notes.Md", "a.b.md", " x.txt "])
    def test_notes_files_are_hidden(self, name: str) -> None:
        assert drive_default_client_visible(name) is False

    @pytest.mark.parametrize(
        "name", ["passport.pdf", "kitas.jpg", "txt", "notes.txt.pdf", "readme.mdx", "", None]
    )
    def test_everything_else_stays_visible(self, name: str | None) -> None:
        assert drive_default_client_visible(name) is True


class _Acquire:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    async def __aenter__(self) -> Any:
        return self.conn

    async def __aexit__(self, *_a: Any) -> bool:
        return False


class _Pool:
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self.conn)

    async def close(self) -> None:
        return None


async def _poll_one_file(file_name: str) -> AsyncMock:
    from backend.services.crm.drive_poll_service import _do_poll_drive_changes

    conn = AsyncMock()
    conn.fetchrow.side_effect = [{"value": "start-token"}]
    conn.fetch.side_effect = [
        [{"client_id": 42, "subfolder_name": "01_Immigration", "subfolder_id": "folder-imm"}],
        [],
        [],
    ]
    conn.fetchval.side_effect = [None, 99]  # no existing doc by file_id; inserted id
    drive_service = AsyncMock()
    drive_service.list_changes_since.return_value = {
        "changes": [
            {
                "file": {
                    "id": "drive-file-1",
                    "name": file_name,
                    "mimeType": "text/plain",
                    "parents": ["folder-imm"],
                },
                "removed": False,
            }
        ],
        "new_page_token": "next",
        "more_pages": False,
        "pages_fetched": 1,
    }
    drive_service.get_file_metadata.return_value = {"size": "0"}
    with (
        patch(
            "backend.services.crm.drive_poll_service.asyncpg.create_pool",
            new=AsyncMock(return_value=_Pool(conn)),
        ),
        patch(
            "backend.services.integrations.service_account_drive_service.ServiceAccountDriveService",
            return_value=drive_service,
        ),
        patch(
            "backend.services.crm.drive_poll_service.enqueue_client",
            new=AsyncMock(return_value={"action": "inserted"}),
        ),
        patch.dict("os.environ", {"DATABASE_URL": "postgresql://test/db"}, clear=False),
    ):
        result = await _do_poll_drive_changes(acquire_advisory_lock=False, inline_ocr=False)
    assert result["processed"] == 1
    return conn


@pytest.mark.asyncio
async def test_poll_registers_txt_note_hidden() -> None:
    conn = await _poll_one_file("WhatsApp Chat.txt")
    insert = conn.fetchval.call_args_list[1]
    assert "INSERT INTO documents" in insert.args[0]
    assert "client_visible" in insert.args[0]
    assert insert.args[-1] is False


@pytest.mark.asyncio
async def test_poll_registers_pdf_visible() -> None:
    conn = await _poll_one_file("passport.pdf")
    assert conn.fetchval.call_args_list[1].args[-1] is True


async def _run_backfill(file_name: str) -> list[Any]:
    from backend.app.routers import admin_drive_health as mod

    conn = AsyncMock()
    conn.fetch.side_effect = [[{"id": 7, "google_drive_folder_id": "root"}], []]
    drive = MagicMock()
    folder = {
        "id": "sub1",
        "name": "01_Immigration",
        "mimeType": "application/vnd.google-apps.folder",
    }
    drive.service.files.return_value.list.return_value.execute.side_effect = [
        {"files": [folder]},
        {"files": [{"id": "f1", "name": file_name, "mimeType": "text/plain"}]},
    ]
    tasks = BackgroundTasks()
    with (
        patch("asyncpg.create_pool", new=AsyncMock(return_value=_Pool(conn))),
        patch(
            "backend.services.integrations.service_account_drive_service.ServiceAccountDriveService",
            return_value=drive,
        ),
        patch.dict("os.environ", {"DATABASE_URL": "postgresql://test/db"}, clear=False),
        patch.object(mod, "_require_backfill_admin"),
    ):
        await mod.backfill_drive_documents(MagicMock(), tasks, {"role": "admin"})
        await tasks.tasks[0].func()
    return [c for c in conn.execute.call_args_list if "INSERT INTO documents" in c.args[0]]


@pytest.mark.asyncio
async def test_backfill_registers_txt_note_hidden() -> None:
    inserts = await _run_backfill("passport notes.txt")
    assert len(inserts) == 1
    assert inserts[0].args[-1] is False


@pytest.mark.asyncio
async def test_backfill_registers_pdf_visible() -> None:
    inserts = await _run_backfill("passport.pdf")
    assert len(inserts) == 1
    assert inserts[0].args[-1] is True
