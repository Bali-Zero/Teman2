"""
Integration tests for WorkSessionService with real PostgreSQL database.

These tests verify that WorkSessionService correctly interacts with PostgreSQL.
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.database
class TestWorkSessionIntegration:
    """Integration tests for WorkSessionService with real PostgreSQL"""

    @pytest.mark.asyncio
    async def test_work_session_connect_no_database_url(self, postgres_container):
        """Test work session connection without database URL"""
        # Skip if database is not available
        if postgres_container is None:
            pytest.skip("Database not available")
        """Test connecting without database URL (should use in-memory fallback)"""
        import os
        from unittest.mock import patch

        from services.work_session_service import WorkSessionService

        # Temporarily remove DATABASE_URL
        original_url = os.environ.get("DATABASE_URL")
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

        try:
            # Mock settings to return None
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.database_url = None
                service = WorkSessionService()
                await service.connect()

                # Should not have pool if no database URL
                assert service.pool is None

                # WorkSessionService doesn't have close(), pool cleanup happens automatically
        finally:
            # Restore original URL
            if original_url:
                os.environ["DATABASE_URL"] = original_url

    @pytest.mark.asyncio
    async def test_work_session_connect_with_database(self, postgres_container):
        """Test connecting with real PostgreSQL database"""
        import os
        from unittest.mock import patch

        from services.work_session_service import WorkSessionService

        database_url = postgres_container
        # Normalize database URL (remove +psycopg2 if present)
        if database_url and "+" in database_url:
            database_url = database_url.replace("+psycopg2", "")

        original_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = database_url

        try:
            # Mock settings to use test database URL
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.database_url = database_url
                service = WorkSessionService()
                await service.connect()

                # Should have pool if database URL is provided
                assert service.pool is not None

                # Cleanup pool
                if service.pool:
                    await service.pool.close()
        finally:
            # Restore original URL
            if original_url:
                os.environ["DATABASE_URL"] = original_url
            elif "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
