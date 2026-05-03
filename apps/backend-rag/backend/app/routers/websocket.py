"""
WebSocket Router & Connection Manager
Handles real-time notifications via Redis Pub/Sub
Replaces Node.js websocket.ts
"""

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """
    Manages active WebSocket connections.
    """

    def __init__(self) -> None:
        # Map user_id -> List[WebSocket]
        self.active_connections: dict[str, list[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, user_id: str, subprotocol: str | None = None,
    ) -> None:
        await websocket.accept(subprotocol=subprotocol)
        async with self.lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            logger.info(
                f"🔌 WebSocket connected: {user_id} (Total: {len(self.active_connections[user_id])})",
            )

    async def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        async with self.lock:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"🔌 WebSocket disconnected: {user_id}")

    async def send_personal_message(self, message: dict, user_id: str) -> None:
        """Send message to all connections of a specific user"""
        if user_id in self.active_connections:
            # Create a copy of the list to avoid modification during iteration issues
            connections = self.active_connections[user_id][:]
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to send WS message to {user_id}: {e}")
                    # Cleanup dead connection
                    await self.disconnect(connection, user_id)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to ALL connected users"""
        # Iterate over a copy of keys
        user_ids = list(self.active_connections.keys())
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)


manager = ConnectionManager()


async def get_current_user_ws(token: str) -> str | None:
    """
    Validate JWT token

    SECURITY: Token is now passed directly (from header/subprotocol) instead of query param
    """
    try:
        # S03: Two-phase JWT expiry enforcement
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm],
            options={"verify_exp": getattr(settings, "jwt_enforce_expiry", False)},
        )
        user_id: str = payload.get("sub") or payload.get("userId")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> Any:
    """
    WebSocket endpoint for real-time updates.

    SECURITY: Token is extracted from Authorization header or subprotocol instead of URL query param
    to prevent token exposure in logs and browser history.

    Client should connect with:
    - Authorization header: "Bearer <token>", OR
    - Subprotocol: "bearer.<token>"
    """
    # Try to get token from Authorization header first (most secure)
    token = None
    auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Remove "Bearer " prefix

    # Fallback to subprotocol if header not available (WebSocket limitation)
    # Use scope.get() as subprotocols attribute may not exist in all Starlette versions
    subprotocols = websocket.scope.get("subprotocols", [])
    if not token and subprotocols:
        for subprotocol in subprotocols:
            if subprotocol.startswith("bearer."):
                token = subprotocol[7:]  # Remove "bearer." prefix
                break

    # Last resort: check query param (deprecated, kept for backward compatibility)
    if not token:
        from urllib.parse import parse_qs

        query_string = websocket.url.query
        if query_string:
            params = parse_qs(query_string)
            token = params.get("token", [None])[0]

    if not token:
        logger.debug("⚠️ WebSocket connection rejected: No token provided")
        await websocket.close(code=4003, reason="Authentication required")
        return

    user_id = await get_current_user_ws(token)

    if not user_id:
        logger.debug("⚠️ WebSocket connection rejected: Invalid token")
        await websocket.close(code=4003, reason="Invalid token")  # Forbidden
        return

    # Echo the subprotocol back to satisfy browser requirement
    # (browser rejects connection if Sec-WebSocket-Protocol was sent but not echoed)
    selected_subprotocol: str | None = None
    if subprotocols:
        for sp in subprotocols:
            if sp.startswith("bearer."):
                selected_subprotocol = sp
                break

    await manager.connect(websocket, user_id, subprotocol=selected_subprotocol)

    # Create a background task to send pings to keep the connection alive
    heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

    try:
        while True:
            # Keep connection alive and handle client messages
            # usage of asyncio.wait_for prevents indefinite blocking if we need to react to other events
            try:
                message_text = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle ping/pong for keepalive
                try:
                    message = json.loads(message_text)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    # Other message types can be handled here if needed
                except json.JSONDecodeError:
                    pass  # non-JSON message — ignore (e.g. raw binary ping frames)
            except asyncio.TimeoutError:
                # No data received for 30s, loop around (heartbeat triggers separately)
                continue

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket client disconnected: {user_id}")
        await manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"❌ WebSocket error for {user_id}: {e}", exc_info=True)
        await manager.disconnect(websocket, user_id)
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


async def send_heartbeat(websocket: WebSocket, interval: int = 15) -> None:
    """Send periodic pings to keep connection alive through proxies"""
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await websocket.send_json({"type": "ping", "source": "server_keepalive"})
            except Exception:
                break
    except asyncio.CancelledError:
        pass  # heartbeat task cancelled on disconnect — expected


# ============================================================================
# Redis Pub/Sub Listener
# ============================================================================


async def redis_listener() -> Any:
    """
    Background task to listen for Redis Pub/Sub events and forward to WebSockets
    """
    from backend.core.redis_manager import RedisManager

    redis_mgr = RedisManager.get_instance()
    client = redis_mgr.get_async_client()
    if client is None:
        logger.warning("Redis not available via RedisManager. WebSocket notifications disabled.")
        redis_mgr.register_component("websocket_pubsub", "disabled")
        return

    redis_mgr.register_component("websocket_pubsub", "active")
    redis_client = client
    pubsub = redis_client.pubsub()

    # Subscribe to channels
    # Patterns:
    # CHANNELS.USER_NOTIFICATIONS:* -> user specific
    # CHANNELS.AI_RESULTS:* -> user specific (usually)
    # CHANNELS.CHAT_MESSAGES:* -> room/user specific
    # CHANNELS.SYSTEM_EVENTS -> broadcast

    # We subscribe to patterns to catch all
    await pubsub.psubscribe("CHANNELS.USER_NOTIFICATIONS:*")
    await pubsub.psubscribe("CHANNELS.AI_RESULTS:*")
    await pubsub.psubscribe("CHANNELS.CHAT_MESSAGES:*")
    await pubsub.subscribe("CHANNELS.SYSTEM_EVENTS")

    logger.info("✅ Redis Pub/Sub listener started")

    try:
        async for message in pubsub.listen():
            if message["type"] in ["message", "pmessage"]:
                channel = message["channel"]
                data_str = message["data"]

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = {"raw_data": data_str}

                # Determine target user from channel name
                # Format: CHANNELS.USER_NOTIFICATIONS:{userId}

                if "USER_NOTIFICATIONS" in channel:
                    # Extract userId
                    parts = channel.split(":")
                    if len(parts) > 1:
                        target_user_id = parts[-1]
                        await manager.send_personal_message(
                            {"type": "notification", "data": data}, target_user_id,
                        )

                elif "AI_RESULTS" in channel:
                    parts = channel.split(":")
                    if len(parts) > 1:
                        target_user_id = parts[-1]
                        await manager.send_personal_message(
                            {"type": "ai-result", "data": data}, target_user_id,
                        )

                elif "CHAT_MESSAGES" in channel:
                    # Chat messages might be for a room or user.
                    # For now, assuming direct mapping or we broadcast to room members.
                    # Simplified: If channel has userId, send to user.
                    parts = channel.split(":")
                    if len(parts) > 1:
                        target_id = parts[-1]
                        # Try sending to user (if target is user)
                        await manager.send_personal_message(
                            {"type": "chat-message", "data": data}, target_id,
                        )
                        # Room management logic can be added when needed

                elif "SYSTEM_EVENTS" in channel:
                    await manager.broadcast({"type": "system-event", "data": data})

    except asyncio.CancelledError:
        logger.info("🛑 Redis listener cancelled")
    except Exception as e:
        logger.error(f"❌ Redis listener error: {e}")
    finally:
        await pubsub.close()
        # Don't close redis_client — it's shared via RedisManager
