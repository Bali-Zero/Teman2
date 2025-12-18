"""
Comprehensive tests for services/session_service.py
Target: 99%+ coverage
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestSessionService:
    """Comprehensive test suite for SessionService"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        redis_mock = AsyncMock()
        redis_mock.ping = AsyncMock(return_value=True)
        redis_mock.setex = AsyncMock()
        redis_mock.get = AsyncMock()
        redis_mock.set = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.expire = AsyncMock()
        redis_mock.keys = AsyncMock(return_value=[])
        redis_mock.close = AsyncMock()
        return redis_mock

    @pytest.fixture
    def session_service(self, mock_redis):
        """Create SessionService instance with mocked Redis"""
        with patch("services.session_service.redis.from_url", return_value=mock_redis):
            from services.session_service import SessionService

            return SessionService("redis://localhost:6379")

    def test_init(self, mock_redis):
        """Test SessionService initialization"""
        with patch("services.session_service.redis.from_url", return_value=mock_redis):
            from services.session_service import SessionService

            service = SessionService("redis://localhost:6379")
            assert service.ttl is not None

    def test_init_custom_ttl(self, mock_redis):
        """Test SessionService initialization with custom TTL"""
        with patch("services.session_service.redis.from_url", return_value=mock_redis):
            from services.session_service import SessionService

            service = SessionService("redis://localhost:6379", ttl_hours=48)
            assert service.ttl.total_seconds() == 48 * 3600

    def test_init_error(self):
        """Test SessionService initialization error"""
        with patch("services.session_service.redis.from_url", side_effect=Exception("Error")):
            from services.session_service import SessionService

            with pytest.raises(Exception):
                SessionService("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_health_check_success(self, session_service, mock_redis):
        """Test health_check success"""
        mock_redis.ping = AsyncMock(return_value=True)
        result = await session_service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_service, mock_redis):
        """Test health_check failure"""
        mock_redis.ping = AsyncMock(side_effect=Exception("Error"))
        result = await session_service.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_create_session(self, session_service, mock_redis):
        """Test create_session"""
        session_id = await session_service.create_session()
        assert session_id is not None
        assert isinstance(session_id, str)
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_error(self, session_service, mock_redis):
        """Test create_session with error"""
        mock_redis.setex = AsyncMock(side_effect=Exception("Error"))
        with pytest.raises(Exception):
            await session_service.create_session()

    @pytest.mark.asyncio
    async def test_get_history_success(self, session_service, mock_redis):
        """Test get_history success"""
        history = [{"role": "user", "content": "Hello"}]
        mock_redis.get = AsyncMock(return_value=json.dumps(history))
        result = await session_service.get_history("session123")
        assert result == history

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, session_service, mock_redis):
        """Test get_history when session not found"""
        mock_redis.get = AsyncMock(return_value=None)
        result = await session_service.get_history("session123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_invalid_json(self, session_service, mock_redis):
        """Test get_history with invalid JSON"""
        mock_redis.get = AsyncMock(return_value="invalid json")
        result = await session_service.get_history("session123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_error(self, session_service, mock_redis):
        """Test get_history with error"""
        mock_redis.get = AsyncMock(side_effect=Exception("Error"))
        result = await session_service.get_history("session123")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_history_success(self, session_service, mock_redis):
        """Test update_history success"""
        history = [{"role": "user", "content": "Hello"}]
        result = await session_service.update_history("session123", history)
        assert result is True
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_history_error(self, session_service, mock_redis):
        """Test update_history with error"""
        mock_redis.set = AsyncMock(side_effect=Exception("Error"))
        history = [{"role": "user", "content": "Hello"}]
        result = await session_service.update_history("session123", history)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_success(self, session_service, mock_redis):
        """Test delete_session success"""
        mock_redis.delete = AsyncMock(return_value=1)
        result = await session_service.delete_session("session123")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, session_service, mock_redis):
        """Test delete_session when session not found"""
        mock_redis.delete = AsyncMock(return_value=0)
        result = await session_service.delete_session("session123")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_error(self, session_service, mock_redis):
        """Test delete_session with error"""
        mock_redis.delete = AsyncMock(side_effect=Exception("Error"))
        result = await session_service.delete_session("session123")
        assert result is False

    @pytest.mark.asyncio
    async def test_extend_session_success(self, session_service, mock_redis):
        """Test extend_session success"""
        mock_redis.expire = AsyncMock(return_value=True)
        result = await session_service.extend_session("session123")
        assert result is True

    @pytest.mark.asyncio
    async def test_extend_session_error(self, session_service, mock_redis):
        """Test extend_session with error"""
        mock_redis.expire = AsyncMock(side_effect=Exception("Error"))
        result = await session_service.extend_session("session123")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_service, mock_redis):
        """Test cleanup_expired_sessions"""
        mock_redis.keys = AsyncMock(return_value=["session:123", "session:456"])
        mock_redis.get = AsyncMock(return_value=None)  # All expired
        result = await session_service.cleanup_expired_sessions()
        assert isinstance(result, int)

    @pytest.mark.asyncio
    async def test_close(self, session_service, mock_redis):
        """Test close"""
        await session_service.close()
        mock_redis.close.assert_called_once()
