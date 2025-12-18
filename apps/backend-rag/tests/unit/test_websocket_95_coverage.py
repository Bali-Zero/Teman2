"""
Comprehensive Tests for WebSocket Router - Target 95% Coverage
Tests ConnectionManager, authentication, Redis pub/sub, and all edge cases
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

# ============================================================================
# CONNECTION MANAGER TESTS
# ============================================================================


class TestConnectionManager:
    """Test ConnectionManager class"""

    @pytest.fixture
    def manager(self):
        """Create fresh ConnectionManager for each test"""
        from backend.app.routers.websocket import ConnectionManager

        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_new_user(self, manager):
        """Test connecting new user"""
        mock_websocket = AsyncMock(spec=WebSocket)

        await manager.connect(mock_websocket, "user1")

        mock_websocket.accept.assert_called_once()
        assert "user1" in manager.active_connections
        assert mock_websocket in manager.active_connections["user1"]

    @pytest.mark.asyncio
    async def test_connect_existing_user_multiple_connections(self, manager):
        """Test connecting existing user with multiple connections"""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user1")

        assert len(manager.active_connections["user1"]) == 2
        assert mock_ws1 in manager.active_connections["user1"]
        assert mock_ws2 in manager.active_connections["user1"]

    @pytest.mark.asyncio
    async def test_disconnect_single_connection(self, manager):
        """Test disconnecting single connection"""
        mock_websocket = AsyncMock(spec=WebSocket)
        await manager.connect(mock_websocket, "user1")

        await manager.disconnect(mock_websocket, "user1")

        assert "user1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_one_of_multiple(self, manager):
        """Test disconnecting one of multiple connections"""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user1")

        await manager.disconnect(mock_ws1, "user1")

        assert "user1" in manager.active_connections
        assert len(manager.active_connections["user1"]) == 1
        assert mock_ws2 in manager.active_connections["user1"]

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_user(self, manager):
        """Test disconnecting nonexistent user doesn't error"""
        mock_websocket = AsyncMock(spec=WebSocket)

        # Should not raise
        await manager.disconnect(mock_websocket, "nonexistent")

    @pytest.mark.asyncio
    async def test_disconnect_wrong_websocket(self, manager):
        """Test disconnecting wrong websocket from user"""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user1")

        # Disconnect a websocket that wasn't connected
        await manager.disconnect(mock_ws2, "user1")

        # Original should still be there
        assert mock_ws1 in manager.active_connections["user1"]

    @pytest.mark.asyncio
    async def test_send_personal_message_success(self, manager):
        """Test sending personal message successfully"""
        mock_websocket = AsyncMock(spec=WebSocket)
        await manager.connect(mock_websocket, "user1")

        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, "user1")

        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_to_nonexistent_user(self, manager):
        """Test sending message to nonexistent user does nothing"""
        message = {"type": "test", "data": "hello"}

        # Should not raise
        await manager.send_personal_message(message, "nonexistent")

    @pytest.mark.asyncio
    async def test_send_personal_message_multiple_connections(self, manager):
        """Test sending message to user with multiple connections"""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user1")

        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, "user1")

        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_personal_message_handles_error(self, manager):
        """Test sending message handles errors and disconnects dead connection"""
        mock_ws_good = AsyncMock(spec=WebSocket)
        mock_ws_bad = AsyncMock(spec=WebSocket)
        mock_ws_bad.send_json.side_effect = Exception("Connection closed")

        await manager.connect(mock_ws_good, "user1")
        await manager.connect(mock_ws_bad, "user1")

        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, "user1")

        # Good connection should receive message
        mock_ws_good.send_json.assert_called()
        # Bad connection should be removed
        assert mock_ws_bad not in manager.active_connections.get("user1", [])

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """Test broadcasting to all users"""
        mock_ws1 = AsyncMock(spec=WebSocket)
        mock_ws2 = AsyncMock(spec=WebSocket)
        mock_ws3 = AsyncMock(spec=WebSocket)

        await manager.connect(mock_ws1, "user1")
        await manager.connect(mock_ws2, "user2")
        await manager.connect(mock_ws3, "user2")

        message = {"type": "broadcast", "data": "hello all"}
        await manager.broadcast(message)

        mock_ws1.send_json.assert_called_with(message)
        mock_ws2.send_json.assert_called_with(message)
        mock_ws3.send_json.assert_called_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self, manager):
        """Test broadcasting with no connections"""
        message = {"type": "broadcast", "data": "hello"}

        # Should not raise
        await manager.broadcast(message)


# ============================================================================
# JWT AUTHENTICATION TESTS
# ============================================================================


class TestGetCurrentUserWs:
    """Test get_current_user_ws function"""

    @pytest.mark.asyncio
    async def test_valid_token(self):
        """Test valid JWT token returns user_id"""
        from backend.app.routers.websocket import get_current_user_ws

        with patch("backend.app.routers.websocket.jwt") as mock_jwt:
            mock_jwt.decode.return_value = {"sub": "user123"}

            result = await get_current_user_ws("valid_token")

            assert result == "user123"

    @pytest.mark.asyncio
    async def test_valid_token_with_userId(self):
        """Test valid JWT token with userId field"""
        from backend.app.routers.websocket import get_current_user_ws

        with patch("backend.app.routers.websocket.jwt") as mock_jwt:
            mock_jwt.decode.return_value = {"userId": "user456"}

            result = await get_current_user_ws("valid_token")

            assert result == "user456"

    @pytest.mark.asyncio
    async def test_token_missing_user_id(self):
        """Test token with no user identifier returns None"""
        from backend.app.routers.websocket import get_current_user_ws

        with patch("backend.app.routers.websocket.jwt") as mock_jwt:
            mock_jwt.decode.return_value = {"other": "data"}

            result = await get_current_user_ws("token_no_user")

            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test invalid token returns None"""
        from jose import JWTError

        from backend.app.routers.websocket import get_current_user_ws

        with patch("backend.app.routers.websocket.jwt") as mock_jwt:
            mock_jwt.decode.side_effect = JWTError("Invalid token")

            result = await get_current_user_ws("invalid_token")

            assert result is None


# ============================================================================
# WEBSOCKET ENDPOINT TESTS
# ============================================================================


class TestWebsocketEndpoint:
    """Test websocket_endpoint"""

    @pytest.mark.asyncio
    async def test_connect_with_auth_header(self):
        """Test WebSocket connection with Authorization header"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"Authorization": "Bearer valid_token"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user123"

            await websocket_endpoint(mock_websocket)

            mock_auth.assert_called_once_with("valid_token")

    @pytest.mark.asyncio
    async def test_connect_with_subprotocol(self):
        """Test WebSocket connection with bearer subprotocol"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = ["bearer.subprotocol_token"]
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user456"

            await websocket_endpoint(mock_websocket)

            mock_auth.assert_called_once_with("subprotocol_token")

    @pytest.mark.asyncio
    async def test_connect_with_query_param(self):
        """Test WebSocket connection with query parameter (deprecated)"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = "token=query_token"
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user789"

            await websocket_endpoint(mock_websocket)

            mock_auth.assert_called_once_with("query_token")

    @pytest.mark.asyncio
    async def test_connect_no_token(self):
        """Test WebSocket connection rejected without token"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        await websocket_endpoint(mock_websocket)

        mock_websocket.close.assert_called_once_with(code=4003, reason="Authentication required")

    @pytest.mark.asyncio
    async def test_connect_invalid_token(self):
        """Test WebSocket connection rejected with invalid token"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"Authorization": "Bearer invalid"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = None

            await websocket_endpoint(mock_websocket)

            mock_websocket.close.assert_called_once_with(code=4003, reason="Invalid token")

    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Test ping/pong keepalive"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"Authorization": "Bearer valid_token"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        # Simulate ping then disconnect
        mock_websocket.receive_text = AsyncMock(
            side_effect=[json.dumps({"type": "ping"}), WebSocketDisconnect()]
        )

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user123"

            await websocket_endpoint(mock_websocket)

            mock_websocket.send_json.assert_called_with({"type": "pong"})

    @pytest.mark.asyncio
    async def test_non_json_message(self):
        """Test handling non-JSON messages"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"Authorization": "Bearer valid_token"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""

        # Non-JSON then disconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["not json {{{", WebSocketDisconnect()])

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user123"

            # Should not raise
            await websocket_endpoint(mock_websocket)

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        """Test handling unexpected errors"""
        from backend.app.routers.websocket import websocket_endpoint

        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.headers = {"Authorization": "Bearer valid_token"}
        mock_websocket.subprotocols = []
        mock_websocket.url.query = ""
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("Unexpected error"))

        with patch("backend.app.routers.websocket.get_current_user_ws") as mock_auth:
            mock_auth.return_value = "user123"

            # Should not raise, should disconnect gracefully
            await websocket_endpoint(mock_websocket)


# ============================================================================
# REDIS LISTENER TESTS
# ============================================================================


class TestRedisListener:
    """Test redis_listener function"""

    @pytest.mark.asyncio
    async def test_redis_listener_no_url(self):
        """Test redis listener returns early without URL"""
        from backend.app.routers.websocket import redis_listener

        with patch("backend.app.routers.websocket.settings") as mock_settings:
            mock_settings.redis_url = None

            # Should return immediately
            await redis_listener()

    @pytest.mark.asyncio
    async def test_redis_listener_user_notification(self):
        """Test redis listener handles user notifications"""
        from backend.app.routers.websocket import manager, redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
            patch.object(manager, "send_personal_message") as mock_send,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                yield {
                    "type": "pmessage",
                    "channel": "CHANNELS.USER_NOTIFICATIONS:user123",
                    "data": json.dumps({"message": "Hello"}),
                }
                raise asyncio.CancelledError()

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()
            mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_redis_listener_ai_results(self):
        """Test redis listener handles AI results"""
        from backend.app.routers.websocket import manager, redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
            patch.object(manager, "send_personal_message") as mock_send,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                yield {
                    "type": "pmessage",
                    "channel": "CHANNELS.AI_RESULTS:user456",
                    "data": json.dumps({"result": "AI response"}),
                }
                raise asyncio.CancelledError()

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()
            mock_send.assert_called()
            call_args = mock_send.call_args_list[-1]
            assert call_args[0][0]["type"] == "ai-result"

    @pytest.mark.asyncio
    async def test_redis_listener_chat_messages(self):
        """Test redis listener handles chat messages"""
        from backend.app.routers.websocket import manager, redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
            patch.object(manager, "send_personal_message") as mock_send,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                yield {
                    "type": "pmessage",
                    "channel": "CHANNELS.CHAT_MESSAGES:room123",
                    "data": json.dumps({"from": "user1", "text": "Hello"}),
                }
                raise asyncio.CancelledError()

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()
            mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_redis_listener_system_events(self):
        """Test redis listener handles system events (broadcast)"""
        from backend.app.routers.websocket import manager, redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
            patch.object(manager, "broadcast") as mock_broadcast,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                yield {
                    "type": "message",
                    "channel": "CHANNELS.SYSTEM_EVENTS",
                    "data": json.dumps({"event": "maintenance"}),
                }
                raise asyncio.CancelledError()

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()
            mock_broadcast.assert_called()
            call_args = mock_broadcast.call_args[0][0]
            assert call_args["type"] == "system-event"

    @pytest.mark.asyncio
    async def test_redis_listener_invalid_json(self):
        """Test redis listener handles invalid JSON data"""
        from backend.app.routers.websocket import manager, redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
            patch.object(manager, "send_personal_message") as mock_send,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                yield {
                    "type": "pmessage",
                    "channel": "CHANNELS.USER_NOTIFICATIONS:user123",
                    "data": "not valid json {{{",
                }
                raise asyncio.CancelledError()

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()
            mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_redis_listener_unexpected_error(self):
        """Test redis listener handles unexpected errors"""
        from backend.app.routers.websocket import redis_listener
        from tests.conftest import create_mock_redis_pubsub

        with (
            patch("backend.app.routers.websocket.settings") as mock_settings,
            patch("backend.app.routers.websocket.redis") as mock_redis,
        ):
            mock_settings.redis_url = "redis://localhost:6379"
            mock_client, mock_pubsub = create_mock_redis_pubsub()

            async def mock_listen():
                raise Exception("Redis error")

            mock_pubsub.listen.return_value = mock_listen()
            mock_redis.from_url.return_value = mock_client

            await redis_listener()


# ============================================================================
# ROUTER CONFIGURATION TESTS
# ============================================================================


class TestRouterConfiguration:
    """Test router configuration"""

    def test_router_exists(self):
        """Test router is properly configured"""
        from backend.app.routers.websocket import router

        assert router is not None

    def test_router_has_websocket_endpoint(self):
        """Test router has websocket endpoint"""
        from backend.app.routers.websocket import router

        routes = [r.path for r in router.routes]
        assert "/ws" in routes or any("/ws" in str(r) for r in routes)

    def test_router_tags(self):
        """Test router has correct tags"""
        from backend.app.routers.websocket import router

        assert "websocket" in router.tags


# ============================================================================
# MANAGER SINGLETON TESTS
# ============================================================================


class TestManagerSingleton:
    """Test manager singleton instance"""

    def test_manager_is_singleton(self):
        """Test manager is a singleton instance"""
        from backend.app.routers.websocket import manager

        assert manager is not None
        assert hasattr(manager, "active_connections")
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")
        assert hasattr(manager, "send_personal_message")
        assert hasattr(manager, "broadcast")

    def test_manager_initial_state(self):
        """Test manager has correct initial state"""
        from backend.app.routers.websocket import ConnectionManager

        fresh_manager = ConnectionManager()
        assert fresh_manager.active_connections == {}
        assert fresh_manager.lock is not None
