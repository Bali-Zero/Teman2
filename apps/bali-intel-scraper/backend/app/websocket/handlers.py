"""
WebSocket message handlers.

Handles different types of WebSocket messages and events.
"""

from typing import Dict, Any
from fastapi import WebSocket
from backend.core.logger import get_logger, LogAction
from .manager import get_websocket_manager

logger = get_logger(__name__, component="websocket")


async def handle_client_connect(client_id: str, websocket: WebSocket) -> None:
    """
    Handle new client connection.

    Args:
        client_id: The client ID
        websocket: The WebSocket connection
    """
    manager = get_websocket_manager()

    # Send welcome message
    await manager.send_message(
        client_id,
        {
            "type": "connected",
            "data": {
                "client_id": client_id,
                "message": "Connected to Nuzantara real-time updates",
            },
        },
    )

    logger.info(
        "Client handshake completed",
        action=LogAction.CONNECT,
        metadata={"client_id": client_id},
    )


async def handle_client_disconnect(client_id: str) -> None:
    """
    Handle client disconnection.

    Args:
        client_id: The client ID
    """
    manager = get_websocket_manager()
    await manager.disconnect(client_id)


async def handle_message(client_id: str, message: Dict[str, Any]) -> None:
    """
    Handle incoming WebSocket message from client.

    Args:
        client_id: The client ID
        message: The message data
    """
    msg_type = message.get("type")

    handlers = {
        "subscribe": handle_subscribe,
        "unsubscribe": handle_unsubscribe,
        "ping": handle_ping,
        "get_stats": handle_get_stats,
    }

    handler = handlers.get(msg_type)
    if handler:
        await handler(client_id, message.get("data", {}))
    else:
        await handle_unknown_message(client_id, message)


async def handle_subscribe(client_id: str, data: Dict[str, Any]) -> None:
    """
    Handle room subscription request.

    Args:
        client_id: The client ID
        data: Subscription data including 'rooms' list
    """
    manager = get_websocket_manager()
    rooms = data.get("rooms", [])

    for room in rooms:
        if room not in manager.rooms:
            manager.rooms[room] = set()
        manager.rooms[room].add(client_id)

    await manager.send_message(
        client_id, {"type": "subscribed", "data": {"rooms": rooms}}
    )

    logger.info(
        "Client subscribed to rooms",
        action=LogAction.UPDATE,
        metadata={"client_id": client_id, "rooms": rooms},
    )


async def handle_unsubscribe(client_id: str, data: Dict[str, Any]) -> None:
    """
    Handle room unsubscription request.

    Args:
        client_id: The client ID
        data: Unsubscription data including 'rooms' list
    """
    manager = get_websocket_manager()
    rooms = data.get("rooms", [])

    for room in rooms:
        if room in manager.rooms:
            manager.rooms[room].discard(client_id)

    await manager.send_message(
        client_id, {"type": "unsubscribed", "data": {"rooms": rooms}}
    )


async def handle_ping(client_id: str, data: Dict[str, Any]) -> None:
    """
    Handle ping message (keep-alive).

    Args:
        client_id: The client ID
        data: Ping data
    """
    manager = get_websocket_manager()
    await manager.send_message(
        client_id, {"type": "pong", "data": {"timestamp": data.get("timestamp")}}
    )


async def handle_get_stats(client_id: str, data: Dict[str, Any]) -> None:
    """
    Handle stats request.

    Args:
        client_id: The client ID
        data: Request data
    """
    manager = get_websocket_manager()
    stats = manager.get_stats()

    await manager.send_message(client_id, {"type": "stats", "data": stats})


async def handle_unknown_message(client_id: str, message: Dict[str, Any]) -> None:
    """
    Handle unknown message type.

    Args:
        client_id: The client ID
        message: The unknown message
    """
    manager = get_websocket_manager()

    await manager.send_message(
        client_id,
        {
            "type": "error",
            "data": {
                "message": f"Unknown message type: {message.get('type')}",
                "supported_types": ["subscribe", "unsubscribe", "ping", "get_stats"],
            },
        },
    )


async def handle_article_update(
    article_id: str, action: str, article_data: Dict[str, Any] = None
) -> int:
    """
    Broadcast article update to all subscribers.

    Args:
        article_id: The article ID
        action: The action performed
        article_data: Optional article data

    Returns:
        Number of clients notified
    """
    manager = get_websocket_manager()
    return await manager.broadcast_article_update(article_id, action, article_data)


async def handle_notification(
    title: str, message: str, level: str = "info", data: Dict[str, Any] = None
) -> int:
    """
    Broadcast notification to all clients.

    Args:
        title: Notification title
        message: Notification message
        level: Notification level
        data: Additional data

    Returns:
        Number of clients notified
    """
    manager = get_websocket_manager()
    return await manager.broadcast_notification(title, message, level, data)
