import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import backend.db.migrate as migrate
import pytest
from backend.db.migration_base import MigrationError


@pytest.mark.asyncio
async def test_cmd_status_outputs_summary(capsys):
    manager = AsyncMock()
    manager.get_status.return_value = {
        "total": 3,
        "applied": 2,
        "pending": 1,
        "applied_list": [1, 2],
        "pending_list": [3],
    }

    await migrate.cmd_status(manager)
    output = capsys.readouterr().out

    assert "MIGRATION STATUS" in output
    assert "Total migrations discovered: 3" in output
    assert "Applied: 2" in output
    assert "Pending: 1" in output
    assert "Applied migrations: 1, 2" in output
    assert "Pending migrations: 3" in output


@pytest.mark.asyncio
async def test_cmd_list_outputs_status(capsys):
    manager = AsyncMock()
    manager.discover_migrations.return_value = [
        {"number": 1, "file": "001_init.py"},
        {"number": 2, "file": "002_add_table.py"},
    ]
    manager.get_applied_migrations.return_value = [{"migration_number": 1}]

    await migrate.cmd_list(manager)
    output = capsys.readouterr().out

    assert "ALL MIGRATIONS" in output
    assert "001: 001_init.py" in output
    assert "002: 002_add_table.py" in output
    assert "APPLIED" in output
    assert "PENDING" in output


@pytest.mark.asyncio
async def test_cmd_apply_specific_not_implemented(capsys):
    manager = AsyncMock()
    result = await migrate.cmd_apply(manager, migration_number=7)
    output = capsys.readouterr().out

    assert result is False
    assert "Applying specific migration 7 not yet implemented" in output


@pytest.mark.asyncio
async def test_cmd_apply_all_dry_run_success(capsys):
    manager = AsyncMock()
    manager.apply_all_pending.return_value = {
        "applied": [1, 2],
        "skipped": [],
        "failed": [],
    }

    result = await migrate.cmd_apply(manager, dry_run=True)
    output = capsys.readouterr().out

    assert result is True
    assert "DRY RUN" in output
    assert "Applied: 2 migrations" in output


@pytest.mark.asyncio
async def test_cmd_apply_all_with_failures(capsys):
    manager = AsyncMock()
    manager.apply_all_pending.return_value = {
        "applied": [1],
        "skipped": [2],
        "failed": [{"number": 3, "error": "boom"}],
    }

    result = await migrate.cmd_apply(manager, dry_run=False)
    output = capsys.readouterr().out

    assert result is False
    assert "Failed: 1 migrations" in output
    assert "Migration 003: boom" in output


@pytest.mark.asyncio
async def test_cmd_info_applied_and_pending(capsys):
    manager = AsyncMock()
    manager.get_applied_migrations.return_value = [
        {"migration_number": 5, "executed_at": "2026-01-01", "description": "Test"},
    ]

    await migrate.cmd_info(manager, 5)
    output_applied = capsys.readouterr().out
    assert "Status: ✅ APPLIED" in output_applied
    assert "Applied at: 2026-01-01" in output_applied
    assert "Description: Test" in output_applied

    await migrate.cmd_info(manager, 6)
    output_pending = capsys.readouterr().out
    assert "Status: ⏳ PENDING" in output_pending


def test_main_no_command_exits_1(capsys):
    with patch("sys.argv", ["migrate"]):
        with pytest.raises(SystemExit) as exc:
            migrate.main()
    assert exc.value.code == 1
    assert "NUZANTARA PRIME - Database Migration Tool" in capsys.readouterr().out


def test_main_missing_database_url_exits_1():
    args = SimpleNamespace(command="status", redis_url='redis://localhost:6379')
    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = ""
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with pytest.raises(SystemExit) as exc:
                migrate.main()
    assert exc.value.code == 1


def test_main_migration_manager_error_exits_1():
    args = SimpleNamespace(command="status", redis_url='redis://localhost:6379')
    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = "postgres://test"
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("backend.db.migrate.MigrationManager", side_effect=MigrationError("fail")):
                with pytest.raises(SystemExit) as exc:
                    migrate.main()
    assert exc.value.code == 1


def test_main_keyboard_interrupt_exits_130():
    args = SimpleNamespace(command="status", redis_url='redis://localhost:6379')

    def run_and_interrupt(coro):
        coro.close()
        raise KeyboardInterrupt

    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = "postgres://test"
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("backend.db.migrate.MigrationManager", return_value=SimpleNamespace()):
                with patch("backend.db.migrate.asyncio.run", side_effect=run_and_interrupt):
                    with pytest.raises(SystemExit) as exc:
                        migrate.main()
    assert exc.value.code == 130


def test_main_exception_exits_1():
    args = SimpleNamespace(command="status", redis_url='redis://localhost:6379')

    def run_and_raise(coro):
        coro.close()
        raise RuntimeError("boom")

    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = "postgres://test"
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("backend.db.migrate.MigrationManager", return_value=SimpleNamespace()):
                with patch("backend.db.migrate.asyncio.run", side_effect=run_and_raise):
                    with pytest.raises(SystemExit) as exc:
                        migrate.main()
    assert exc.value.code == 1


def test_main_dispatches_command_runs_and_exits_0():
    args = SimpleNamespace(command="status", redis_url='redis://localhost:6379')

    class DummyManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def run_coroutine(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = "postgres://test"
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("backend.db.migrate.MigrationManager", return_value=DummyManager()):
                with patch("backend.db.migrate.cmd_status", AsyncMock(return_value=True)) as cmd_status:
                    with patch("backend.db.migrate.asyncio.run", side_effect=run_coroutine):
                        with pytest.raises(SystemExit) as exc:
                            migrate.main()
    assert exc.value.code == 0
    cmd_status.assert_awaited_once()


def test_main_unknown_command_prints_help_and_exits_1(capsys):
    args = SimpleNamespace(command="unknown", dry_run=False, migration_number=1, redis_url='redis://localhost:6379')

    class DummyManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def run_coroutine(coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch("backend.db.migrate.settings") as mock_settings:
        mock_settings.database_url = "postgres://test"
        with patch("argparse.ArgumentParser.parse_args", return_value=args):
            with patch("backend.db.migrate.MigrationManager", return_value=DummyManager()):
                with patch("backend.db.migrate.asyncio.run", side_effect=run_coroutine):
                    with pytest.raises(SystemExit) as exc:
                        migrate.main()
    assert exc.value.code == 1
    assert "NUZANTARA PRIME - Database Migration Tool" in capsys.readouterr().out
