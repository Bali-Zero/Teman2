"""
Complete 100% Coverage Tests for Session Service

Tests all methods and edge cases in session_service.py.
"""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_redis():
    """Create mock Redis instance"""
    mock = AsyncMock()
    return mock


@pytest.fixture
def session_service():
    """Create SessionService instance with mocked Redis"""
    with patch("services.session_service.redis") as mock_redis_module:
        mock_client = AsyncMock()
        mock_redis_module.from_url.return_value = mock_client

        from services.session_service import SessionService

        service = SessionService("redis://localhost:6379", ttl_hours=24)
        service.redis = mock_client
        return service


class TestSessionServiceInit:
    """Tests for SessionService initialization"""

    def test_init_success(self):
        """Test successful initialization"""
        with patch("services.session_service.redis") as mock_redis:
            mock_redis.from_url.return_value = AsyncMock()

            from services.session_service import SessionService

            service = SessionService("redis://localhost:6379", ttl_hours=12)

            assert service.ttl == timedelta(hours=12)
            mock_redis.from_url.assert_called_once()

    def test_init_failure(self):
        """Test initialization failure"""
        with patch("services.session_service.redis") as mock_redis:
            mock_redis.from_url.side_effect = Exception("Connection failed")

            from services.session_service import SessionService

            with pytest.raises(Exception, match="Connection failed"):
                SessionService("redis://localhost:6379")


class TestHealthCheck:
    """Tests for health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, session_service):
        """Test successful health check"""
        session_service.redis.ping = AsyncMock()

        result = await session_service.health_check()

        assert result is True
        session_service.redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_service):
        """Test failed health check"""
        session_service.redis.ping.side_effect = Exception("Ping failed")

        result = await session_service.health_check()

        assert result is False


class TestCreateSession:
    """Tests for create_session method"""

    @pytest.mark.asyncio
    async def test_create_session_success(self, session_service):
        """Test successful session creation"""
        session_service.redis.setex = AsyncMock()

        session_id = await session_service.create_session()

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        session_service.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_failure(self, session_service):
        """Test session creation failure"""
        session_service.redis.setex.side_effect = Exception("Redis error")

        with pytest.raises(Exception, match="Redis error"):
            await session_service.create_session()


class TestGetHistory:
    """Tests for get_history method"""

    @pytest.mark.asyncio
    async def test_get_history_success(self, session_service):
        """Test successful history retrieval"""
        history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        session_service.redis.get.return_value = json.dumps(history)

        result = await session_service.get_history("test-session-id")

        assert result == history
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, session_service):
        """Test history not found"""
        session_service.redis.get.return_value = None

        result = await session_service.get_history("nonexistent-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_json_error(self, session_service):
        """Test history with invalid JSON"""
        session_service.redis.get.return_value = "invalid json {"

        result = await session_service.get_history("test-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_redis_error(self, session_service):
        """Test history retrieval with Redis error"""
        session_service.redis.get.side_effect = Exception("Redis error")

        result = await session_service.get_history("test-session")

        assert result is None


class TestUpdateHistory:
    """Tests for update_history method"""

    @pytest.mark.asyncio
    async def test_update_history_success(self, session_service):
        """Test successful history update"""
        session_service.redis.setex = AsyncMock()
        history = [{"role": "user", "content": "Test"}]

        result = await session_service.update_history("test-session", history)

        assert result is True
        session_service.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_history_invalid_format(self, session_service):
        """Test update with invalid format"""
        result = await session_service.update_history("test-session", "not a list")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_redis_error(self, session_service):
        """Test update with Redis error"""
        session_service.redis.setex.side_effect = Exception("Redis error")

        result = await session_service.update_history("test-session", [])

        assert result is False


class TestDeleteSession:
    """Tests for delete_session method"""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, session_service):
        """Test successful session deletion"""
        session_service.redis.delete.return_value = 1

        result = await session_service.delete_session("test-session")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, session_service):
        """Test delete nonexistent session"""
        session_service.redis.delete.return_value = 0

        result = await session_service.delete_session("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_error(self, session_service):
        """Test delete with Redis error"""
        session_service.redis.delete.side_effect = Exception("Redis error")

        result = await session_service.delete_session("test-session")

        assert result is False


class TestExtendTTL:
    """Tests for extend_ttl method"""

    @pytest.mark.asyncio
    async def test_extend_ttl_success(self, session_service):
        """Test successful TTL extension"""
        session_service.redis.expire.return_value = True

        result = await session_service.extend_ttl("test-session")

        assert result is True

    @pytest.mark.asyncio
    async def test_extend_ttl_not_found(self, session_service):
        """Test TTL extension for nonexistent session"""
        session_service.redis.expire.return_value = False

        result = await session_service.extend_ttl("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_error(self, session_service):
        """Test TTL extension with error"""
        session_service.redis.expire.side_effect = Exception("Redis error")

        result = await session_service.extend_ttl("test-session")

        assert result is False


class TestGetSessionInfo:
    """Tests for get_session_info method"""

    @pytest.mark.asyncio
    async def test_get_session_info_success(self, session_service):
        """Test successful session info retrieval"""
        session_service.redis.ttl.return_value = 3600
        session_service.redis.get.return_value = json.dumps([{"role": "user", "content": "Hello"}])

        result = await session_service.get_session_info("test-session")

        assert result is not None
        assert result["session_id"] == "test-session"
        assert result["message_count"] == 1
        assert result["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self, session_service):
        """Test session info for nonexistent session"""
        session_service.redis.ttl.return_value = -2  # Key doesn't exist

        result = await session_service.get_session_info("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_no_data(self, session_service):
        """Test session info with no data"""
        session_service.redis.ttl.return_value = 3600
        session_service.redis.get.return_value = None

        result = await session_service.get_session_info("test-session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_error(self, session_service):
        """Test session info with error"""
        session_service.redis.ttl.side_effect = Exception("Redis error")

        result = await session_service.get_session_info("test-session")

        assert result is None


class TestCleanupExpiredSessions:
    """Tests for cleanup_expired_sessions method"""

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero(self, session_service):
        """Test cleanup always returns 0 (Redis handles TTL)"""
        result = await session_service.cleanup_expired_sessions()

        assert result == 0


class TestGetAnalytics:
    """Tests for get_analytics method"""

    @pytest.mark.asyncio
    async def test_get_analytics_success(self, session_service):
        """Test successful analytics retrieval"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2", "session:3"]:
                yield key

        session_service.redis.scan_iter = mock_scan_iter
        session_service.redis.get.side_effect = [
            json.dumps([{"role": "user", "content": "Hi"}] * 5),  # 5 messages
            json.dumps([{"role": "user", "content": "Hi"}] * 15),  # 15 messages
            json.dumps([{"role": "user", "content": "Hi"}] * 55),  # 55 messages
        ]

        result = await session_service.get_analytics()

        assert result["total_sessions"] == 3
        assert result["active_sessions"] == 3
        assert result["sessions_by_range"]["0-10"] == 1
        assert result["sessions_by_range"]["11-20"] == 1
        assert result["sessions_by_range"]["51+"] == 1

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, session_service):
        """Test analytics with no sessions"""

        async def mock_scan_iter(pattern):
            return
            yield  # Empty generator

        session_service.redis.scan_iter = mock_scan_iter

        result = await session_service.get_analytics()

        assert result["total_sessions"] == 0
        assert result["active_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_json_error(self, session_service):
        """Test analytics with JSON parse error"""

        async def mock_scan_iter(pattern):
            yield "session:1"

        session_service.redis.scan_iter = mock_scan_iter
        session_service.redis.get.return_value = "invalid json"

        result = await session_service.get_analytics()

        # Should handle gracefully
        assert result["total_sessions"] == 1

    @pytest.mark.asyncio
    async def test_get_analytics_error(self, session_service):
        """Test analytics with error"""

        async def mock_scan_iter(pattern):
            raise Exception("Redis error")
            yield

        session_service.redis.scan_iter = mock_scan_iter

        result = await session_service.get_analytics()

        assert "error" in result


class TestUpdateHistoryWithTTL:
    """Tests for update_history_with_ttl method"""

    @pytest.mark.asyncio
    async def test_update_with_custom_ttl(self, session_service):
        """Test update with custom TTL"""
        session_service.redis.setex = AsyncMock()

        result = await session_service.update_history_with_ttl(
            "test-session", [{"role": "user", "content": "Hi"}], ttl_hours=48
        )

        assert result is True
        call_args = session_service.redis.setex.call_args
        assert call_args[0][1] == timedelta(hours=48)

    @pytest.mark.asyncio
    async def test_update_with_default_ttl(self, session_service):
        """Test update with default TTL"""
        session_service.redis.setex = AsyncMock()

        result = await session_service.update_history_with_ttl(
            "test-session", [{"role": "user", "content": "Hi"}]
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_with_ttl_invalid_format(self, session_service):
        """Test update with invalid format"""
        result = await session_service.update_history_with_ttl("test-session", "not a list")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_with_ttl_error(self, session_service):
        """Test update with error"""
        session_service.redis.setex.side_effect = Exception("Redis error")

        result = await session_service.update_history_with_ttl("test-session", [])

        assert result is False


class TestExtendTTLCustom:
    """Tests for extend_ttl_custom method"""

    @pytest.mark.asyncio
    async def test_extend_custom_success(self, session_service):
        """Test successful custom TTL extension"""
        session_service.redis.expire.return_value = True

        result = await session_service.extend_ttl_custom("test-session", 48)

        assert result is True

    @pytest.mark.asyncio
    async def test_extend_custom_failure(self, session_service):
        """Test custom TTL extension failure"""
        session_service.redis.expire.side_effect = Exception("Redis error")

        result = await session_service.extend_ttl_custom("test-session", 48)

        assert result is False


class TestExportSession:
    """Tests for export_session method"""

    @pytest.mark.asyncio
    async def test_export_json(self, session_service):
        """Test JSON export"""
        session_service.get_history = AsyncMock(
            return_value=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        )

        result = await session_service.export_session("test-session", format="json")

        assert result is not None
        data = json.loads(result)
        assert data["session_id"] == "test-session"
        assert data["message_count"] == 2

    @pytest.mark.asyncio
    async def test_export_markdown(self, session_service):
        """Test Markdown export"""
        session_service.get_history = AsyncMock(
            return_value=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ]
        )

        result = await session_service.export_session("test-session", format="markdown")

        assert result is not None
        assert "# Conversation Export" in result
        assert "👤 User" in result
        assert "🤖 Assistant" in result

    @pytest.mark.asyncio
    async def test_export_not_found(self, session_service):
        """Test export for nonexistent session"""
        session_service.get_history = AsyncMock(return_value=None)

        result = await session_service.export_session("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_export_error(self, session_service):
        """Test export with error"""
        session_service.get_history = AsyncMock(side_effect=Exception("Error"))

        result = await session_service.export_session("test-session")

        assert result is None


class TestClose:
    """Tests for close method"""

    @pytest.mark.asyncio
    async def test_close_success(self, session_service):
        """Test successful close"""
        session_service.redis.close = AsyncMock()

        await session_service.close()

        session_service.redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_error(self, session_service):
        """Test close with error"""
        session_service.redis.close.side_effect = Exception("Close error")

        # Should not raise
        await session_service.close()
