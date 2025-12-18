"""
Integration tests for WebSocket Service
Tests WebSocket connection management integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["REDIS_URL"] = "redis://localhost:6379"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestWebSocketServiceIntegration:
    """Integration tests for WebSocket Service"""

    @pytest.mark.asyncio
    async def test_websocket_manager_operations(self):
        """Test WebSocket manager operations"""
        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        assert manager is not None
        assert hasattr(manager, "active_connections")
        assert hasattr(manager, "connect")
        assert hasattr(manager, "disconnect")

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test WebSocket connection lifecycle"""
        from unittest.mock import MagicMock

        from app.routers.websocket import ConnectionManager

        manager = ConnectionManager()
        mock_websocket = MagicMock()
        mock_websocket.accept = AsyncMock()

        # Connect
        await manager.connect(mock_websocket, "user123")
        assert "user123" in manager.active_connections

        # Disconnect
        await manager.disconnect(mock_websocket, "user123")
        assert (
            "user123" not in manager.active_connections
            or len(manager.active_connections.get("user123", [])) == 0
        )
