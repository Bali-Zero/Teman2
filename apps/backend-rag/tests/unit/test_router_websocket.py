"""
Unit tests for WebSocket Router & Connection Manager
Tests real-time notification handling via WebSocket connections

Coverage:
- ConnectionManager class (connect, disconnect, messaging)
- WebSocket endpoint authentication
- JWT token validation for WebSocket
- Personal message sending
- Broadcast functionality
- Redis Pub/Sub listener (mocked)
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-minimum-32-characters-long"
    settings.jwt_algorithm = "HS256"
    settings.redis_url = "redis://localhost:6379"
    return settings


@pytest.fixture
def mock_settings_no_redis():
    """Mock settings without Redis URL"""
    settings = MagicMock()
    settings.jwt_secret_key = "test-secret-key-minimum-32-characters-long"
    settings.jwt_algorithm = "HS256"
    settings.redis_url = None
    return settings


@pytest.fixture
def valid_jwt_token(mock_settings):
    """Generate a valid JWT token for WebSocket authentication"""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": "test-user-123",
        "userId": "test-user-123",
        "email": "test@example.com",
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")
    return token


@pytest.fixture
def expired_jwt_token(mock_settings):
    """Generate an expired JWT token"""
    from datetime import datetime, timezone

    from jose import jwt

    exp = datetime.now(timezone.utc).timestamp() - 3600  # 1 hour ago
    payload = {
        "sub": "test-user-123",
        "exp": int(exp),
    }
    token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")
    return token


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection"""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.headers = {}  # SECURITY: Token now comes from headers/subprotocol, not query param
    ws.subprotocols = []
    ws.url = MagicMock()
    ws.url.query = ""
    return ws


@pytest.fixture
def connection_manager():
    """Create a fresh ConnectionManager instance"""
    with patch("app.routers.websocket.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret-key-minimum-32-characters-long"
        mock_settings.jwt_algorithm = "HS256"

        from app.routers.websocket import ConnectionManager

        return ConnectionManager()


# ============================================================================
# ConnectionManager Initialization Tests
# ============================================================================


class TestConnectionManagerInit:
    """Tests for ConnectionManager initialization"""

    def test_init_creates_empty_connections(self):
        """Test that ConnectionManager starts with empty connections"""
        with patch("app.routers.websocket.settings"):
            from app.routers.websocket import ConnectionManager

            manager = ConnectionManager()

            assert manager.active_connections == {}
            assert manager.lock is not None


# ============================================================================
# Connection Management Tests
# ============================================================================


class TestConnectionManagement:
    """Tests for WebSocket connection lifecycle"""

    @pytest.mark.asyncio
    async def test_connect_new_user(self, connection_manager, mock_websocket):
        """Test connecting a new user"""
        user_id = "new-user-123"

        await connection_manager.connect(mock_websocket, user_id)

        mock_websocket.accept.assert_called_once()
        assert user_id in connection_manager.active_connections
        assert mock_websocket in connection_manager.active_connections[user_id]

    @pytest.mark.asyncio
    async def test_connect_multiple_connections_same_user(self, connection_manager, mock_websocket):
        """Test multiple connections from the same user"""
        user_id = "multi-conn-user"
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await connection_manager.connect(ws1, user_id)
        await connection_manager.connect(ws2, user_id)

        assert len(connection_manager.active_connections[user_id]) == 2
        assert ws1 in connection_manager.active_connections[user_id]
        assert ws2 in connection_manager.active_connections[user_id]

    @pytest.mark.asyncio
    async def test_connect_different_users(self, connection_manager):
        """Test connecting different users"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await connection_manager.connect(ws1, "user-1")
        await connection_manager.connect(ws2, "user-2")

        assert "user-1" in connection_manager.active_connections
        assert "user-2" in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self, connection_manager, mock_websocket):
        """Test that disconnect removes the connection"""
        user_id = "disconnect-user"

        await connection_manager.connect(mock_websocket, user_id)
        assert user_id in connection_manager.active_connections

        await connection_manager.disconnect(mock_websocket, user_id)

        # User should be removed when last connection is closed
        assert user_id not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_connections(self, connection_manager):
        """Test that disconnecting one connection keeps others"""
        user_id = "multi-conn-user"
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()

        await connection_manager.connect(ws1, user_id)
        await connection_manager.connect(ws2, user_id)

        await connection_manager.disconnect(ws1, user_id)

        assert user_id in connection_manager.active_connections
        assert len(connection_manager.active_connections[user_id]) == 1
        assert ws2 in connection_manager.active_connections[user_id]

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_user(self, connection_manager, mock_websocket):
        """Test disconnecting a user that doesn't exist"""
        # Should not raise an error
        await connection_manager.disconnect(mock_websocket, "nonexistent-user")

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_connection(self, connection_manager):
        """Test disconnecting a connection that doesn't exist for user"""
        user_id = "user-with-other-conn"
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws2 = AsyncMock()

        await connection_manager.connect(ws1, user_id)

        # Try to disconnect ws2 which was never connected
        await connection_manager.disconnect(ws2, user_id)

        # ws1 should still be connected
        assert ws1 in connection_manager.active_connections[user_id]


# ============================================================================
# Message Sending Tests
# ============================================================================


class TestMessageSending:
    """Tests for sending messages to WebSocket connections"""

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self, connection_manager, mock_websocket):
        """Test sending a personal message to a user"""
        user_id = "recipient-user"
        message = {"type": "notification", "data": {"text": "Hello"}}

        await connection_manager.connect(mock_websocket, user_id)
        await connection_manager.send_personal_message(message, user_id)

        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_multiple_connections(self, connection_manager):
        """Test sending message to all connections of a user"""
        user_id = "multi-conn-user"
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        message = {"type": "broadcast", "data": "to all"}

        await connection_manager.connect(ws1, user_id)
        await connection_manager.connect(ws2, user_id)
        await connection_manager.send_personal_message(message, user_id)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_nonexistent_user(self, connection_manager):
        """Test sending message to nonexistent user does nothing"""
        message = {"type": "test"}

        # Should not raise an error
        await connection_manager.send_personal_message(message, "nonexistent-user")

    @pytest.mark.asyncio
    async def test_send_personal_message_handles_failed_connection(self, connection_manager):
        """Test that failed connections are cleaned up during send"""
        user_id = "user-with-failing-conn"
        ws_good = AsyncMock()
        ws_good.accept = AsyncMock()
        ws_good.send_json = AsyncMock()

        ws_bad = AsyncMock()
        ws_bad.accept = AsyncMock()
        ws_bad.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        message = {"type": "test"}

        await connection_manager.connect(ws_good, user_id)
        await connection_manager.connect(ws_bad, user_id)

        with patch("app.routers.websocket.logger"):
            await connection_manager.send_personal_message(message, user_id)

        # Good connection should receive message
        ws_good.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_all_users(self, connection_manager):
        """Test broadcasting message to all connected users"""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        message = {"type": "system-event", "data": "maintenance"}

        await connection_manager.connect(ws1, "user-1")
        await connection_manager.connect(ws2, "user-2")
        await connection_manager.broadcast(message)

        ws1.send_json.assert_called_once_with(message)
        ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, connection_manager):
        """Test broadcast with no active connections"""
        message = {"type": "system-event"}

        # Should not raise an error
        await connection_manager.broadcast(message)


# ============================================================================
# JWT Token Validation Tests
# ============================================================================


class TestWebSocketJWTValidation:
    """Tests for JWT token validation in WebSocket connections"""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self, mock_settings, valid_jwt_token):
        """Test that valid token returns user ID"""
        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws(valid_jwt_token)

            assert user_id == "test-user-123"

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self, mock_settings, expired_jwt_token):
        """Test that expired token returns None"""
        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws(expired_jwt_token)

            assert user_id is None

    @pytest.mark.asyncio
    async def test_invalid_token_returns_none(self, mock_settings):
        """Test that invalid token returns None"""
        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws("invalid-token-format")

            assert user_id is None

    @pytest.mark.asyncio
    async def test_token_with_sub_claim(self, mock_settings):
        """Test token using 'sub' claim for user ID"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "sub": "user-from-sub",
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")

        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws(token)

            assert user_id == "user-from-sub"

    @pytest.mark.asyncio
    async def test_token_with_userId_claim(self, mock_settings):
        """Test token using 'userId' claim for user ID"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "userId": "user-from-userId",
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")

        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws(token)

            assert user_id == "user-from-userId"

    @pytest.mark.asyncio
    async def test_token_missing_user_identifier(self, mock_settings):
        """Test token without user identifier returns None"""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        payload = {
            "email": "test@example.com",  # No sub or userId
            "exp": int(exp.timestamp()),
        }
        token = jwt.encode(payload, mock_settings.jwt_secret_key, algorithm="HS256")

        with patch("app.routers.websocket.settings", mock_settings):
            from app.routers.websocket import get_current_user_ws

            user_id = await get_current_user_ws(token)

            assert user_id is None


# ============================================================================
# WebSocket Endpoint Tests
# ============================================================================


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint behavior"""

    @pytest.mark.asyncio
    async def test_websocket_rejects_invalid_token(self, mock_settings, mock_websocket):
        """Test that WebSocket endpoint rejects invalid token"""
        # SECURITY: Token now comes from header/subprotocol, not query param
        mock_websocket.headers = {"authorization": "Bearer invalid-token"}
        mock_websocket.subprotocols = []

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.get_current_user_ws", AsyncMock(return_value=None)),
            patch("app.routers.websocket.logger"),
        ):
            from app.routers.websocket import websocket_endpoint

            await websocket_endpoint(mock_websocket)

            mock_websocket.close.assert_called_once_with(code=4003, reason="Invalid token")

    @pytest.mark.asyncio
    async def test_websocket_connects_with_valid_token(
        self, mock_settings, mock_websocket, valid_jwt_token
    ):
        """Test WebSocket connects with valid token via Authorization header"""
        # SECURITY: Token now comes from header/subprotocol, not query param
        mock_websocket.headers = {"authorization": f"Bearer {valid_jwt_token}"}
        mock_websocket.subprotocols = []

        # Set up the mock to raise WebSocketDisconnect after accepting
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            from app.routers.websocket import websocket_endpoint

            await websocket_endpoint(mock_websocket)

            mock_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_connects_with_subprotocol_token(
        self, mock_settings, mock_websocket, valid_jwt_token
    ):
        """Test WebSocket connects with valid token via subprotocol"""
        # SECURITY: Test subprotocol fallback when header not available
        mock_websocket.headers = {}
        mock_websocket.subprotocols = [f"bearer.{valid_jwt_token}"]

        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = AsyncMock()

            from app.routers.websocket import websocket_endpoint

            await websocket_endpoint(mock_websocket)

            mock_manager.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_rejects_no_token(self, mock_settings, mock_websocket):
        """Test that WebSocket endpoint rejects connection without token"""
        # SECURITY: No token provided in header, subprotocol, or query param
        mock_websocket.headers = {}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.logger"),
        ):
            from app.routers.websocket import websocket_endpoint

            await websocket_endpoint(mock_websocket)

            mock_websocket.close.assert_called_once_with(
                code=4003, reason="Authentication required"
            )


# ============================================================================
# Redis Pub/Sub Listener Tests
# ============================================================================


class TestRedisListener:
    """Tests for Redis Pub/Sub listener"""

    @pytest.mark.asyncio
    async def test_redis_listener_disabled_without_url(self, mock_settings_no_redis):
        """Test that Redis listener is disabled without URL"""
        with (
            patch("app.routers.websocket.settings", mock_settings_no_redis),
            patch("app.routers.websocket.logger") as mock_logger,
        ):
            from app.routers.websocket import redis_listener

            await redis_listener()

            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_redis_listener_handles_user_notification(self, mock_settings):
        """Test Redis listener handles USER_NOTIFICATIONS channel"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()

        # Simulate a message coming through
        async def mock_listen():
            yield {
                "type": "pmessage",
                "channel": "CHANNELS.USER_NOTIFICATIONS:user-123",
                "data": json.dumps({"text": "New notification"}),
            }
            # Cancel after first message
            raise asyncio.CancelledError()

        mock_pubsub.listen = mock_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.redis.from_url", return_value=mock_redis),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.send_personal_message = AsyncMock()

            from app.routers.websocket import redis_listener

            await redis_listener()

            mock_manager.send_personal_message.assert_called_once()
            call_args = mock_manager.send_personal_message.call_args
            assert call_args[0][0]["type"] == "notification"
            assert call_args[0][1] == "user-123"

    @pytest.mark.asyncio
    async def test_redis_listener_handles_ai_results(self, mock_settings):
        """Test Redis listener handles AI_RESULTS channel"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            yield {
                "type": "pmessage",
                "channel": "CHANNELS.AI_RESULTS:user-456",
                "data": json.dumps({"response": "AI response"}),
            }
            raise asyncio.CancelledError()

        mock_pubsub.listen = mock_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.redis.from_url", return_value=mock_redis),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.send_personal_message = AsyncMock()

            from app.routers.websocket import redis_listener

            await redis_listener()

            call_args = mock_manager.send_personal_message.call_args
            assert call_args[0][0]["type"] == "ai-result"

    @pytest.mark.asyncio
    async def test_redis_listener_handles_system_events(self, mock_settings):
        """Test Redis listener handles SYSTEM_EVENTS channel with broadcast"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            yield {
                "type": "message",
                "channel": "CHANNELS.SYSTEM_EVENTS",
                "data": json.dumps({"event": "maintenance"}),
            }
            raise asyncio.CancelledError()

        mock_pubsub.listen = mock_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.redis.from_url", return_value=mock_redis),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.broadcast = AsyncMock()

            from app.routers.websocket import redis_listener

            await redis_listener()

            mock_manager.broadcast.assert_called_once()
            call_args = mock_manager.broadcast.call_args
            assert call_args[0][0]["type"] == "system-event"

    @pytest.mark.asyncio
    async def test_redis_listener_handles_invalid_json(self, mock_settings):
        """Test Redis listener handles invalid JSON gracefully"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            yield {
                "type": "pmessage",
                "channel": "CHANNELS.USER_NOTIFICATIONS:user-123",
                "data": "not valid json",  # Invalid JSON
            }
            raise asyncio.CancelledError()

        mock_pubsub.listen = mock_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.redis.from_url", return_value=mock_redis),
            patch("app.routers.websocket.manager") as mock_manager,
            patch("app.routers.websocket.logger"),
        ):
            mock_manager.send_personal_message = AsyncMock()

            from app.routers.websocket import redis_listener

            await redis_listener()

            # Should still send, but with raw_data wrapper
            call_args = mock_manager.send_personal_message.call_args
            assert "raw_data" in call_args[0][0]["data"]

    @pytest.mark.asyncio
    async def test_redis_listener_handles_connection_error(self, mock_settings):
        """Test Redis listener handles connection errors gracefully"""
        mock_redis = MagicMock()
        mock_pubsub = AsyncMock()

        async def mock_listen():
            raise Exception("Redis connection lost")

        mock_pubsub.listen = mock_listen
        mock_pubsub.psubscribe = AsyncMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis.close = AsyncMock()

        with (
            patch("app.routers.websocket.settings", mock_settings),
            patch("app.routers.websocket.redis.from_url", return_value=mock_redis),
            patch("app.routers.websocket.logger") as mock_logger,
        ):
            from app.routers.websocket import redis_listener

            await redis_listener()

            mock_logger.error.assert_called()
            mock_pubsub.close.assert_called()
            mock_redis.close.assert_called()


# ============================================================================
# Concurrency Tests
# ============================================================================


class TestConcurrency:
    """Tests for concurrent access to ConnectionManager"""

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, connection_manager):
        """Test multiple concurrent connections"""

        async def connect_user(user_id):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await connection_manager.connect(ws, user_id)
            return ws

        # Connect multiple users concurrently
        tasks = [connect_user(f"user-{i}") for i in range(10)]
        await asyncio.gather(*tasks)

        assert len(connection_manager.active_connections) == 10

    @pytest.mark.asyncio
    async def test_concurrent_disconnect(self, connection_manager):
        """Test concurrent disconnections"""
        websockets = []
        user_id = "shared-user"

        # Connect multiple WebSockets for same user
        for _ in range(5):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            await connection_manager.connect(ws, user_id)
            websockets.append(ws)

        # Disconnect concurrently
        tasks = [connection_manager.disconnect(ws, user_id) for ws in websockets]
        await asyncio.gather(*tasks)

        assert user_id not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_concurrent_send_messages(self, connection_manager):
        """Test sending messages concurrently"""
        websockets = []
        user_id = "multi-msg-user"

        # Connect multiple WebSockets
        for _ in range(3):
            ws = AsyncMock()
            ws.accept = AsyncMock()
            ws.send_json = AsyncMock()
            await connection_manager.connect(ws, user_id)
            websockets.append(ws)

        # Send multiple messages concurrently
        messages = [{"id": i} for i in range(5)]
        tasks = [connection_manager.send_personal_message(msg, user_id) for msg in messages]
        await asyncio.gather(*tasks)

        # Each WebSocket should receive all messages
        for ws in websockets:
            assert ws.send_json.call_count == 5
