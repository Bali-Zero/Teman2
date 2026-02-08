"""
WebSocket module for real-time updates.

Provides:
- Live article updates
- Real-time notifications
- Connection management
- Broadcast to multiple clients
"""

from .manager import WebSocketManager, get_websocket_manager
from .handlers import (
    handle_article_update,
    handle_notification,
    handle_client_connect,
    handle_client_disconnect,
)

__all__ = [
    "WebSocketManager",
    "get_websocket_manager",
    "handle_article_update",
    "handle_notification",
    "handle_client_connect",
    "handle_client_disconnect",
]
