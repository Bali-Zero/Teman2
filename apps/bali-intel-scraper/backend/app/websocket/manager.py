"""
WebSocket Connection Manager.

Manages client connections and message broadcasting.
"""

import time
from typing import Dict, List, Set
from fastapi import WebSocket
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="websocket")


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Connection tracking by client ID
    - Room-based subscriptions (e.g., 'articles', 'notifications')
    - Broadcast to all or specific rooms
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        # Active connections: client_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

        # Room subscriptions: room_name -> set of client_ids
        self.rooms: Dict[str, Set[str]] = {
            "articles": set(),
            "notifications": set(),
            "system": set(),
        }

        # Client metadata: client_id -> metadata dict
        self.client_metadata: Dict[str, dict] = {}

    async def connect(
        self, websocket: WebSocket, client_id: str, rooms: List[str] = None
    ) -> None:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            client_id: Unique identifier for the client
            rooms: List of rooms to subscribe to
        """
        await websocket.accept()

        self.active_connections[client_id] = websocket
        self.client_metadata[client_id] = {
            "rooms": rooms or ["notifications"],
            "connected_at": time.time(),
        }

        # Subscribe to rooms
        for room in rooms or ["notifications"]:
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(client_id)

        logger.info(
            "WebSocket client connected",
            action=LogAction.CONNECT,
            metadata={
                "client_id": client_id,
                "rooms": rooms,
                "total_connections": len(self.active_connections),
            },
        )

    async def disconnect(self, client_id: str) -> None:
        """
        Disconnect a client and clean up.

        Args:
            client_id: The client to disconnect
        """
        if client_id not in self.active_connections:
            return

        # Remove from all rooms
        for room_name, clients in self.rooms.items():
            clients.discard(client_id)

        # Remove connection
        del self.active_connections[client_id]
        if client_id in self.client_metadata:
            del self.client_metadata[client_id]

        logger.info(
            "WebSocket client disconnected",
            action=LogAction.DISCONNECT,
            metadata={
                "client_id": client_id,
                "total_connections": len(self.active_connections),
            },
        )

    async def send_message(self, client_id: str, message: dict) -> bool:
        """
        Send a message to a specific client.

        Args:
            client_id: Target client
            message: Message to send

        Returns:
            True if sent successfully, False otherwise
        """
        if client_id not in self.active_connections:
            return False

        try:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error(
                "Failed to send message to client",
                action=LogAction.ERROR,
                metadata={"client_id": client_id, "error": str(e)},
            )
            await self.disconnect(client_id)
            return False

    async def broadcast(
        self, message: dict, room: str = None, exclude: List[str] = None
    ) -> int:
        """
        Broadcast a message to all clients or a specific room.

        Args:
            message: Message to broadcast
            room: Room to broadcast to (None = all clients)
            exclude: List of client IDs to exclude

        Returns:
            Number of clients that received the message
        """
        exclude = exclude or []
        sent_count = 0

        # Get target clients
        if room:
            target_clients = self.rooms.get(room, set())
        else:
            target_clients = set(self.active_connections.keys())

        # Send to each client
        for client_id in target_clients:
            if client_id not in exclude:
                if await self.send_message(client_id, message):
                    sent_count += 1

        return sent_count

    async def broadcast_article_update(
        self,
        article_id: str,
        action: str,  # 'created', 'updated', 'deleted'
        article_data: dict = None,
    ) -> int:
        """
        Broadcast an article update to subscribers.

        Args:
            article_id: The article ID
            action: The action performed
            article_data: Optional article data

        Returns:
            Number of clients notified
        """
        message = {
            "type": "article_update",
            "data": {
                "id": article_id,
                "action": action,
                "article": article_data,
            },
            "timestamp": time.time(),
        }

        return await self.broadcast(message, room="articles")

    async def broadcast_notification(
        self,
        title: str,
        message: str,
        level: str = "info",  # 'info', 'warning', 'error', 'success'
        data: dict = None,
    ) -> int:
        """
        Broadcast a notification to all clients.

        Args:
            title: Notification title
            message: Notification message
            level: Notification level
            data: Additional data

        Returns:
            Number of clients notified
        """
        notification = {
            "type": "notification",
            "data": {
                "title": title,
                "message": message,
                "level": level,
                "data": data,
            },
            "timestamp": time.time(),
        }

        return await self.broadcast(notification, room="notifications")

    def get_stats(self) -> dict:
        """Get current WebSocket statistics."""
        return {
            "total_connections": len(self.active_connections),
            "rooms": {name: len(clients) for name, clients in self.rooms.items()},
        }


# Global instance
_websocket_manager: WebSocketManager = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
