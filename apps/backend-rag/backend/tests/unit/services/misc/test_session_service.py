"""
Unit tests for SessionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.session_service import SessionService


@pytest.fixture
def session_service():
    """Create SessionService instance"""
    with patch('redis.asyncio.from_url') as mock_redis:
        mock_redis_client = AsyncMock()
        mock_redis.return_value = mock_redis_client
        service = SessionService(redis_url="redis://localhost:6379")
        service.redis = mock_redis_client
        return service


class TestSessionService:
    """Tests for SessionService"""

    def test_init(self):
        """Test initialization"""
        with patch('redis.asyncio.from_url') as mock_redis:
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
        import json
        session_service.redis.setex = AsyncMock()
        result = await session_service.create_session()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_history(self, session_service):
        """Test getting session history"""
        import json
        session_service.redis.get = AsyncMock(return_value=json.dumps([{"role": "user", "content": "test"}]))
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
        import json
        session_service.redis.setex = AsyncMock()
        history = [{"role": "user", "content": "test message"}]
        result = await session_service.update_history("test_session", history)
        assert result is True
        session_service.redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session(self, session_service):
        """Test deleting session"""
        session_service.redis.delete = AsyncMock()
        await session_service.delete_session("test_session")
        session_service.redis.delete.assert_called_once()

