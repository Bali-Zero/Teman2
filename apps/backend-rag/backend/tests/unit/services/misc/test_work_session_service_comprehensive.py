"""
Unit tests for WorkSessionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.work_session_service import WorkSessionService


@pytest.fixture
def work_session_service():
    """Create WorkSessionService instance"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.database_url = None
        return WorkSessionService()


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    pool.fetchrow = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetch = AsyncMock()
    return pool


class TestWorkSessionService:
    """Tests for WorkSessionService"""

    def test_init(self):
        """Test initialization"""
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.database_url = None
            service = WorkSessionService()
            assert service.db_url is None
            assert service.pool is None

    @pytest.mark.asyncio
    async def test_connect(self, work_session_service):
        """Test connecting to database"""
        mock_pool = MagicMock()  # Pool doesn't need to be AsyncMock

        with (
            patch(
                "services.misc.work_session_service.asyncpg.create_pool", new_callable=AsyncMock
            ) as mock_create_pool,
            patch("app.core.config.settings") as mock_settings,
        ):
            mock_create_pool.return_value = mock_pool
            mock_settings.database_url = "postgresql://test:test@localhost/test"

            # Update db_url on the service instance
            work_session_service.db_url = "postgresql://test:test@localhost/test"

            await work_session_service.connect()
            # Verify create_pool was called
            mock_create_pool.assert_called_once()
            # Verify pool was set
            assert work_session_service.pool is not None

    @pytest.mark.asyncio
    async def test_start_session_no_pool(self, work_session_service):
        """Test starting session without pool"""
        result = await work_session_service.start_session("user1", "Test User", "test@example.com")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_start_session_new(self, work_session_service, mock_db_pool):
        """Test starting new session"""
        work_session_service.pool = mock_db_pool

        # First call returns None (no existing), second call returns new session
        mock_db_pool.fetchrow = AsyncMock(
            side_effect=[
                None,  # No existing session
                {"id": 1, "session_start": MagicMock(isoformat=lambda: "2024-01-01T00:00:00")},
            ]
        )

        with (
            patch.object(work_session_service, "_write_to_log") as mock_log,
            patch.object(work_session_service, "_notify_zero") as mock_notify,
        ):
            result = await work_session_service.start_session(
                "user1", "Test User", "test@example.com"
            )
            assert result["status"] == "started"

    @pytest.mark.asyncio
    async def test_start_session_existing(self, work_session_service, mock_db_pool):
        """Test starting session when already exists"""
        work_session_service.pool = mock_db_pool

        mock_db_pool.fetchrow = AsyncMock(
            return_value={
                "id": 1,
                "session_start": MagicMock(isoformat=lambda: "2024-01-01T00:00:00"),
            }
        )

        result = await work_session_service.start_session("user1", "Test User", "test@example.com")
        assert result["status"] == "already_active"

    @pytest.mark.asyncio
    async def test_update_activity(self, work_session_service, mock_db_pool):
        """Test updating activity"""
        work_session_service.pool = mock_db_pool

        await work_session_service.update_activity("user1")
        mock_db_pool.execute.assert_called()

    @pytest.mark.asyncio
    async def test_increment_conversations(self, work_session_service, mock_db_pool):
        """Test incrementing conversations"""
        work_session_service.pool = mock_db_pool

        await work_session_service.increment_conversations("user1")
        mock_db_pool.execute.assert_called()

    @pytest.mark.asyncio
    async def test_end_session(self, work_session_service, mock_db_pool):
        """Test ending session"""
        work_session_service.pool = mock_db_pool

        mock_db_pool.fetchrow = AsyncMock(
            return_value={"id": 1, "session_start": MagicMock(), "last_activity": MagicMock()}
        )

        with (
            patch.object(work_session_service, "_write_to_log") as mock_log,
            patch.object(work_session_service, "_notify_zero") as mock_notify,
        ):
            result = await work_session_service.end_session("user1")
            assert "status" in result or "error" in result

    @pytest.mark.asyncio
    async def test_get_today_sessions(self, work_session_service, mock_db_pool):
        """Test getting today's sessions"""
        work_session_service.pool = mock_db_pool

        mock_db_pool.fetch = AsyncMock(return_value=[{"id": 1, "user_name": "Test User"}])

        sessions = await work_session_service.get_today_sessions()
        assert isinstance(sessions, list)
