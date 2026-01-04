"""
Unit tests for SessionService - targeting 90% coverage
Tests Redis-based conversation history storage
"""

import json
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_redis():
    """Create mock Redis client"""
    mock = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=json.dumps([]))
    mock.delete = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=86400)
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def session_service(mock_redis):
    """Create SessionService with mocked Redis"""
    with patch("services.misc.session_service.redis.from_url", return_value=mock_redis):
        from services.misc.session_service import SessionService

        service = SessionService("redis://localhost:6379", ttl_hours=24)
        return service


# ============================================================================
# INIT TESTS
# ============================================================================


class TestSessionServiceInit:
    """Tests for SessionService initialization"""

    def test_init_success(self, mock_redis):
        """Test successful initialization"""
        with patch("services.misc.session_service.redis.from_url", return_value=mock_redis):
            from services.misc.session_service import SessionService

            service = SessionService("redis://localhost:6379", ttl_hours=24)

            assert service.ttl == timedelta(hours=24)

    def test_init_custom_ttl(self, mock_redis):
        """Test initialization with custom TTL"""
        with patch("services.misc.session_service.redis.from_url", return_value=mock_redis):
            from services.misc.session_service import SessionService

            service = SessionService("redis://localhost:6379", ttl_hours=48)

            assert service.ttl == timedelta(hours=48)

    def test_init_failure(self):
        """Test initialization failure"""
        with patch(
            "services.misc.session_service.redis.from_url",
            side_effect=Exception("Connection failed"),
        ):
            from services.misc.session_service import SessionService

            with pytest.raises(Exception) as exc_info:
                SessionService("redis://invalid:6379")

            assert "Connection failed" in str(exc_info.value)


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================


class TestHealthCheck:
    """Tests for health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_success(self, session_service, mock_redis):
        """Test successful health check"""
        mock_redis.ping = AsyncMock(return_value=True)

        result = await session_service.health_check()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, session_service, mock_redis):
        """Test health check with Redis failure"""
        mock_redis.ping = AsyncMock(side_effect=Exception("Connection lost"))

        result = await session_service.health_check()

        assert result is False


# ============================================================================
# CREATE SESSION TESTS
# ============================================================================


class TestCreateSession:
    """Tests for create_session method"""

    @pytest.mark.asyncio
    async def test_create_session_success(self, session_service, mock_redis):
        """Test successful session creation"""
        session_id = await session_service.create_session()

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_failure(self, session_service, mock_redis):
        """Test session creation failure"""
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))

        with pytest.raises(Exception) as exc_info:
            await session_service.create_session()

        assert "Redis error" in str(exc_info.value)


# ============================================================================
# GET HISTORY TESTS
# ============================================================================


class TestGetHistory:
    """Tests for get_history method"""

    @pytest.mark.asyncio
    async def test_get_history_success(self, session_service, mock_redis):
        """Test successful history retrieval"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        mock_redis.get = AsyncMock(return_value=json.dumps(history))

        result = await session_service.get_history("session_123")

        assert result == history
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, session_service, mock_redis):
        """Test history retrieval for non-existent session"""
        mock_redis.get = AsyncMock(return_value=None)

        result = await session_service.get_history("nonexistent_session")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_json_decode_error(self, session_service, mock_redis):
        """Test history retrieval with invalid JSON"""
        mock_redis.get = AsyncMock(return_value="invalid json {{{")

        result = await session_service.get_history("session_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_history_redis_error(self, session_service, mock_redis):
        """Test history retrieval with Redis error"""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection lost"))

        result = await session_service.get_history("session_123")

        assert result is None


# ============================================================================
# UPDATE HISTORY TESTS
# ============================================================================


class TestUpdateHistory:
    """Tests for update_history method"""

    @pytest.mark.asyncio
    async def test_update_history_success(self, session_service, mock_redis):
        """Test successful history update"""
        history = [{"role": "user", "content": "Hello"}]

        result = await session_service.update_history("session_123", history)

        assert result is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_update_history_invalid_format(self, session_service, mock_redis):
        """Test history update with invalid format"""
        result = await session_service.update_history("session_123", "not a list")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_redis_error(self, session_service, mock_redis):
        """Test history update with Redis error"""
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        history = [{"role": "user", "content": "Hello"}]

        result = await session_service.update_history("session_123", history)

        assert result is False


# ============================================================================
# DELETE SESSION TESTS
# ============================================================================


class TestDeleteSession:
    """Tests for delete_session method"""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, session_service, mock_redis):
        """Test successful session deletion"""
        mock_redis.delete = AsyncMock(return_value=1)

        result = await session_service.delete_session("session_123")

        assert result is True
        mock_redis.delete.assert_called_with("session:session_123")

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, session_service, mock_redis):
        """Test deletion of non-existent session"""
        mock_redis.delete = AsyncMock(return_value=0)

        result = await session_service.delete_session("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_redis_error(self, session_service, mock_redis):
        """Test deletion with Redis error"""
        mock_redis.delete = AsyncMock(side_effect=Exception("Redis error"))

        result = await session_service.delete_session("session_123")

        assert result is False


# ============================================================================
# EXTEND TTL TESTS
# ============================================================================


class TestExtendTtl:
    """Tests for extend_ttl method"""

    @pytest.mark.asyncio
    async def test_extend_ttl_success(self, session_service, mock_redis):
        """Test successful TTL extension"""
        mock_redis.expire = AsyncMock(return_value=True)

        result = await session_service.extend_ttl("session_123")

        assert result is True
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_ttl_session_not_found(self, session_service, mock_redis):
        """Test TTL extension for non-existent session"""
        mock_redis.expire = AsyncMock(return_value=False)

        result = await session_service.extend_ttl("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_redis_error(self, session_service, mock_redis):
        """Test TTL extension with Redis error"""
        mock_redis.expire = AsyncMock(side_effect=Exception("Redis error"))

        result = await session_service.extend_ttl("session_123")

        assert result is False


# ============================================================================
# GET SESSION INFO TESTS
# ============================================================================


class TestGetSessionInfo:
    """Tests for get_session_info method"""

    @pytest.mark.asyncio
    async def test_get_session_info_success(self, session_service, mock_redis):
        """Test successful session info retrieval"""
        history = [{"role": "user", "content": "Hello"}]
        mock_redis.ttl = AsyncMock(return_value=3600)
        mock_redis.get = AsyncMock(return_value=json.dumps(history))

        result = await session_service.get_session_info("session_123")

        assert result is not None
        assert result["session_id"] == "session_123"
        assert result["message_count"] == 1
        assert result["ttl_seconds"] == 3600
        assert result["ttl_hours"] == 1.0

    @pytest.mark.asyncio
    async def test_get_session_info_key_not_exists(self, session_service, mock_redis):
        """Test session info for non-existent key"""
        mock_redis.ttl = AsyncMock(return_value=-2)

        result = await session_service.get_session_info("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_no_data(self, session_service, mock_redis):
        """Test session info when data is missing"""
        mock_redis.ttl = AsyncMock(return_value=3600)
        mock_redis.get = AsyncMock(return_value=None)

        result = await session_service.get_session_info("session_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_info_redis_error(self, session_service, mock_redis):
        """Test session info with Redis error"""
        mock_redis.ttl = AsyncMock(side_effect=Exception("Redis error"))

        result = await session_service.get_session_info("session_123")

        assert result is None


# ============================================================================
# CLEANUP EXPIRED SESSIONS TEST
# ============================================================================


class TestCleanupExpiredSessions:
    """Tests for cleanup_expired_sessions method"""

    @pytest.mark.asyncio
    async def test_cleanup_returns_zero(self, session_service):
        """Test cleanup always returns 0 (Redis auto-cleans)"""
        result = await session_service.cleanup_expired_sessions()

        assert result == 0


# ============================================================================
# GET ANALYTICS TESTS
# ============================================================================


class TestGetAnalytics:
    """Tests for get_analytics method"""

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, session_service, mock_redis):
        """Test analytics with no sessions"""

        async def empty_scan_iter(*args, **kwargs):
            return
            yield  # Make it an async generator that yields nothing

        mock_redis.scan_iter = empty_scan_iter

        result = await session_service.get_analytics()

        assert result["total_sessions"] == 0
        assert result["active_sessions"] == 0
        assert result["avg_messages_per_session"] == 0
        assert result["top_session"] is None

    @pytest.mark.asyncio
    async def test_get_analytics_with_sessions(self, session_service, mock_redis):
        """Test analytics with sessions"""
        sessions = {
            "session:sess1": json.dumps([{"role": "user", "content": "Hello"}]),
            "session:sess2": json.dumps(
                [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"},
                ]
            ),
        }

        async def mock_scan_iter(*args, **kwargs):
            for key in sessions.keys():
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get = AsyncMock(side_effect=lambda k: sessions.get(k))

        result = await session_service.get_analytics()

        assert result["total_sessions"] == 2
        assert result["active_sessions"] == 2
        assert result["avg_messages_per_session"] == 1.5
        assert result["top_session"]["messages"] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_with_ranges(self, session_service, mock_redis):
        """Test analytics message count ranges"""
        sessions = {
            "session:small": json.dumps([{"role": "user", "content": "x"}] * 5),
            "session:medium": json.dumps([{"role": "user", "content": "x"}] * 15),
            "session:large": json.dumps([{"role": "user", "content": "x"}] * 35),
            "session:xlarge": json.dumps([{"role": "user", "content": "x"}] * 60),
        }

        async def mock_scan_iter(*args, **kwargs):
            for key in sessions.keys():
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get = AsyncMock(side_effect=lambda k: sessions.get(k))

        result = await session_service.get_analytics()

        assert result["sessions_by_range"]["0-10"] == 1
        assert result["sessions_by_range"]["11-20"] == 1
        assert result["sessions_by_range"]["21-50"] == 1
        assert result["sessions_by_range"]["51+"] == 1

    @pytest.mark.asyncio
    async def test_get_analytics_json_decode_error(self, session_service, mock_redis):
        """Test analytics with invalid JSON in session"""
        sessions = {
            "session:valid": json.dumps([{"role": "user", "content": "Hi"}]),
            "session:invalid": "not valid json {{",
        }

        async def mock_scan_iter(*args, **kwargs):
            for key in sessions.keys():
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get = AsyncMock(side_effect=lambda k: sessions.get(k))

        result = await session_service.get_analytics()

        # Should handle gracefully, only count valid session
        assert result["total_sessions"] == 2
        assert result["active_sessions"] == 1

    @pytest.mark.asyncio
    async def test_get_analytics_redis_error(self, session_service, mock_redis):
        """Test analytics with Redis error"""

        async def error_scan_iter(*args, **kwargs):
            raise Exception("Redis error")
            yield  # Make it an async generator

        mock_redis.scan_iter = error_scan_iter

        result = await session_service.get_analytics()

        assert "error" in result
        assert result["total_sessions"] == 0


# ============================================================================
# UPDATE HISTORY WITH TTL TESTS
# ============================================================================


class TestUpdateHistoryWithTtl:
    """Tests for update_history_with_ttl method"""

    @pytest.mark.asyncio
    async def test_update_history_with_custom_ttl(self, session_service, mock_redis):
        """Test history update with custom TTL"""
        history = [{"role": "user", "content": "Hello"}]

        result = await session_service.update_history_with_ttl("session_123", history, ttl_hours=48)

        assert result is True
        # Verify setex was called with custom TTL
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == timedelta(hours=48)

    @pytest.mark.asyncio
    async def test_update_history_with_default_ttl(self, session_service, mock_redis):
        """Test history update with default TTL"""
        history = [{"role": "user", "content": "Hello"}]

        result = await session_service.update_history_with_ttl(
            "session_123", history, ttl_hours=None
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_invalid_format(self, session_service, mock_redis):
        """Test history update with invalid format"""
        result = await session_service.update_history_with_ttl(
            "session_123", "not a list", ttl_hours=24
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_redis_error(self, session_service, mock_redis):
        """Test history update with Redis error"""
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        history = [{"role": "user", "content": "Hello"}]

        result = await session_service.update_history_with_ttl("session_123", history, ttl_hours=24)

        assert result is False


# ============================================================================
# EXTEND TTL CUSTOM TESTS
# ============================================================================


class TestExtendTtlCustom:
    """Tests for extend_ttl_custom method"""

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_success(self, session_service, mock_redis):
        """Test successful custom TTL extension"""
        mock_redis.expire = AsyncMock(return_value=True)

        result = await session_service.extend_ttl_custom("session_123", 72)

        assert result is True
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == timedelta(hours=72)

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_session_not_found(self, session_service, mock_redis):
        """Test custom TTL extension for non-existent session"""
        mock_redis.expire = AsyncMock(return_value=False)

        result = await session_service.extend_ttl_custom("nonexistent", 48)

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_redis_error(self, session_service, mock_redis):
        """Test custom TTL extension with Redis error"""
        mock_redis.expire = AsyncMock(side_effect=Exception("Redis error"))

        result = await session_service.extend_ttl_custom("session_123", 48)

        assert result is False


# ============================================================================
# EXPORT SESSION TESTS
# ============================================================================


class TestExportSession:
    """Tests for export_session method"""

    @pytest.mark.asyncio
    async def test_export_session_json(self, session_service, mock_redis):
        """Test session export as JSON"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        mock_redis.get = AsyncMock(return_value=json.dumps(history))

        result = await session_service.export_session("session_123", format="json")

        assert result is not None
        parsed = json.loads(result)
        assert parsed["session_id"] == "session_123"
        assert parsed["message_count"] == 2
        assert len(parsed["conversation"]) == 2

    @pytest.mark.asyncio
    async def test_export_session_markdown(self, session_service, mock_redis):
        """Test session export as Markdown"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        mock_redis.get = AsyncMock(return_value=json.dumps(history))

        result = await session_service.export_session("session_123", format="markdown")

        assert result is not None
        assert "# Conversation Export" in result
        assert "session_123" in result
        assert "User" in result
        assert "Assistant" in result
        assert "Hello" in result
        assert "Hi there!" in result

    @pytest.mark.asyncio
    async def test_export_session_not_found(self, session_service, mock_redis):
        """Test export of non-existent session"""
        mock_redis.get = AsyncMock(return_value=None)

        result = await session_service.export_session("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_export_session_error(self, session_service, mock_redis):
        """Test export with error"""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        result = await session_service.export_session("session_123")

        assert result is None


# ============================================================================
# CLOSE TESTS
# ============================================================================


class TestClose:
    """Tests for close method"""

    @pytest.mark.asyncio
    async def test_close_success(self, session_service, mock_redis):
        """Test successful connection close"""
        await session_service.close()

        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_error(self, session_service, mock_redis):
        """Test close with error"""
        mock_redis.close = AsyncMock(side_effect=Exception("Close error"))

        # Should not raise
        await session_service.close()
