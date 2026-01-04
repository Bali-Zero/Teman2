"""
Unit tests for SessionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.session_service import SessionService


@pytest.fixture
def session_service():
    """Create SessionService instance"""
    with patch("redis.asyncio.from_url") as mock_redis:
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        service = SessionService(redis_url="redis://localhost:6379")
        service.redis = mock_redis_client
        return service


class TestSessionService:
    """Tests for SessionService"""

    def test_init(self):
        """Test initialization"""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client
            service = SessionService(redis_url="redis://localhost:6379")
            assert service.ttl.total_seconds() == 24 * 3600

    @pytest.mark.asyncio
    async def test_health_check(self, session_service):
        """Test health check"""
        session_service.redis.ping = AsyncMock(return_value=True)
        result = await session_service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_create_session(self, session_service):
        """Test creating session"""
        session_service.redis.setex = AsyncMock()
        result = await session_service.create_session()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_history(self, session_service):
        """Test getting session history"""
        import json

        session_service.redis.get = AsyncMock(
            return_value=json.dumps([{"role": "user", "content": "test"}])
        )
        result = await session_service.get_history("test_session_id")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, session_service):
        """Test getting non-existent session history"""
        session_service.redis.get = AsyncMock(return_value=None)
        result = await session_service.get_history("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_history(self, session_service):
        """Test updating session history"""
        session_service.redis.setex = AsyncMock()
        history = [{"role": "user", "content": "test message"}]
        result = await session_service.update_history("test_session", history)
        assert result is True
        session_service.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session(self, session_service):
        """Test deleting session"""
        session_service.redis.delete = AsyncMock(return_value=1)
        result = await session_service.delete_session("test_session")
        assert result is True
        session_service.redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, session_service):
        """Test deleting non-existent session"""
        session_service.redis.delete = AsyncMock(return_value=0)
        result = await session_service.delete_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_exception(self, session_service):
        """Test deleting session with exception"""
        session_service.redis.delete = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.delete_session("test_session")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_history_json_error(self, session_service):
        """Test getting history with JSON decode error"""
        session_service.redis.get = AsyncMock(return_value="invalid json")
        result = await session_service.get_history("test_session")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_exception(self, session_service):
        """Test getting history with exception"""
        session_service.redis.get = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.get_history("test_session")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_history_exception(self, session_service):
        """Test updating history with exception"""
        session_service.redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        history = [{"role": "user", "content": "test"}]
        result = await session_service.update_history("test_session", history)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_invalid_format(self, session_service):
        """Test updating history with invalid format"""
        result = await session_service.update_history("test_session", "not a list")
        assert result is False

    @pytest.mark.asyncio
    async def test_create_session_exception(self, session_service):
        """Test creating session with exception"""
        session_service.redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        with pytest.raises(Exception):
            await session_service.create_session()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_service):
        """Test health check failure"""
        session_service.redis.ping = AsyncMock(side_effect=Exception("Connection error"))
        result = await session_service.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl(self, session_service):
        """Test extending TTL"""
        session_service.redis.expire = AsyncMock(return_value=True)
        result = await session_service.extend_ttl("test_session")
        assert result is True

    @pytest.mark.asyncio
    async def test_extend_ttl_exception(self, session_service):
        """Test extending TTL with exception"""
        session_service.redis.expire = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.extend_ttl("test_session")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_session_info(self, session_service):
        """Test getting session info"""
        import json

        session_service.redis.ttl = AsyncMock(return_value=3600)
        session_service.redis.get = AsyncMock(
            return_value=json.dumps([{"role": "user", "content": "test"}])
        )
        result = await session_service.get_session_info("test_session")
        assert result is not None
        assert result["message_count"] == 1
        assert result["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self, session_service):
        """Test getting session info for non-existent session"""
        session_service.redis.ttl = AsyncMock(return_value=-2)
        result = await session_service.get_session_info("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_exception(self, session_service):
        """Test getting session info with exception"""
        session_service.redis.ttl = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.get_session_info("test_session")
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_service):
        """Test cleanup expired sessions"""
        result = await session_service.cleanup_expired_sessions()
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, session_service):
        """Test getting analytics with no sessions"""

        async def mock_scan_iter(pattern):
            return
            yield  # Make it async generator

        session_service.redis.scan_iter = mock_scan_iter
        result = await session_service.get_analytics()
        assert result["total_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_with_sessions(self, session_service):
        """Test getting analytics with sessions"""
        import json

        async def mock_scan_iter(pattern):
            yield "session:session1"
            yield "session:session2"

        session_service.redis.scan_iter = mock_scan_iter
        session_service.redis.get = AsyncMock(
            side_effect=[
                json.dumps([{"role": "user", "content": "test"}] * 5),
                json.dumps([{"role": "user", "content": "test"}] * 15),
            ]
        )

        result = await session_service.get_analytics()
        assert result["total_sessions"] == 2
        assert result["active_sessions"] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_exception(self, session_service):
        """Test getting analytics with exception"""
        session_service.redis.scan_iter = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.get_analytics()
        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_history_with_ttl(self, session_service):
        """Test updating history with custom TTL"""
        session_service.redis.setex = AsyncMock()
        history = [{"role": "user", "content": "test"}]
        result = await session_service.update_history_with_ttl(
            "test_session", history, ttl_hours=48
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_invalid_format(self, session_service):
        """Test updating history with TTL and invalid format"""
        result = await session_service.update_history_with_ttl(
            "test_session", "not a list", ttl_hours=48
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_custom(self, session_service):
        """Test extending TTL with custom hours"""
        session_service.redis.expire = AsyncMock(return_value=True)
        result = await session_service.extend_ttl_custom("test_session", ttl_hours=48)
        assert result is True

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_exception(self, session_service):
        """Test extending TTL custom with exception"""
        session_service.redis.expire = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.extend_ttl_custom("test_session", ttl_hours=48)
        assert result is False

    @pytest.mark.asyncio
    async def test_export_session_json(self, session_service):
        """Test exporting session as JSON"""
        import json

        session_service.redis.get = AsyncMock(
            return_value=json.dumps([{"role": "user", "content": "test"}])
        )
        result = await session_service.export_session("test_session", format="json")
        assert result is not None
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_export_session_markdown(self, session_service):
        """Test exporting session as Markdown"""
        import json

        session_service.redis.get = AsyncMock(
            return_value=json.dumps([{"role": "user", "content": "test"}])
        )
        result = await session_service.export_session("test_session", format="markdown")
        assert result is not None
        assert "# Conversation Export" in result

    @pytest.mark.asyncio
    async def test_export_session_not_found(self, session_service):
        """Test exporting non-existent session"""
        session_service.redis.get = AsyncMock(return_value=None)
        result = await session_service.export_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_export_session_exception(self, session_service):
        """Test exporting session with exception"""
        session_service.redis.get = AsyncMock(side_effect=Exception("Redis error"))
        result = await session_service.export_session("test_session")
        assert result is None

    @pytest.mark.asyncio
    async def test_close(self, session_service):
        """Test closing connection"""
        session_service.redis.close = AsyncMock()
        await session_service.close()
        session_service.redis.close.assert_called_once()

    def test_init_custom_ttl(self):
        """Test initialization with custom TTL"""
        with patch("redis.asyncio.from_url") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client
            service = SessionService(redis_url="redis://localhost:6379", ttl_hours=48)
            assert service.ttl.total_seconds() == 48 * 3600

    def test_init_exception(self):
        """Test initialization with exception"""
        with patch("redis.asyncio.from_url", side_effect=Exception("Connection failed")):
            with pytest.raises(Exception):
                SessionService(redis_url="redis://invalid:6379")
