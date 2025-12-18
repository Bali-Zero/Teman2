"""
API Tests for WebSocket Router - Coverage 95% Target
Tests all WebSocket functionality and edge cases to achieve 95% coverage

Coverage:
- WebSocket endpoint /ws with all authentication methods
- ConnectionManager methods (connect, disconnect, send_personal_message, broadcast)
- get_current_user_ws token validation
- Redis Pub/Sub listener edge cases
- Error handling and edge cases
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test ConnectionManager
# ============================================================================


class TestConnectionManager:
    """Test suite for ConnectionManager class"""

    @pytest.mark.asyncio
    async def test_connect_new_user(self):
        """Test connecting a new user"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket, "user123")

        assert "user123" in manager.active_connections
        assert len(manager.active_connections["user123"]) == 1
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_existing_user(self):
        """Test connecting additional websocket for existing user"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user123")
        await manager.connect(mock_ws2, "user123")

        assert len(manager.active_connections["user123"]) == 2

    @pytest.mark.asyncio
    async def test_disconnect_user(self):
        """Test disconnecting a user"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket, "user123")
        await manager.disconnect(mock_websocket, "user123")

        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_user_multiple_connections(self):
        """Test disconnecting one connection when user has multiple"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user123")
        await manager.connect(mock_ws2, "user123")
        await manager.disconnect(mock_ws1, "user123")

        assert "user123" in manager.active_connections
        assert len(manager.active_connections["user123"]) == 1
        assert mock_ws2 in manager.active_connections["user123"]

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self):
        """Test sending personal message successfully"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message({"type": "test", "data": "message"}, "user123")

        mock_websocket.send_json.assert_called_once_with({"type": "test", "data": "message"})

    @pytest.mark.asyncio
    async def test_send_personal_message_no_user(self):
        """Test sending personal message to non-existent user"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()

        # Should not raise error
        await manager.send_personal_message({"type": "test"}, "nonexistent")

    @pytest.mark.asyncio
    async def test_send_personal_message_connection_error(self):
        """Test sending personal message when connection fails"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock(side_effect=Exception("Connection error"))

        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message({"type": "test"}, "user123")

        # Should disconnect dead connection
        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting to all users"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws1.send_json = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user2")

        await manager.broadcast({"type": "broadcast", "data": "message"})

        mock_ws1.send_json.assert_called_once()
        mock_ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_empty(self):
        """Test broadcasting when no connections exist"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()

        # Should not raise error
        await manager.broadcast({"type": "test"})


# ============================================================================
# Test Token Validation
# ============================================================================


class TestTokenValidation:
    """Test suite for get_current_user_ws function"""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test getting user from valid token"""
        from app.routers.websocket import get_current_user_ws

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        user_id = await get_current_user_ws(token)

        assert user_id == "user123"

    @pytest.mark.asyncio
    async def test_get_current_user_token_with_userid(self):
        """Test getting user from token with userId field"""
        from app.routers.websocket import get_current_user_ws

        payload = {"userId": "user456", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        user_id = await get_current_user_ws(token)

        assert user_id == "user456"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test getting user from invalid token"""
        from app.routers.websocket import get_current_user_ws

        user_id = await get_current_user_ws("invalid_token")

        assert user_id is None

    @pytest.mark.asyncio
    async def test_get_current_user_no_user_field(self):
        """Test getting user from token without sub or userId"""
        from app.routers.websocket import get_current_user_ws

        payload = {"exp": 9999999999}  # No sub or userId
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        user_id = await get_current_user_ws(token)

        assert user_id is None


# ============================================================================
# Test WebSocket Endpoint
# ============================================================================


class TestWebSocketEndpoint:
    """Test suite for /ws WebSocket endpoint"""

    @pytest.mark.asyncio
    async def test_websocket_auth_header(self):
        """Test WebSocket connection with Authorization header"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"authorization": f"Bearer {token}"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("app.routers.websocket.manager") as mock_manager:
            await websocket_endpoint(mock_websocket)

            mock_manager.connect.assert_called_once()
            mock_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_subprotocol(self):
        """Test WebSocket connection with subprotocol"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = [f"bearer.{token}"]
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("app.routers.websocket.manager") as mock_manager:
            await websocket_endpoint(mock_websocket)

            mock_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_query_param(self):
        """Test WebSocket connection with query param (deprecated)"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = f"token={token}"
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("app.routers.websocket.manager") as mock_manager:
            await websocket_endpoint(mock_websocket)

            mock_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_no_token(self):
        """Test WebSocket connection without token"""
        from app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.close = AsyncMock()

        await websocket_endpoint(mock_websocket)

        mock_websocket.close.assert_called_once_with(code=4003, reason="Authentication required")

    @pytest.mark.asyncio
    async def test_websocket_invalid_token(self):
        """Test WebSocket connection with invalid token"""
        from app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"authorization": "Bearer invalid_token"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.close = AsyncMock()

        await websocket_endpoint(mock_websocket)

        mock_websocket.close.assert_called_once_with(code=4003, reason="Invalid token")

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self):
        """Test WebSocket ping/pong keepalive"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"authorization": f"Bearer {token}"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.send_json = AsyncMock()

        # Simulate ping message then disconnect
        call_count = 0

        async def receive_text():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"type": "ping"}'
            raise WebSocketDisconnect()

        mock_websocket.receive_text = receive_text

        with patch("app.routers.websocket.manager") as mock_manager:
            await websocket_endpoint(mock_websocket)

            # Should send pong response
            mock_websocket.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_websocket_non_json_message(self):
        """Test WebSocket with non-JSON message"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"authorization": f"Bearer {token}"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        # Simulate non-JSON message then disconnect
        call_count = 0

        async def receive_text():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "not json"
            raise WebSocketDisconnect()

        mock_websocket.receive_text = receive_text

        with patch("app.routers.websocket.manager") as mock_manager:
            # Should not raise error
            await websocket_endpoint(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_general_error(self):
        """Test WebSocket endpoint error handling"""
        from app.routers.websocket import websocket_endpoint

        payload = {"sub": "user123", "exp": 9999999999}
        token = jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"authorization": f"Bearer {token}"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("General error"))

        with patch("app.routers.websocket.manager") as mock_manager:
            await websocket_endpoint(mock_websocket)

            # Should disconnect on error
            mock_manager.disconnect.assert_called_once()


# ============================================================================
# Test Redis Listener
# ============================================================================


class TestRedisListener:
    """Test suite for redis_listener function"""

    @pytest.mark.asyncio
    async def test_redis_listener_no_redis_url(self):
        """Test redis_listener when Redis URL not set"""
        from app.routers.websocket import redis_listener

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = None

            # Should return early without error
            await redis_listener()

    @pytest.mark.asyncio
    async def test_redis_listener_user_notifications(self):
        """Test redis_listener handling USER_NOTIFICATIONS channel"""
        from app.routers.websocket import redis_listener

        mock_message = {
            "type": "pmessage",
            "channel": "CHANNELS.USER_NOTIFICATIONS:user123",
            "data": '{"notification": "test"}',
        }

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.listen = AsyncMock(return_value=iter([mock_message]))

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                with patch("app.routers.websocket.manager") as mock_manager:
                    # Simulate cancellation after one message
                    async def listen_gen():
                        yield mock_message
                        raise asyncio.CancelledError()

                    mock_pubsub.listen = listen_gen()

                    await redis_listener()

                    mock_manager.send_personal_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_listener_ai_results(self):
        """Test redis_listener handling AI_RESULTS channel"""
        import asyncio

        from app.routers.websocket import redis_listener

        mock_message = {
            "type": "pmessage",
            "channel": "CHANNELS.AI_RESULTS:user456",
            "data": '{"result": "test"}',
        }

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                with patch("app.routers.websocket.manager") as mock_manager:

                    async def listen_gen():
                        yield mock_message
                        raise asyncio.CancelledError()

                    mock_pubsub.listen = listen_gen()

                    await redis_listener()

                    mock_manager.send_personal_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_listener_chat_messages(self):
        """Test redis_listener handling CHAT_MESSAGES channel"""
        import asyncio

        from app.routers.websocket import redis_listener

        mock_message = {
            "type": "pmessage",
            "channel": "CHANNELS.CHAT_MESSAGES:room123",
            "data": '{"message": "hello"}',
        }

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                with patch("app.routers.websocket.manager") as mock_manager:

                    async def listen_gen():
                        yield mock_message
                        raise asyncio.CancelledError()

                    mock_pubsub.listen = listen_gen()

                    await redis_listener()

                    mock_manager.send_personal_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_listener_system_events(self):
        """Test redis_listener handling SYSTEM_EVENTS channel"""
        import asyncio

        from app.routers.websocket import redis_listener

        mock_message = {
            "type": "message",
            "channel": "CHANNELS.SYSTEM_EVENTS",
            "data": '{"event": "system"}',
        }

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                with patch("app.routers.websocket.manager") as mock_manager:

                    async def listen_gen():
                        yield mock_message
                        raise asyncio.CancelledError()

                    mock_pubsub.listen = listen_gen()

                    await redis_listener()

                    mock_manager.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_redis_listener_invalid_json(self):
        """Test redis_listener with invalid JSON data"""
        import asyncio

        from app.routers.websocket import redis_listener

        mock_message = {
            "type": "message",
            "channel": "CHANNELS.USER_NOTIFICATIONS:user123",
            "data": "not json",
        }

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                with patch("app.routers.websocket.manager") as mock_manager:

                    async def listen_gen():
                        yield mock_message
                        raise asyncio.CancelledError()

                    mock_pubsub.listen = listen_gen()

                    # Should handle invalid JSON gracefully
                    await redis_listener()

                    # Should still send message with raw_data
                    assert mock_manager.send_personal_message.called

    @pytest.mark.asyncio
    async def test_redis_listener_error(self):
        """Test redis_listener error handling"""
        from app.routers.websocket import redis_listener

        mock_pubsub = AsyncMock()
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_pubsub.listen = AsyncMock(side_effect=Exception("Redis error"))

        mock_redis = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()

        with patch("app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = "redis://localhost:6379"

            with patch("app.routers.websocket.redis.from_url", return_value=mock_redis):
                # Should handle error gracefully
                await redis_listener()

                mock_pubsub.close.assert_called_once()
                mock_redis.close.assert_called_once()
