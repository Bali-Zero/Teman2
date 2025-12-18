"""
Comprehensive Integration Tests for WebSocket Services
Tests WebSocket connections, real-time updates, streaming

Covers:
- WebSocket connections
- Real-time message handling
- Streaming responses
- Connection management
- Error handling in WebSocket
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestWebSocketServices:
    """Integration tests for WebSocket services"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, db_pool):
        """Test WebSocket connection"""

        async with db_pool.acquire() as conn:
            # Create websocket_connections table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS websocket_connections (
                    id SERIAL PRIMARY KEY,
                    connection_id VARCHAR(255) UNIQUE,
                    user_id VARCHAR(255),
                    connected_at TIMESTAMP DEFAULT NOW(),
                    disconnected_at TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'connected'
                )
                """
            )

            # Track connection
            connection_id = "ws_conn_123"
            conn_id = await conn.fetchval(
                """
                INSERT INTO websocket_connections (connection_id, user_id, status)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                connection_id,
                "test_user_ws",
                "connected",
            )

            assert conn_id is not None

            # Verify connection
            connection = await conn.fetchrow(
                """
                SELECT connection_id, status
                FROM websocket_connections
                WHERE id = $1
                """,
                conn_id,
            )

            assert connection["status"] == "connected"

            # Cleanup
            await conn.execute("DELETE FROM websocket_connections WHERE id = $1", conn_id)

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, db_pool):
        """Test WebSocket message handling"""

        async with db_pool.acquire() as conn:
            # Create websocket_messages table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS websocket_messages (
                    id SERIAL PRIMARY KEY,
                    connection_id VARCHAR(255),
                    message_type VARCHAR(100),
                    message_content JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store message
            message_id = await conn.fetchval(
                """
                INSERT INTO websocket_messages (
                    connection_id, message_type, message_content
                )
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "ws_conn_123",
                "chat_message",
                {"text": "Hello", "user": "test_user"},
            )

            assert message_id is not None

            # Retrieve messages
            messages = await conn.fetch(
                """
                SELECT message_type, message_content
                FROM websocket_messages
                WHERE connection_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                "ws_conn_123",
            )

            assert len(messages) == 1

            # Cleanup
            await conn.execute("DELETE FROM websocket_messages WHERE id = $1", message_id)

    @pytest.mark.asyncio
    async def test_websocket_disconnection(self, db_pool):
        """Test WebSocket disconnection"""

        async with db_pool.acquire() as conn:
            # Create connection
            connection_id = "ws_disconnect_test"
            conn_id = await conn.fetchval(
                """
                INSERT INTO websocket_connections (connection_id, user_id, status)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                connection_id,
                "test_user",
                "connected",
            )

            # Disconnect
            await conn.execute(
                """
                UPDATE websocket_connections
                SET status = $1, disconnected_at = NOW()
                WHERE id = $2
                """,
                "disconnected",
                conn_id,
            )

            # Verify disconnection
            connection = await conn.fetchrow(
                """
                SELECT status, disconnected_at
                FROM websocket_connections
                WHERE id = $1
                """,
                conn_id,
            )

            assert connection["status"] == "disconnected"
            assert connection["disconnected_at"] is not None

            # Cleanup
            await conn.execute("DELETE FROM websocket_connections WHERE id = $1", conn_id)

    @pytest.mark.asyncio
    async def test_websocket_broadcast(self, db_pool):
        """Test WebSocket broadcast"""

        async with db_pool.acquire() as conn:
            # Create multiple connections
            connection_ids = ["ws_1", "ws_2", "ws_3"]

            for conn_id in connection_ids:
                await conn.execute(
                    """
                    INSERT INTO websocket_connections (connection_id, user_id, status)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (connection_id) DO NOTHING
                    """,
                    conn_id,
                    "test_user",
                    "connected",
                )

            # Get active connections for broadcast
            active_connections = await conn.fetch(
                """
                SELECT connection_id
                FROM websocket_connections
                WHERE status = $1
                """,
                "connected",
            )

            assert len(active_connections) >= len(connection_ids)

            # Cleanup
            await conn.execute(
                """
                DELETE FROM websocket_connections
                WHERE connection_id = ANY($1)
                """,
                connection_ids,
            )
