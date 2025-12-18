"""
API Tests for WorkSessionService - Coverage 95% Target
Tests WorkSessionService methods

Coverage:
- start_session method
- update_activity method
- increment_conversations method
- end_session method
- get_daily_summary method
- connect method
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key_for_testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestWorkSessionService:
    """Test WorkSessionService methods"""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test connect method with database URL"""
        from backend.services.work_session_service import WorkSessionService

        with patch("backend.services.work_session_service.asyncpg.create_pool") as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool

            service = WorkSessionService()
            await service.connect()

            assert service.pool is not None

    @pytest.mark.asyncio
    async def test_connect_no_database_url(self):
        """Test connect method without database URL"""
        from backend.services.work_session_service import WorkSessionService

        with patch("backend.services.work_session_service.settings") as mock_settings:
            mock_settings.database_url = None

            service = WorkSessionService()
            await service.connect()

            assert service.pool is None

    @pytest.mark.asyncio
    async def test_start_session_new(self):
        """Test start_session creates new session"""
        from datetime import datetime

        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)  # No existing session

        mock_session = MagicMock()
        mock_session.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "session123",
                "session_start": datetime.now(),
            }.get(k)
        )

        mock_pool.fetchrow = AsyncMock(return_value=mock_session)

        service = WorkSessionService()
        service.pool = mock_pool

        with patch.object(service, "_notify_zero", new_callable=AsyncMock):
            result = await service.start_session("user123", "Test User", "test@example.com")

            assert "status" in result
            assert result["status"] == "started"
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_start_session_already_active(self):
        """Test start_session with existing active session"""
        from datetime import datetime

        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_existing = MagicMock()
        mock_existing.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "existing123",
                "session_start": datetime.now(),
            }.get(k)
        )

        mock_pool.fetchrow = AsyncMock(return_value=mock_existing)

        service = WorkSessionService()
        service.pool = mock_pool

        result = await service.start_session("user123", "Test User", "test@example.com")

        assert "status" in result
        assert result["status"] == "already_active"
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_start_session_no_pool(self):
        """Test start_session without database pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        result = await service.start_session("user123", "Test User", "test@example.com")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_activity(self):
        """Test update_activity method"""
        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock()

        service = WorkSessionService()
        service.pool = mock_pool

        await service.update_activity("user123")

        mock_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_activity_no_pool(self):
        """Test update_activity without pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        # Should not raise error
        await service.update_activity("user123")

    @pytest.mark.asyncio
    async def test_increment_conversations(self):
        """Test increment_conversations method"""
        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_pool.execute = AsyncMock()

        service = WorkSessionService()
        service.pool = mock_pool

        await service.increment_conversations("user123")

        mock_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_conversations_no_pool(self):
        """Test increment_conversations without pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        # Should not raise error
        await service.increment_conversations("user123")

    @pytest.mark.asyncio
    async def test_end_session_success(self):
        """Test end_session successfully ends session"""
        from datetime import datetime

        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_session = MagicMock()
        mock_session.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "id": "session123",
                "session_start": datetime.now(),
                "user_name": "Test User",
                "user_email": "test@example.com",
                "activities_count": 10,
                "conversations_count": 5,
            }.get(k)
        )

        mock_pool.fetchrow = AsyncMock(return_value=mock_session)
        mock_pool.execute = AsyncMock()

        service = WorkSessionService()
        service.pool = mock_pool

        with patch.object(service, "_notify_zero", new_callable=AsyncMock):
            result = await service.end_session("user123")

            assert "status" in result
            assert result["status"] == "ended"

    @pytest.mark.asyncio
    async def test_end_session_no_active_session(self):
        """Test end_session with no active session"""
        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)

        service = WorkSessionService()
        service.pool = mock_pool

        result = await service.end_session("user123")

        assert "status" in result
        assert result["status"] == "no_active_session"

    @pytest.mark.asyncio
    async def test_end_session_no_pool(self):
        """Test end_session without pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        result = await service.end_session("user123")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_today_sessions(self):
        """Test get_today_sessions method"""
        from datetime import datetime

        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "session_start": datetime.now(),
                "session_end": None,
                "duration_minutes": 480,
                "activities_count": 20,
                "conversations_count": 10,
                "status": "active",
                "last_activity": datetime.now(),
                "notes": None,
            }.get(k)
        )

        mock_pool.fetch = AsyncMock(return_value=[mock_row])

        service = WorkSessionService()
        service.pool = mock_pool

        result = await service.get_today_sessions()

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_today_sessions_no_pool(self):
        """Test get_today_sessions without pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        result = await service.get_today_sessions()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_week_summary(self):
        """Test get_week_summary method"""
        from datetime import datetime

        from backend.services.work_session_service import WorkSessionService

        mock_pool = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "user_name": "Test User",
                "user_email": "test@example.com",
                "session_start": datetime.now(),
                "duration_minutes": 480,
                "conversations_count": 10,
                "activities_count": 20,
            }.get(k)
        )

        mock_pool.fetch = AsyncMock(return_value=[mock_row])

        service = WorkSessionService()
        service.pool = mock_pool

        result = await service.get_week_summary()

        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_week_summary_no_pool(self):
        """Test get_week_summary without pool"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()
        service.pool = None

        result = await service.get_week_summary()

        assert result == {}

    def test_write_to_log(self):
        """Test _write_to_log method"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()

        # Should not raise error
        service._write_to_log("test_event", {"key": "value"})

    def test_ensure_data_dir(self):
        """Test _ensure_data_dir method"""
        from backend.services.work_session_service import WorkSessionService

        service = WorkSessionService()

        # Should not raise error
        service._ensure_data_dir()
