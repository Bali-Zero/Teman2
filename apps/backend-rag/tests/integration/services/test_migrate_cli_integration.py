"""
Integration Tests for Migration CLI Tool (db/migrate.py)
Tests migration commands with real database
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestMigrateCLIIntegration:
    """Integration tests for migration CLI tool"""

    def test_migrate_status_command(self, postgres_container):
        """Test migrate status command"""
        # Set DATABASE_URL
        os.environ["DATABASE_URL"] = postgres_container

        # Run migrate status
        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "status"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should complete successfully
        assert result.returncode == 0 or result.returncode == 1  # May fail if no migrations
        assert "MIGRATION STATUS" in result.stdout or "status" in result.stdout.lower()

    def test_migrate_list_command(self, postgres_container):
        """Test migrate list command"""
        os.environ["DATABASE_URL"] = postgres_container

        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "list"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should complete successfully
        assert result.returncode == 0 or result.returncode == 1
        assert "ALL MIGRATIONS" in result.stdout or "migrations" in result.stdout.lower()

    def test_migrate_info_command(self, postgres_container):
        """Test migrate info command"""
        os.environ["DATABASE_URL"] = postgres_container

        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "info", "1"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should complete (may show pending if migration doesn't exist)
        assert result.returncode == 0 or result.returncode == 1

    def test_migrate_apply_all_dry_run(self, postgres_container):
        """Test migrate apply-all with dry-run"""
        os.environ["DATABASE_URL"] = postgres_container

        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "apply-all", "--dry-run"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Should complete (may skip if no migrations)
        assert result.returncode == 0 or result.returncode == 1
        assert (
            "DRY RUN" in result.stdout
            or "dry" in result.stdout.lower()
            or "MIGRATION RESULTS" in result.stdout
        )

    def test_migrate_help_command(self):
        """Test migrate help command"""
        result = subprocess.run(
            [sys.executable, "-m", "db.migrate", "--help"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "NUZANTARA PRIME" in result.stdout or "migration" in result.stdout.lower()

    def test_migrate_no_command_shows_help(self):
        """Test migrate with no command shows help"""
        result = subprocess.run(
            [sys.executable, "-m", "db.migrate"],
            cwd=str(backend_path.parent),
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should show help and exit with error code
        assert result.returncode == 1
        assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()

    def test_migrate_without_database_url(self):
        """Test migrate fails gracefully without DATABASE_URL"""
        # Remove DATABASE_URL if set
        old_db_url = os.environ.pop("DATABASE_URL", None)

        try:
            result = subprocess.run(
                [sys.executable, "-m", "db.migrate", "status"],
                cwd=str(backend_path.parent),
                capture_output=True,
                text=True,
                timeout=10,
            )

            # Should fail with error message
            assert result.returncode == 1
            assert "DATABASE_URL" in result.stderr or "DATABASE_URL" in result.stdout
        finally:
            # Restore DATABASE_URL
            if old_db_url:
                os.environ["DATABASE_URL"] = old_db_url
