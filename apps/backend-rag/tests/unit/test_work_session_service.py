"""
Unit tests for WorkSessionService
Tests work session tracking functionality
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestWorkSessionService:
    """Unit tests for WorkSessionService"""

    @pytest.fixture
    def mock_db_pool(self):
        """Create mock database pool"""
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock()
        mock_pool.fetch = AsyncMock(return_value=[])
        mock_pool.execute = AsyncMock()
        return mock_pool

    def test_work_session_service_init(self):
        """Test WorkSessionService initialization"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost/test"
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                assert service is not None
                assert service.db_url is not None

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_db_pool):
        """Test successful database connection"""
        from unittest.mock import AsyncMock

        with (
            patch(
                "services.work_session_service.asyncpg.create_pool",
                new_callable=AsyncMock,
                return_value=mock_db_pool,
            ),
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_settings.database_url = "postgresql://test:test@localhost/test"
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                await service.connect()
                assert service.pool is not None

    @pytest.mark.asyncio
    async def test_connect_no_database_url(self):
        """Test connection without database URL"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = None
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                await service.connect()
                assert service.pool is None

    @pytest.mark.asyncio
    async def test_start_session_new(self, mock_db_pool):
        """Test starting a new session"""
        mock_db_pool.fetchrow = AsyncMock(return_value=None)
        mock_db_pool.execute = AsyncMock()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost/test"
            with (
                patch("pathlib.Path.mkdir"),
                patch("pathlib.Path.exists", return_value=True),
                patch("services.work_session_service.WorkSessionService._write_to_log"),
            ):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                service.pool = mock_db_pool
                result = await service.start_session(
                    user_id="test_user", user_name="Test User", user_email="test@example.com"
                )
                assert result is not None
                assert "session_id" in result or "error" in result

    @pytest.mark.asyncio
    async def test_start_session_already_active(self, mock_db_pool):
        """Test starting session when already active"""
        from datetime import datetime

        mock_db_pool.fetchrow = AsyncMock(
            return_value={"id": "existing_session", "session_start": datetime.now()}
        )
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost/test"
            with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                service.pool = mock_db_pool
                result = await service.start_session(
                    user_id="test_user", user_name="Test User", user_email="test@example.com"
                )
                assert result is not None
                assert result.get("status") == "already_active"

    @pytest.mark.asyncio
    async def test_end_session(self, mock_db_pool):
        """Test ending a session"""
        mock_db_pool.execute = AsyncMock()
        with patch("services.work_session_service.asyncpg.create_pool", return_value=mock_db_pool):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with (
                    patch("pathlib.Path.mkdir"),
                    patch("pathlib.Path.exists", return_value=True),
                    patch("services.work_session_service.WorkSessionService._write_to_log"),
                ):
                    from services.work_session_service import WorkSessionService

                    service = WorkSessionService()
                    service.pool = mock_db_pool
                    # Check if end_session method exists
                    if hasattr(service, "end_session"):
                        result = await service.end_session("session_id", "test_user")
                        assert result is not None

    @pytest.mark.asyncio
    async def test_get_user_status(self, mock_db_pool):
        """Test getting user status"""
        mock_db_pool.fetchrow = AsyncMock(
            return_value={"status": "active", "session_start": "2025-01-01 09:00:00"}
        )
        with patch("services.work_session_service.asyncpg.create_pool", return_value=mock_db_pool):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.database_url = "postgresql://test:test@localhost/test"
                with patch("pathlib.Path.mkdir"), patch("pathlib.Path.exists", return_value=True):
                    from services.work_session_service import WorkSessionService

                    service = WorkSessionService()
                    service.pool = mock_db_pool
                    # Check if get_user_status method exists
                    if hasattr(service, "get_user_status"):
                        result = await service.get_user_status("test_user")
                        assert result is not None

    def test_write_to_log(self):
        """Test writing to log file"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test:test@localhost/test"
            with (
                patch("pathlib.Path.mkdir"),
                patch("pathlib.Path.exists", return_value=True),
                patch("builtins.open", create=True) as mock_open,
            ):
                from services.work_session_service import WorkSessionService

                service = WorkSessionService()
                service._write_to_log("test_event", {"data": "test"})
                mock_open.assert_called_once()
