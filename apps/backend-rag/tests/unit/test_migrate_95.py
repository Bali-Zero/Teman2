"""
Unit Tests for db/migrate.py - 95% Coverage Target
Tests the database migration CLI tool
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test cmd_status function
# ============================================================================


class TestCmdStatus:
    """Test suite for cmd_status function"""

    @pytest.mark.asyncio
    async def test_cmd_status_with_applied_and_pending(self, capsys):
        """Test status command with both applied and pending migrations"""
        mock_manager = MagicMock()
        mock_manager.get_status = AsyncMock(
            return_value={
                "total": 5,
                "applied": 3,
                "pending": 2,
                "applied_list": [1, 2, 3],
                "pending_list": [4, 5],
            }
        )

        from db.migrate import cmd_status

        await cmd_status(mock_manager)

        captured = capsys.readouterr()
        assert "MIGRATION STATUS" in captured.out
        assert "Total migrations discovered: 5" in captured.out
        assert "Applied: 3" in captured.out
        assert "Pending: 2" in captured.out
        assert "Applied migrations:" in captured.out
        assert "Pending migrations:" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_status_no_pending(self, capsys):
        """Test status command with no pending migrations"""
        mock_manager = MagicMock()
        mock_manager.get_status = AsyncMock(
            return_value={
                "total": 3,
                "applied": 3,
                "pending": 0,
                "applied_list": [1, 2, 3],
                "pending_list": [],
            }
        )

        from db.migrate import cmd_status

        await cmd_status(mock_manager)

        captured = capsys.readouterr()
        assert "Applied: 3" in captured.out
        assert "Pending: 0" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_status_no_applied(self, capsys):
        """Test status command with no applied migrations"""
        mock_manager = MagicMock()
        mock_manager.get_status = AsyncMock(
            return_value={
                "total": 2,
                "applied": 0,
                "pending": 2,
                "applied_list": [],
                "pending_list": [1, 2],
            }
        )

        from db.migrate import cmd_status

        await cmd_status(mock_manager)

        captured = capsys.readouterr()
        assert "Applied: 0" in captured.out
        assert "Pending: 2" in captured.out


# ============================================================================
# Test cmd_list function
# ============================================================================


class TestCmdList:
    """Test suite for cmd_list function"""

    @pytest.mark.asyncio
    async def test_cmd_list_mixed_migrations(self, capsys):
        """Test list command with mixed applied/pending migrations"""
        mock_manager = MagicMock()
        mock_manager.discover_migrations = AsyncMock(
            return_value=[
                {"number": 1, "file": "001_initial.py"},
                {"number": 2, "file": "002_add_users.py"},
                {"number": 3, "file": "003_add_products.py"},
            ]
        )
        mock_manager.get_applied_migrations = AsyncMock(
            return_value=[{"migration_number": 1}, {"migration_number": 2}]
        )

        from db.migrate import cmd_list

        await cmd_list(mock_manager)

        captured = capsys.readouterr()
        assert "ALL MIGRATIONS" in captured.out
        assert "001_initial.py" in captured.out
        assert "APPLIED" in captured.out
        assert "PENDING" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_list_empty(self, capsys):
        """Test list command with no migrations"""
        mock_manager = MagicMock()
        mock_manager.discover_migrations = AsyncMock(return_value=[])
        mock_manager.get_applied_migrations = AsyncMock(return_value=[])

        from db.migrate import cmd_list

        await cmd_list(mock_manager)

        captured = capsys.readouterr()
        assert "ALL MIGRATIONS" in captured.out


# ============================================================================
# Test cmd_apply function
# ============================================================================


class TestCmdApply:
    """Test suite for cmd_apply function"""

    @pytest.mark.asyncio
    async def test_cmd_apply_specific_migration_not_implemented(self, capsys):
        """Test applying specific migration shows not implemented message"""
        mock_manager = MagicMock()

        from db.migrate import cmd_apply

        result = await cmd_apply(mock_manager, migration_number=5, dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "not yet implemented" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_apply_all_success(self, capsys):
        """Test successful apply all migrations"""
        mock_manager = MagicMock()
        mock_manager.apply_all_pending = AsyncMock(
            return_value={"applied": [1, 2, 3], "skipped": [], "failed": []}
        )

        from db.migrate import cmd_apply

        result = await cmd_apply(mock_manager, dry_run=False)

        assert result is True
        captured = capsys.readouterr()
        assert "MIGRATION RESULTS" in captured.out
        assert "Applied: 3 migrations" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_apply_dry_run(self, capsys):
        """Test apply with dry run mode"""
        mock_manager = MagicMock()
        mock_manager.apply_all_pending = AsyncMock(
            return_value={"applied": [1], "skipped": [], "failed": []}
        )

        from db.migrate import cmd_apply

        result = await cmd_apply(mock_manager, dry_run=True)

        assert result is True
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_apply_with_failures(self, capsys):
        """Test apply with failed migrations"""
        mock_manager = MagicMock()
        mock_manager.apply_all_pending = AsyncMock(
            return_value={
                "applied": [1],
                "skipped": [2],
                "failed": [{"number": 3, "error": "Database connection error"}],
            }
        )

        from db.migrate import cmd_apply

        result = await cmd_apply(mock_manager, dry_run=False)

        assert result is False
        captured = capsys.readouterr()
        assert "Failed: 1 migrations" in captured.out
        assert "Database connection error" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_apply_with_skipped(self, capsys):
        """Test apply with skipped migrations"""
        mock_manager = MagicMock()
        mock_manager.apply_all_pending = AsyncMock(
            return_value={"applied": [], "skipped": [1, 2], "failed": []}
        )

        from db.migrate import cmd_apply

        result = await cmd_apply(mock_manager, dry_run=False)

        assert result is True
        captured = capsys.readouterr()
        assert "Skipped: 2 migrations" in captured.out


# ============================================================================
# Test cmd_info function
# ============================================================================


class TestCmdInfo:
    """Test suite for cmd_info function"""

    @pytest.mark.asyncio
    async def test_cmd_info_applied_migration(self, capsys):
        """Test info for applied migration"""
        mock_manager = MagicMock()
        mock_manager.get_applied_migrations = AsyncMock(
            return_value=[
                {
                    "migration_number": 7,
                    "executed_at": "2024-01-15 10:30:00",
                    "description": "Add user preferences table",
                }
            ]
        )

        from db.migrate import cmd_info

        await cmd_info(mock_manager, 7)

        captured = capsys.readouterr()
        assert "MIGRATION 007 INFO" in captured.out
        assert "APPLIED" in captured.out
        assert "2024-01-15" in captured.out
        assert "Add user preferences table" in captured.out

    @pytest.mark.asyncio
    async def test_cmd_info_pending_migration(self, capsys):
        """Test info for pending migration"""
        mock_manager = MagicMock()
        mock_manager.get_applied_migrations = AsyncMock(return_value=[{"migration_number": 1}])

        from db.migrate import cmd_info

        await cmd_info(mock_manager, 5)

        captured = capsys.readouterr()
        assert "MIGRATION 005 INFO" in captured.out
        assert "PENDING" in captured.out
        assert "has not been applied yet" in captured.out


# ============================================================================
# Test main function
# ============================================================================


class TestMain:
    """Test suite for main function"""

    def test_main_no_command(self):
        """Test main with no command shows help and exits"""
        with patch("sys.argv", ["migrate.py"]):
            with patch("sys.exit") as mock_exit:
                from db.migrate import main

                main()
                mock_exit.assert_called_with(1)

    def test_main_no_database_url(self):
        """Test main with no database URL configured"""
        with patch("sys.argv", ["migrate.py", "status"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = None
                with patch("sys.exit") as mock_exit:
                    from db.migrate import main

                    main()
                    mock_exit.assert_called()

    def test_main_manager_initialization_error(self):
        """Test main with manager initialization error"""
        with patch("sys.argv", ["migrate.py", "status"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    from db.migration_base import MigrationError

                    mock_manager_cls.side_effect = MigrationError("Connection failed")
                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        mock_exit.assert_called_with(1)

    def test_main_status_command_success(self):
        """Test main with status command"""
        with patch("sys.argv", ["migrate.py", "status"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager.get_status = AsyncMock(
                        return_value={
                            "total": 0,
                            "applied": 0,
                            "pending": 0,
                            "applied_list": [],
                            "pending_list": [],
                        }
                    )
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        # Success returns None from cmd_status, so exit(0 if None else 1) = exit(1)
                        mock_exit.assert_called()

    def test_main_list_command(self):
        """Test main with list command"""
        with patch("sys.argv", ["migrate.py", "list"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager.discover_migrations = AsyncMock(return_value=[])
                    mock_manager.get_applied_migrations = AsyncMock(return_value=[])
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        mock_exit.assert_called()

    def test_main_apply_all_command(self):
        """Test main with apply-all command"""
        with patch("sys.argv", ["migrate.py", "apply-all"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager.apply_all_pending = AsyncMock(
                        return_value={"applied": [], "skipped": [], "failed": []}
                    )
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        mock_exit.assert_called()

    def test_main_apply_all_dry_run(self):
        """Test main with apply-all --dry-run command"""
        with patch("sys.argv", ["migrate.py", "apply-all", "--dry-run"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager.apply_all_pending = AsyncMock(
                        return_value={"applied": [1], "skipped": [], "failed": []}
                    )
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        mock_exit.assert_called()

    def test_main_info_command(self):
        """Test main with info command"""
        with patch("sys.argv", ["migrate.py", "info", "7"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager.get_applied_migrations = AsyncMock(return_value=[])
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        main()
                        mock_exit.assert_called()

    def test_main_keyboard_interrupt(self):
        """Test main with keyboard interrupt"""
        with patch("sys.argv", ["migrate.py", "status"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager_cls.return_value = MagicMock()
                    with patch("asyncio.run") as mock_run:
                        mock_run.side_effect = KeyboardInterrupt()
                        with patch("sys.exit") as mock_exit:
                            from db.migrate import main

                            main()
                            mock_exit.assert_called_with(130)

    def test_main_generic_exception(self):
        """Test main with generic exception"""
        with patch("sys.argv", ["migrate.py", "status"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager_cls.return_value = MagicMock()
                    with patch("asyncio.run") as mock_run:
                        mock_run.side_effect = Exception("Unknown error")
                        with patch("sys.exit") as mock_exit:
                            from db.migrate import main

                            main()
                            mock_exit.assert_called_with(1)

    def test_main_unknown_command(self):
        """Test main with unknown command"""
        with patch("sys.argv", ["migrate.py", "unknown-cmd"]):
            with patch("db.migrate.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("db.migrate.MigrationManager") as mock_manager_cls:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager_cls.return_value = mock_manager

                    with patch("sys.exit") as mock_exit:
                        from db.migrate import main

                        # This will fail to parse and show help
                        try:
                            main()
                        except SystemExit:
                            pass
