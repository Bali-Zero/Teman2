"""
Additional tests for SessionService to reach 95% coverage
Covers edge cases and missing branches
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


class TestSessionServiceAdditional:
    """Additional tests for SessionService"""

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

    @pytest.mark.asyncio
    async def test_get_analytics_with_json_decode_error(self, service, mock_redis):
        """Test analytics with JSON decode error in some sessions"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            "invalid json {",  # Invalid JSON
            json.dumps([{"role": "user"}] * 5),  # Valid
        ]

        analytics = await service.get_analytics()

        # Should handle invalid JSON gracefully
        assert analytics["total_sessions"] == 2
        assert analytics["active_sessions"] >= 1

    @pytest.mark.asyncio
    async def test_get_analytics_with_empty_session_data(self, service, mock_redis):
        """Test analytics with empty session data"""

        async def mock_scan_iter(pattern):
            for key in ["session:1"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.return_value = json.dumps([])  # Empty history

        analytics = await service.get_analytics()

        assert analytics["total_sessions"] == 1
        assert analytics["active_sessions"] == 0  # No messages

    @pytest.mark.asyncio
    async def test_get_analytics_sessions_by_range(self, service, mock_redis):
        """Test analytics categorizes sessions by message count ranges"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2", "session:3", "session:4"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([{"role": "user"}] * 5),  # 5 messages -> 0-10
            json.dumps([{"role": "user"}] * 15),  # 15 messages -> 11-20
            json.dumps([{"role": "user"}] * 30),  # 30 messages -> 21-50
            json.dumps([{"role": "user"}] * 60),  # 60 messages -> 51+
        ]

        analytics = await service.get_analytics()

        assert "sessions_by_range" in analytics
        ranges = analytics["sessions_by_range"]
        assert ranges.get("0-10", 0) >= 1
        assert ranges.get("11-20", 0) >= 1
        assert ranges.get("21-50", 0) >= 1
        assert ranges.get("51+", 0) >= 1

    @pytest.mark.asyncio
    async def test_get_session_info_with_json_decode_error(self, service, mock_redis):
        """Test get_session_info with JSON decode error"""
        mock_redis.ttl.return_value = 3600
        mock_redis.get.return_value = "invalid json {"

        info = await service.get_session_info("session123")

        # Should handle error gracefully
        assert info is None

    @pytest.mark.asyncio
    async def test_export_session_default_format(self, service, mock_redis):
        """Test export_session with default format (should be JSON)"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi!"}]
        )

        export = await service.export_session("session123")

        assert export is not None
        # Should be JSON format by default
        data = json.loads(export)
        assert data["session_id"] == "session123"

    @pytest.mark.asyncio
    async def test_export_session_markdown_with_empty_content(self, service, mock_redis):
        """Test export_session markdown with empty content"""
        mock_redis.get.return_value = json.dumps(
            [{"role": "user", "content": ""}, {"role": "assistant", "content": "Hi!"}]
        )

        export = await service.export_session("session123", format="markdown")

        assert export is not None
        assert "# Conversation Export" in export

    @pytest.mark.asyncio
    async def test_update_history_with_ttl_zero_hours(self, service, mock_redis):
        """Test update_history_with_ttl with zero hours"""
        history = [{"role": "user", "content": "Test"}]

        result = await service.update_history_with_ttl("session123", history, ttl_hours=0)

        assert result is True
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_ttl_custom_with_zero_hours(self, service, mock_redis):
        """Test extend_ttl_custom with zero hours"""
        mock_redis.expire.return_value = True

        result = await service.extend_ttl_custom("session123", ttl_hours=0)

        assert result is True

    @pytest.mark.asyncio
    async def test_get_history_with_empty_string(self, service, mock_redis):
        """Test get_history with empty string data"""
        mock_redis.get.return_value = ""

        history = await service.get_history("session123")

        # Should handle empty string gracefully
        assert history is None

    @pytest.mark.asyncio
    async def test_create_session_generates_uuid(self, service, mock_redis):
        """Test create_session generates valid UUID"""
        session_id = await service.create_session()

        # UUID format: 8-4-4-4-12 hex digits
        import uuid

        try:
            uuid.UUID(session_id)
            assert True
        except ValueError:
            assert False, f"Invalid UUID format: {session_id}"

    @pytest.mark.asyncio
    async def test_export_session_markdown_with_unknown_role(self, service, mock_redis):
        """Test export_session markdown handles unknown role"""
        mock_redis.get.return_value = json.dumps(
            [
                {"role": "system", "content": "System message"},
                {"role": "user", "content": "User message"},
            ]
        )

        export = await service.export_session("session123", format="markdown")

        assert export is not None
        assert "# Conversation Export" in export
        # Unknown role should be handled (defaults to Assistant format)
        assert "User message" in export

    @pytest.mark.asyncio
    async def test_get_analytics_top_session_tracking(self, service, mock_redis):
        """Test analytics tracks top session correctly"""

        async def mock_scan_iter(pattern):
            for key in ["session:1", "session:2"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_redis.get.side_effect = [
            json.dumps([{"role": "user"}] * 10),  # 10 messages
            json.dumps([{"role": "user"}] * 5),  # 5 messages (less)
        ]

        analytics = await service.get_analytics()

        # Top session should be session:1 with 10 messages
        assert analytics["top_session"] is not None
        if analytics["top_session"]:
            assert analytics["top_session"]["messages"] == 10

    @pytest.mark.asyncio
    async def test_get_analytics_with_no_message_counts(self, service, mock_redis):
        """Test analytics when no message counts available"""

        async def mock_scan_iter(pattern):
            return
            yield  # Empty generator

        mock_redis.scan_iter = mock_scan_iter

        analytics = await service.get_analytics()

        assert analytics["total_sessions"] == 0
        assert analytics["active_sessions"] == 0
        assert analytics["avg_messages_per_session"] == 0
