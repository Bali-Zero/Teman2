import io
import runpy
from unittest.mock import AsyncMock, patch

import export_bab
import pytest


@pytest.mark.asyncio
async def test_export_bab_no_database_url(capsys):
    with patch("os.getenv", return_value=None):
        await export_bab.export_bab()
    output = capsys.readouterr().out
    assert "DATABASE_URL not set" in output


@pytest.mark.asyncio
async def test_export_bab_success_writes_json(capsys):
    fake_records = [
        {
            "id": 1,
            "document_id": "PP_31_2013",
            "type": "bab",
            "title": "BAB I",
            "pasal_count": 2,
            "char_count": 100,
            "text_preview": "preview",
            "full_text_length": 1000,
            "created_at": "2026-01-01",
        },
        {
            "id": 2,
            "document_id": "PP_31_2013",
            "type": "bab",
            "title": "BAB II",
            "pasal_count": 3,
            "char_count": 200,
            "text_preview": "preview2",
            "full_text_length": 2000,
            "created_at": "2026-01-02",
        },
    ]
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = fake_records

    with patch("os.getenv", return_value="postgres://test"):
        with patch("asyncpg.connect", AsyncMock(return_value=mock_conn)) as connect:
            with patch("builtins.open", return_value=io.StringIO()) as open_file:
                await export_bab.export_bab()

    connect.assert_awaited_once()
    mock_conn.fetch.assert_awaited_once()
    mock_conn.close.assert_awaited_once()
    open_file.assert_called_once()

    output = capsys.readouterr().out
    assert "Connecting to database..." in output
    assert "Exported 2 BAB" in output


@pytest.mark.asyncio
async def test_export_bab_handles_exception(capsys):
    with patch("os.getenv", return_value="postgres://test"):
        with patch("asyncpg.connect", side_effect=RuntimeError("boom")):
            with patch("traceback.print_exc") as print_exc:
                await export_bab.export_bab()
    output = capsys.readouterr().out
    assert "ERROR: boom" in output
    print_exc.assert_called_once()


def test_main_runs_export_bab():
    called = {"ran": False}

    def run_coroutine(coro):
        called["ran"] = True
        coro.close()
        return None

    with patch("asyncio.run", side_effect=run_coroutine):
        runpy.run_module("export_bab", run_name="__main__")

    assert called["ran"] is True
