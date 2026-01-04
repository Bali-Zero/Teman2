"""
Unit tests for websocket router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.websocket import ConnectionManager, get_current_user_ws


class TestConnectionManager:
    """Tests for ConnectionManager"""

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting a websocket"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        assert "user123" in manager.active_connections
        assert mock_websocket in manager.active_connections["user123"]
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple(self):
        """Test connecting multiple websockets for same user"""
        manager = ConnectionManager()
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()

        await manager.connect(mock_ws1, "user123")
        await manager.connect(mock_ws2, "user123")
        assert len(manager.active_connections["user123"]) == 2

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting a websocket"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.disconnect(mock_websocket, "user123")
        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_last_connection(self):
        """Test disconnecting last connection removes user"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.disconnect(mock_websocket, "user123")
        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        """Test sending personal message"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock()

        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message({"type": "test"}, "user123")
        mock_websocket.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_send_personal_message_failed(self):
        """Test sending message to dead connection"""
        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        await manager.connect(mock_websocket, "user123")
        await manager.send_personal_message({"type": "test"}, "user123")
        # Should disconnect dead connection
        assert "user123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting to all users"""
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
    async def test_send_personal_message_no_user(self):
        """Test sending message to non-existent user"""
        manager = ConnectionManager()
        # Should not raise error
        await manager.send_personal_message({"type": "test"}, "nonexistent")


class TestWebSocketAuth:
    """Tests for WebSocket authentication"""

    @pytest.mark.asyncio
    @patch("app.routers.websocket.settings")
    @patch("app.routers.websocket.jwt")
    async def test_get_current_user_ws_valid(self, mock_jwt, mock_settings):
        """Test getting current user with valid token"""
        mock_settings.jwt_secret_key = "secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_jwt.decode.return_value = {"sub": "user123"}

        user_id = await get_current_user_ws("valid_token")
        assert user_id == "user123"

    @pytest.mark.asyncio
    @patch("app.routers.websocket.settings")
    @patch("app.routers.websocket.jwt")
    async def test_get_current_user_ws_userid(self, mock_jwt, mock_settings):
        """Test getting current user with userId in payload"""
        mock_settings.jwt_secret_key = "secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_jwt.decode.return_value = {"userId": "user456"}

        user_id = await get_current_user_ws("valid_token")
        assert user_id == "user456"

    @pytest.mark.asyncio
    @patch("app.routers.websocket.settings")
    @patch("app.routers.websocket.jwt")
    async def test_get_current_user_ws_invalid(self, mock_jwt, mock_settings):
        """Test getting current user with invalid token"""
        from jose import JWTError

        mock_settings.jwt_secret_key = "secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_jwt.decode.side_effect = JWTError("Invalid token")

        user_id = await get_current_user_ws("invalid_token")
        assert user_id is None

    @pytest.mark.asyncio
    @patch("app.routers.websocket.settings")
    @patch("app.routers.websocket.jwt")
    async def test_get_current_user_ws_no_user_id(self, mock_jwt, mock_settings):
        """Test getting current user with no user ID in payload"""
        mock_settings.jwt_secret_key = "secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_jwt.decode.return_value = {}

        user_id = await get_current_user_ws("token")
        assert user_id is None
