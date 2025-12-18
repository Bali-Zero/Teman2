"""
Integration Tests for SessionService
Tests Redis-based session management with real Redis connection
"""

import json
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest_asyncio.fixture(scope="function")
async def redis_url():
    """Get Redis URL from environment or use default"""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    return redis_url


@pytest_asyncio.fixture(scope="function")
async def session_service(redis_url):
    """Create SessionService instance"""
    from services.session_service import SessionService

    service = SessionService(redis_url, ttl_hours=1)
    # Test connection
    is_healthy = await service.health_check()
    if not is_healthy:
        pytest.skip("Redis not available")

    yield service

    # Cleanup: close connection
    await service.close()


@pytest.mark.integration
@pytest.mark.redis
class TestSessionServiceIntegration:
    """Comprehensive integration tests for SessionService"""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_session(self, session_service):
        """Test creating a session and retrieving it"""
        # Create session
        session_id = await session_service.create_session()
        assert session_id is not None
        assert len(session_id) == 36  # UUID length

        # Retrieve empty history
        history = await session_service.get_history(session_id)
        assert history == []

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_update_history(self, session_service):
        """Test updating session history"""
        session_id = await session_service.create_session()

        # Update with conversation history
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ]
        success = await session_service.update_history(session_id, history)
        assert success is True

        # Retrieve and verify
        retrieved = await session_service.get_history(session_id)
        assert len(retrieved) == 2
        assert retrieved[0]["role"] == "user"
        assert retrieved[0]["content"] == "Hello"

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_extend_ttl(self, session_service):
        """Test extending session TTL"""
        session_id = await session_service.create_session()

        # Get initial TTL
        info_before = await session_service.get_session_info(session_id)
        assert info_before is not None

        # Extend TTL
        extended = await session_service.extend_ttl(session_id)
        assert extended is True

        # Verify TTL was extended
        info_after = await session_service.get_session_info(session_id)
        assert info_after["ttl_seconds"] > 0

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_get_session_info(self, session_service):
        """Test getting session metadata"""
        session_id = await session_service.create_session()

        # Add some messages
        history = [
            {"role": "user", "content": "Message 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Message 2"},
        ]
        await session_service.update_history(session_id, history)

        # Get info
        info = await session_service.get_session_info(session_id)
        assert info is not None
        assert info["session_id"] == session_id
        assert info["message_count"] == 3
        assert info["ttl_seconds"] > 0
        assert info["ttl_hours"] > 0

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_delete_session(self, session_service):
        """Test deleting a session"""
        session_id = await session_service.create_session()

        # Verify exists
        history = await session_service.get_history(session_id)
        assert history is not None

        # Delete
        deleted = await session_service.delete_session(session_id)
        assert deleted is True

        # Verify deleted
        history_after = await session_service.get_history(session_id)
        assert history_after is None

    @pytest.mark.asyncio
    async def test_update_history_with_custom_ttl(self, session_service):
        """Test updating history with custom TTL"""
        session_id = await session_service.create_session()

        history = [{"role": "user", "content": "Test"}]
        success = await session_service.update_history_with_ttl(session_id, history, ttl_hours=2)
        assert success is True

        # Verify TTL was set
        info = await session_service.get_session_info(session_id)
        assert info is not None
        assert info["ttl_hours"] > 1.5  # Should be around 2 hours

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_extend_ttl_custom(self, session_service):
        """Test extending TTL with custom duration"""
        session_id = await session_service.create_session()

        # Extend to 3 hours
        extended = await session_service.extend_ttl_custom(session_id, ttl_hours=3)
        assert extended is True

        # Verify
        info = await session_service.get_session_info(session_id)
        assert info is not None
        assert info["ttl_hours"] > 2.5  # Should be around 3 hours

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_export_session_json(self, session_service):
        """Test exporting session as JSON"""
        session_id = await session_service.create_session()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        await session_service.update_history(session_id, history)

        # Export as JSON
        exported = await session_service.export_session(session_id, format="json")
        assert exported is not None

        # Parse and verify
        data = json.loads(exported)
        assert data["session_id"] == session_id
        assert data["message_count"] == 2
        assert len(data["conversation"]) == 2

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_export_session_markdown(self, session_service):
        """Test exporting session as Markdown"""
        session_id = await session_service.create_session()

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        await session_service.update_history(session_id, history)

        # Export as Markdown
        exported = await session_service.export_session(session_id, format="markdown")
        assert exported is not None
        assert "Conversation Export" in exported
        assert "User" in exported
        assert "Assistant" in exported

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_analytics(self, session_service):
        """Test getting session analytics"""
        # Create multiple sessions with different message counts
        session1 = await session_service.create_session()
        await session_service.update_history(
            session1,
            [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Resp 1"},
            ],
        )

        session2 = await session_service.create_session()
        await session_service.update_history(
            session2,
            [
                {"role": "user", "content": "Msg 1"},
                {"role": "assistant", "content": "Resp 1"},
                {"role": "user", "content": "Msg 2"},
                {"role": "assistant", "content": "Resp 2"},
                {"role": "user", "content": "Msg 3"},
            ],
        )

        # Get analytics
        analytics = await session_service.get_analytics()
        assert analytics is not None
        assert analytics["total_sessions"] >= 2
        assert analytics["active_sessions"] >= 2
        assert analytics["avg_messages_per_session"] > 0
        assert "sessions_by_range" in analytics

        # Cleanup
        await session_service.delete_session(session1)
        await session_service.delete_session(session2)

    @pytest.mark.asyncio
    async def test_invalid_history_format(self, session_service):
        """Test handling invalid history format"""
        session_id = await session_service.create_session()

        # Try to update with invalid format (not a list)
        success = await session_service.update_history(session_id, "not a list")
        assert success is False

        # Cleanup
        await session_service.delete_session(session_id)

    @pytest.mark.asyncio
    async def test_nonexistent_session(self, session_service):
        """Test operations on non-existent session"""
        fake_session_id = "00000000-0000-0000-0000-000000000000"

        # Get history
        history = await session_service.get_history(fake_session_id)
        assert history is None

        # Get info
        info = await session_service.get_session_info(fake_session_id)
        assert info is None

        # Delete (should return False)
        deleted = await session_service.delete_session(fake_session_id)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_health_check(self, session_service):
        """Test Redis health check"""
        is_healthy = await session_service.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, session_service):
        """Test cleanup of expired sessions (no-op, Redis handles automatically)"""
        result = await session_service.cleanup_expired_sessions()
        assert result == 0  # Redis handles cleanup automatically

    @pytest.mark.asyncio
    async def test_large_conversation_history(self, session_service):
        """Test handling large conversation history (50+ messages)"""
        session_id = await session_service.create_session()

        # Create 50+ message conversation
        history = []
        for i in range(60):
            if i % 2 == 0:
                history.append({"role": "user", "content": f"Message {i}"})
            else:
                history.append({"role": "assistant", "content": f"Response {i}"})

        success = await session_service.update_history(session_id, history)
        assert success is True

        # Retrieve and verify
        retrieved = await session_service.get_history(session_id)
        assert len(retrieved) == 60

        # Cleanup
        await session_service.delete_session(session_id)
