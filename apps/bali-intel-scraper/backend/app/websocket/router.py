"""
WebSocket API Routes.

Defines WebSocket endpoints for real-time communication.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import List, Optional

from .manager import get_websocket_manager
from .handlers import handle_client_connect, handle_client_disconnect, handle_message

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
    rooms: Optional[List[str]] = Query(None, description="Rooms to subscribe to"),
):
    """
    Main WebSocket endpoint for real-time updates.

    Query Parameters:
        client_id: Unique identifier for the client
        rooms: Comma-separated list of rooms to subscribe to
               (default: notifications)

    Rooms Available:
        - articles: Article updates (new, edited, deleted)
        - notifications: System notifications
        - system: System status updates

    Message Format (Client -> Server):
        {
            "type": "subscribe|unsubscribe|ping|get_stats",
            "data": {...}
        }

    Message Format (Server -> Client):
        {
            "type": "article_update|notification|connected|stats|error",
            "data": {...},
            "timestamp": 1234567890
        }
    """
    manager = get_websocket_manager()
    rooms_list = rooms or ["notifications"]

    # Accept connection
    await manager.connect(websocket, client_id, rooms_list)

    # Send welcome message
    await handle_client_connect(client_id, websocket)

    try:
        # Message loop
        while True:
            # Receive message from client
            message = await websocket.receive_json()

            # Handle the message
            await handle_message(client_id, message)

    except WebSocketDisconnect:
        await handle_client_disconnect(client_id)


@router.websocket("/articles")
async def websocket_articles(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
):
    """
    Dedicated WebSocket endpoint for article updates only.

    This is a convenience endpoint that automatically subscribes
    to the 'articles' room.

    Query Parameters:
        client_id: Unique identifier for the client
    """
    manager = get_websocket_manager()

    await manager.connect(websocket, client_id, rooms=["articles"])
    await handle_client_connect(client_id, websocket)

    try:
        while True:
            message = await websocket.receive_json()
            await handle_message(client_id, message)
    except WebSocketDisconnect:
        await handle_client_disconnect(client_id)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
):
    """
    Dedicated WebSocket endpoint for notifications only.

    This is a convenience endpoint that automatically subscribes
    to the 'notifications' room.

    Query Parameters:
        client_id: Unique identifier for the client
    """
    manager = get_websocket_manager()

    await manager.connect(websocket, client_id, rooms=["notifications"])
    await handle_client_connect(client_id, websocket)

    try:
        while True:
            message = await websocket.receive_json()
            await handle_message(client_id, message)
    except WebSocketDisconnect:
        await handle_client_disconnect(client_id)
