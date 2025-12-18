"""
Comprehensive tests for SessionService
Target: 100% coverage
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestSessionService:
    """Tests for SessionService class"""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        mock = AsyncMock()
        mock.ping = AsyncMock()
        mock.get = AsyncMock()
        mock.setex = AsyncMock()
        mock.delete = AsyncMock()
        mock.expire = AsyncMock()
        mock.ttl = AsyncMock()
        mock.scan_iter = AsyncMock()
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_redis):
        """Create SessionService instance"""
        with patch("services.session_service.redis.from_url") as mock_from_url:
            mock_from_url.return_value = mock_redis
            from services.session_service import SessionService

            service = SessionService("redis://localhost:6379")
            service.redis = mock_redis
            return service

    def test_init_success(self, mock_redis):
        """Test successful initialization"""
        with patch("services.session_service.redis.from_url") as mock_from_url:
            mock_from_url.return_value = mock_redis
            from services.session_service import SessionService

            service = SessionService("redis://localhost:6379", ttl_hours=48)

            assert service.ttl.total_seconds() == 48 * 3600

    def test_init_failure(self):
        """Test initialization failure"""
        with patch("services.session_service.redis.from_url") as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")
            from services.session_service import SessionService

            with pytest.raises(Exception, match="Connection failed"):
                SessionService("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_health_check_success(self, service, mock_redis):
        """Test successful health check"""
        mock_redis.ping.return_value = True

        result = await service.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, service, mock_redis):
        """Test failed health check"""
        mock_redis.ping.side_effect = Exception("Connection refused")

        result = await service.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_create_session(self, service, mock_redis):
        """Test creating a new session"""
        session_id = await service.create_session()

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_failure(self, service, mock_redis):
        """Test session creation failure"""
        mock_redis.setex.side_effect = Exception("Redis error")

        with pytest.raises(Exception):
            await service.create_session()

    @pytest.mark.asyncio
    async def test_get_history_success(self, service, mock_redis):
        """Test getting session history"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        )

        history = await service.get_history("session123")

        assert history is not None
        assert len(history) == 2
        assert history[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, service, mock_redis):
        """Test getting non-existent session history"""
        mock_redis.get.return_value = None

        history = await service.get_history("nonexistent")

        assert history is None

    @pytest.mark.asyncio
    async def test_get_history_invalid_json(self, service, mock_redis):
        """Test getting history with invalid JSON"""
        mock_redis.get.return_value = "invalid json {"

        history = await service.get_history("session123")

        assert history is None

    @pytest.mark.asyncio
    async def test_get_history_exception(self, service, mock_redis):
        """Test getting history with exception"""
        mock_redis.get.side_effect = Exception("Redis error")

        history = await service.get_history("session123")

        assert history is None

    @pytest.mark.asyncio
    async def test_update_history_success(self, service, mock_redis):
        """Test updating session history"""
        history = [{"role": "user", "content": "Test"}]

        result = await service.update_history("session123", history)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_history_invalid_format(self, service, mock_redis):
        """Test updating with invalid history format"""
        result = await service.update_history("session123", "not a list")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_exception(self, service, mock_redis):
        """Test updating history with exception"""
        mock_redis.setex.side_effect = Exception("Redis error")

        result = await service.update_history("session123", [])

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_success(self, service, mock_redis):
        """Test deleting a session"""
        mock_redis.delete.return_value = 1

        result = await service.delete_session("session123")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_session_not_found(self, service, mock_redis):
        """Test deleting non-existent session"""
        mock_redis.delete.return_value = 0

        result = await service.delete_session("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_session_exception(self, service, mock_redis):
        """Test deleting session with exception"""
        mock_redis.delete.side_effect = Exception("Redis error")

        result = await service.delete_session("session123")

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_success(self, service, mock_redis):
        """Test extending session TTL"""
        mock_redis.expire.return_value = True

        result = await service.extend_ttl("session123")

        assert result is True

    @pytest.mark.asyncio
    async def test_extend_ttl_failure(self, service, mock_redis):
        """Test extending TTL for non-existent session"""
        mock_redis.expire.return_value = False

        result = await service.extend_ttl("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_exception(self, service, mock_redis):
        """Test extending TTL with exception"""
        mock_redis.expire.side_effect = Exception("Redis error")

        result = await service.extend_ttl("session123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_session_info_success(self, service, mock_redis):
        """Test getting session info"""
        mock_redis.ttl.return_value = 3600
        mock_redis.get.return_value = json.dumps([{"role": "user", "content": "Test"}])

        info = await service.get_session_info("session123")

        assert info is not None
        assert info["session_id"] == "session123"
        assert info["message_count"] == 1
        assert info["ttl_seconds"] == 3600
        assert info["ttl_hours"] == 1.0

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self, service, mock_redis):
        """Test getting info for non-existent session"""
        mock_redis.ttl.return_value = -2  # Key doesn't exist

        info = await service.get_session_info("nonexistent")

        assert info is None

    @pytest.mark.asyncio
    async def test_get_session_info_no_data(self, service, mock_redis):
        """Test getting info when data is missing"""
        mock_redis.ttl.return_value = 3600
        mock_redis.get.return_value = None

        info = await service.get_session_info("session123")

        assert info is None

    @pytest.mark.asyncio
    async def test_get_session_info_exception(self, service, mock_redis):
        """Test getting info with exception"""
        mock_redis.ttl.side_effect = Exception("Redis error")

        info = await service.get_session_info("session123")

        assert info is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, service):
        """Test cleanup (no-op for Redis)"""
        result = await service.cleanup_expired_sessions()

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_analytics_success(self, service, mock_redis):
        """Test getting session analytics"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2", "session:3"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([{"role": "user"}] * 5),  # 5 messages
            json.dumps([{"role": "user"}] * 15),  # 15 messages
            json.dumps([{"role": "user"}] * 55),  # 55 messages
        ]

        analytics = await service.get_analytics()

        assert analytics["total_sessions"] == 3
        assert analytics["active_sessions"] == 3
        assert "top_session" in analytics
        assert "sessions_by_range" in analytics

    @pytest.mark.asyncio
    async def test_get_analytics_empty(self, service, mock_redis):
        """Test getting analytics with no sessions"""

        async def mock_scan_iter(pattern):
            return
            yield  # Empty async generator

        mock_redis.scan_iter = mock_scan_iter

        analytics = await service.get_analytics()

        assert analytics["total_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_exception(self, service, mock_redis):
        """Test getting analytics with exception"""

        async def mock_scan_iter(pattern):
            raise Exception("Redis error")
            yield

        mock_redis.scan_iter = mock_scan_iter

        analytics = await service.get_analytics()

        assert "error" in analytics

    @pytest.mark.asyncio
    async def test_get_analytics_invalid_json(self, service, mock_redis):
        """Test analytics with invalid JSON in some sessions"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            "invalid json",  # Invalid
            json.dumps([{"role": "user"}] * 5),  # Valid
        ]

        analytics = await service.get_analytics()

        # Should handle invalid JSON gracefully
        assert analytics["total_sessions"] == 2

    @pytest.mark.asyncio
    async def test_get_analytics_with_top_session(self, service, mock_redis):
        """Test analytics correctly identifies top session"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2", "session:3"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([{"role": "user"}] * 5),  # 5 messages
            json.dumps([{"role": "user"}] * 25),  # 25 messages (top)
            json.dumps([{"role": "user"}] * 10),  # 10 messages
        ]

        analytics = await service.get_analytics()

        assert analytics["top_session"] is not None
        assert analytics["top_session"]["messages"] == 25
        assert analytics["sessions_by_range"]["21-50"] >= 1

    @pytest.mark.asyncio
    async def test_get_analytics_sessions_by_range(self, service, mock_redis):
        """Test analytics categorizes sessions by message count ranges"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2", "session:3", "session:4", "session:5"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([{"role": "user"}] * 5),  # 0-10 range
            json.dumps([{"role": "user"}] * 15),  # 11-20 range
            json.dumps([{"role": "user"}] * 30),  # 21-50 range
            json.dumps([{"role": "user"}] * 60),  # 51+ range
            json.dumps([{"role": "user"}] * 8),  # 0-10 range
        ]

        analytics = await service.get_analytics()

        assert analytics["sessions_by_range"]["0-10"] >= 2
        assert analytics["sessions_by_range"]["11-20"] >= 1
        assert analytics["sessions_by_range"]["21-50"] >= 1
        assert analytics["sessions_by_range"]["51+"] >= 1

    @pytest.mark.asyncio
    async def test_get_analytics_top_session_none(self, service, mock_redis):
        """Test analytics when no sessions have messages (top_session is None)"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([]),  # Empty session
            json.dumps([]),  # Empty session
        ]

        analytics = await service.get_analytics()

        # top_session should be None when no sessions have messages
        assert analytics["top_session"] is None
        assert analytics["active_sessions"] == 0

    @pytest.mark.asyncio
    async def test_get_analytics_empty_message_counts(self, service, mock_redis):
        """Test analytics with empty message_counts list"""

        async def mock_scan_iter(pattern):
            return
            yield  # Empty generator

        mock_redis.scan_iter = mock_scan_iter

        analytics = await service.get_analytics()

        # Should handle empty message_counts gracefully
        assert analytics["avg_messages_per_session"] == 0

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_success(self, service, mock_redis):
        """Test updating history with custom TTL"""
        history = [{"role": "user", "content": "Test"}]

        result = await service.update_history_with_ttl("session123", history, ttl_hours=48)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_default(self, service, mock_redis):
        """Test updating history with default TTL"""
        history = [{"role": "user", "content": "Test"}]

        result = await service.update_history_with_ttl("session123", history)

        assert result is True

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_invalid_format(self, service, mock_redis):
        """Test updating with invalid format"""
        result = await service.update_history_with_ttl("session123", "not a list")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_exception(self, service, mock_redis):
        """Test updating with exception"""
        mock_redis.setex.side_effect = Exception("Redis error")

        result = await service.update_history_with_ttl("session123", [])

        assert result is False

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_success(self, service, mock_redis):
        """Test extending TTL with custom duration"""
        mock_redis.expire.return_value = True

        result = await service.extend_ttl_custom("session123", 72)

        assert result is True

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_exception(self, service, mock_redis):
        """Test extending custom TTL with exception"""
        mock_redis.expire.side_effect = Exception("Redis error")

        result = await service.extend_ttl_custom("session123", 72)

        assert result is False

    @pytest.mark.asyncio
    async def test_export_session_json(self, service, mock_redis):
        """Test exporting session as JSON"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        )

        export = await service.export_session("session123", format="json")

        assert export is not None
        data = json.loads(export)
        assert data["session_id"] == "session123"
        assert data["message_count"] == 2

    @pytest.mark.asyncio
    async def test_export_session_markdown(self, service, mock_redis):
        """Test exporting session as Markdown"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        )

        export = await service.export_session("session123", format="markdown")

        assert export is not None
        assert "# Conversation Export" in export
        assert "👤 User" in export
        assert "🤖 Assistant" in export

    @pytest.mark.asyncio
    async def test_export_session_not_found(self, service, mock_redis):
        """Test exporting non-existent session"""
        mock_redis.get.return_value = None

        export = await service.export_session("nonexistent")

        assert export is None

    @pytest.mark.asyncio
    async def test_export_session_exception(self, service, mock_redis):
        """Test exporting with exception"""
        mock_redis.get.side_effect = Exception("Redis error")

        export = await service.export_session("session123")

        assert export is None

    @pytest.mark.asyncio
    async def test_export_session_unknown_role(self, service, mock_redis):
        """Test exporting session with unknown role"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "unknown", "content": "Test"}, {"role": "user", "content": "Hello"}]
        )

        export = await service.export_session("session123", format="markdown")

        assert export is not None
        assert "Test" in export

    @pytest.mark.asyncio
    async def test_close(self, service, mock_redis):
        """Test closing connection"""
        await service.close()

        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_exception(self, service, mock_redis):
        """Test closing with exception"""
        mock_redis.close.side_effect = Exception("Close error")

        # Should not raise
        await service.close()
