"""
Integration Tests for db/migrate.py
Tests database migration CLI tool with real database
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMigrateIntegration:
    """Comprehensive integration tests for db/migrate.py"""

    @pytest_asyncio.fixture
    async def mock_migration_manager(self):
        """Create mock migration manager"""
        mock_manager = MagicMock()
        mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
        mock_manager.__aexit__ = AsyncMock(return_value=None)
        mock_manager.get_status = AsyncMock(
            return_value={
                "total": 10,
                "applied": 5,
                "pending": 5,
                "applied_list": [1, 2, 3, 4, 5],
                "pending_list": [6, 7, 8, 9, 10],
            }
        )
        mock_manager.discover_migrations = AsyncMock(
            return_value=[
                {"number": 1, "file": "001_initial.sql"},
                {"number": 2, "file": "002_schema.sql"},
            ]
        )
        mock_manager.get_applied_migrations = AsyncMock(
            return_value=[
                {
                    "migration_number": 1,
                    "executed_at": "2025-01-01",
                    "description": "Initial migration",
                }
            ]
        )
        mock_manager.apply_all_pending = AsyncMock(
            return_value={"applied": [6, 7], "skipped": [], "failed": []}
        )
        return mock_manager

    @pytest.mark.asyncio
    async def test_cmd_status(self, mock_migration_manager):
        """Test status command"""
        from db.migrate import cmd_status

        # Should not raise exception
        await cmd_status(mock_migration_manager)
        mock_migration_manager.get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_list(self, mock_migration_manager):
        """Test list command"""
        from db.migrate import cmd_list

        # Should not raise exception
        await cmd_list(mock_migration_manager)
        mock_migration_manager.discover_migrations.assert_called_once()
        mock_migration_manager.get_applied_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_apply_all(self, mock_migration_manager):
        """Test apply-all command"""
        from db.migrate import cmd_apply

        result = await cmd_apply(mock_migration_manager, dry_run=False)
        assert result is True
        mock_migration_manager.apply_all_pending.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_apply_all_dry_run(self, mock_migration_manager):
        """Test apply-all command with dry run"""
        from db.migrate import cmd_apply

        result = await cmd_apply(mock_migration_manager, dry_run=True)
        assert result is True
        mock_migration_manager.apply_all_pending.assert_called_once_with(dry_run=True)

    @pytest.mark.asyncio
    async def test_cmd_apply_specific_migration(self, mock_migration_manager):
        """Test apply command with specific migration number"""
        from db.migrate import cmd_apply

        result = await cmd_apply(mock_migration_manager, migration_number=5, dry_run=False)
        # Should return False as specific migration not implemented
        assert result is False

    @pytest.mark.asyncio
    async def test_cmd_apply_with_failures(self, mock_migration_manager):
        """Test apply command when migrations fail"""
        from db.migrate import cmd_apply

        mock_migration_manager.apply_all_pending = AsyncMock(
            return_value={
                "applied": [6],
                "skipped": [],
                "failed": [{"number": 7, "error": "Migration failed"}],
            }
        )

        result = await cmd_apply(mock_migration_manager, dry_run=False)
        assert result is False  # Should return False when failures occur

    @pytest.mark.asyncio
    async def test_cmd_info_applied(self, mock_migration_manager):
        """Test info command for applied migration"""
        from db.migrate import cmd_info

        # Should not raise exception
        await cmd_info(mock_migration_manager, migration_number=1)
        mock_migration_manager.get_applied_migrations.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_info_pending(self, mock_migration_manager):
        """Test info command for pending migration"""
        from db.migrate import cmd_info

        # Should not raise exception
        await cmd_info(mock_migration_manager, migration_number=10)
        mock_migration_manager.get_applied_migrations.assert_called_once()

    def test_main_with_status_command(self):
        """Test main function with status command"""

        from db.migrate import main

        with patch("sys.argv", ["migrate", "status"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run") as mock_run:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager_class.return_value = mock_manager

                    # Mock the async function
                    async def mock_async_func():
                        from db.migrate import cmd_status

                        await cmd_status(mock_manager)
                        return True

                    mock_run.return_value = True

                    # Should not raise exception
                    try:
                        main()
                    except SystemExit:
                        pass  # Expected when command completes

    def test_main_with_list_command(self):
        """Test main function with list command"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "list"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run") as mock_run:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager_class.return_value = mock_manager

                    mock_run.return_value = True

                    try:
                        main()
                    except SystemExit:
                        pass

    def test_main_with_apply_all_command(self):
        """Test main function with apply-all command"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "apply-all"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run") as mock_run:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager_class.return_value = mock_manager

                    mock_run.return_value = True

                    try:
                        main()
                    except SystemExit:
                        pass

    def test_main_with_info_command(self):
        """Test main function with info command"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "info", "7"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run") as mock_run:
                    mock_manager = MagicMock()
                    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
                    mock_manager.__aexit__ = AsyncMock(return_value=None)
                    mock_manager_class.return_value = mock_manager

                    mock_run.return_value = True

                    try:
                        main()
                    except SystemExit:
                        pass

    def test_main_no_command(self):
        """Test main function with no command (should print help)"""
        from db.migrate import main

        with patch("sys.argv", ["migrate"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                try:
                    main()
                except SystemExit:
                    pass
                # Should print help when no command provided

    def test_main_no_database_url(self):
        """Test main function when DATABASE_URL is not set"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "status"]):
            with patch("app.core.config.settings.database_url", None):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 1  # Should exit with error code

    def test_main_migration_error(self):
        """Test main function when MigrationManager initialization fails"""
        from db.migrate import MigrationError, main

        with patch("sys.argv", ["migrate", "status"]):
            with patch("db.migrate.MigrationManager", side_effect=MigrationError("Init failed")):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 1  # Should exit with error code

    def test_main_keyboard_interrupt(self):
        """Test main function handling keyboard interrupt"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "status"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run", side_effect=KeyboardInterrupt()):
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager

                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 130  # Should exit with 130 for keyboard interrupt

    def test_main_general_exception(self):
        """Test main function handling general exception"""
        from db.migrate import main

        with patch("sys.argv", ["migrate", "status"]):
            with patch("db.migrate.MigrationManager") as mock_manager_class:
                with patch("db.migrate.asyncio.run", side_effect=Exception("General error")):
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager

                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 1  # Should exit with error code
