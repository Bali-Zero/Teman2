"""
API Tests for WebSocket Router
Tests WebSocket connection management

Note: WebSocket testing is limited - full testing requires WebSocket client
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["REDIS_URL"] = "redis://localhost:6379"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.api
class TestWebSocketEndpoints:
    """Tests for WebSocket endpoints"""

    @pytest.mark.asyncio
    async def test_websocket_endpoint_requires_token(self):
        """Test that WebSocket endpoint requires token"""
        # WebSocket connections can't be easily tested with TestClient
        # This test verifies the endpoint exists and requires authentication
        # Full WebSocket testing would require a WebSocket client library

        # Try to connect without token - should fail
        # Note: TestClient doesn't support WebSocket, so we test the validation logic
        from app.routers.websocket import get_current_user_ws

        # Test token validation function
        result = await get_current_user_ws("invalid_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_websocket_token_validation_valid(self):
        """Test WebSocket token validation with valid token"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from app.routers.websocket import get_current_user_ws

        # Create valid token
        payload = {
            "sub": "test@example.com",
            "userId": "test-user-123",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        user_id = await get_current_user_ws(token)
        assert user_id == "test@example.com" or user_id == "test-user-123"

    @pytest.mark.asyncio
    async def test_websocket_token_validation_invalid(self):
        """Test WebSocket token validation with invalid token"""
        from app.routers.websocket import get_current_user_ws

        user_id = await get_current_user_ws("invalid_token")
        assert user_id is None

    @pytest.mark.asyncio
    async def test_websocket_token_validation_expired(self):
        """Test WebSocket token validation with expired token"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from app.routers.websocket import get_current_user_ws

        # Create expired token
        payload = {
            "sub": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        user_id = await get_current_user_ws(token)
        assert user_id is None

    def test_connection_manager_initialization(self):
        """Test ConnectionManager initialization"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        assert manager.active_connections == {}
        assert manager.lock is not None

    @pytest.mark.asyncio
    async def test_connection_manager_connect(self):
        """Test ConnectionManager connect method"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, "user123")

        assert "user123" in manager.active_connections
        assert len(manager.active_connections["user123"]) == 1

    @pytest.mark.asyncio
    async def test_connection_manager_disconnect(self):
        """Test ConnectionManager disconnect method"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.disconnect(mock_websocket, "user123")

        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_connection_manager_send_personal_message(self):
        """Test ConnectionManager send_personal_message"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message({"type": "test"}, "user123")

        mock_websocket.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """Test ConnectionManager broadcast"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user2")
        await manager.broadcast({"type": "broadcast"})

        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_listener_initialization(self):
        """Test Redis listener initialization"""
        from unittest.mock import patch

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = None
            from app.routers.websocket import redis_listener

            # Should return early if Redis URL not set
            await redis_listener()

    @pytest.mark.asyncio
    async def test_redis_listener_subscription(self):
        """Test Redis listener subscription"""
        from unittest.mock import AsyncMock, MagicMock, patch

        with (
            patch("app.routers.websocket.settings") as mock_settings,
            patch("app.routers.websocket.redis") as mock_redis,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client = MagicMock()
            mock_pubsub = MagicMock()
            mock_pubsub.psubscribe = AsyncMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_pubsub.listen = AsyncMock()
            mock_pubsub.close = AsyncMock()
            mock_client.pubsub.return_value = mock_pubsub
            mock_redis.from_url.return_value = mock_client

            # Start listener (will be cancelled immediately)
            import asyncio

            from app.routers.websocket import redis_listener

            task = asyncio.create_task(redis_listener())
            await asyncio.sleep(0.1)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_connection_manager_multiple_connections_same_user(self):
        """Test ConnectionManager with multiple connections for same user"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()

        await manager.connect(mock_ws1, "user123")
        await manager.connect(mock_ws2, "user123")

        assert "user123" in manager.active_connections
        assert len(manager.active_connections["user123"]) == 2

    @pytest.mark.asyncio
    async def test_connection_manager_send_to_nonexistent_user(self):
        """Test sending message to nonexistent user"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        # Should not raise error
        await manager.send_personal_message({"type": "test"}, "nonexistent")
