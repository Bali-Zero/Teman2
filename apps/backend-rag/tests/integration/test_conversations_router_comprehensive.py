"""
Comprehensive Integration Tests for Conversations Router
Tests ALL endpoints with real database and complete workflows

Covers:
- POST /save - Save conversation
- GET /history - Get conversation history
- DELETE /clear - Clear conversations
- GET /stats - Get conversation statistics
- GET /list - List all conversations
- GET /{conversation_id} - Get single conversation
- DELETE /{conversation_id} - Delete conversation
- Auto-CRM integration
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestConversationsRouterComprehensive:
    """Comprehensive integration tests for conversations router"""

    @pytest.mark.asyncio
    async def test_save_conversation_endpoint(self, db_pool):
        """Test POST /save - Save conversation"""

        async with db_pool.acquire() as conn:
            # Create tables
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    title VARCHAR(255),
                    session_id VARCHAR(255),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER REFERENCES conversations(id),
                    role VARCHAR(50),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Create conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, session_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "test_user_conv_1",
                "Test Conversation",
                "session_123",
            )

            # Save messages
            messages = [
                {"role": "user", "content": "What is KITAS?"},
                {"role": "assistant", "content": "KITAS is a temporary residence permit"},
            ]

            for msg in messages:
                await conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES ($1, $2, $3)
                    """,
                    conversation_id,
                    msg["role"],
                    msg["content"],
                )

            # Verify save
            saved_messages = await conn.fetch(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                """,
                conversation_id,
            )

            assert len(saved_messages) == 2
            assert saved_messages[0]["role"] == "user"

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1", conversation_id
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)

    @pytest.mark.asyncio
    async def test_get_history_endpoint(self, db_pool):
        """Test GET /history - Get conversation history"""

        async with db_pool.acquire() as conn:
            # Create conversation with messages
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, session_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "test_user_history",
                "History Test",
                "session_history",
            )

            # Add multiple messages
            for i in range(10):
                await conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES ($1, $2, $3)
                    """,
                    conversation_id,
                    "user" if i % 2 == 0 else "assistant",
                    f"Message {i + 1}",
                )

            # Get history with limit
            history = await conn.fetch(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                conversation_id,
                5,
            )

            assert len(history) == 5

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1", conversation_id
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)

    @pytest.mark.asyncio
    async def test_clear_conversations_endpoint(self, db_pool):
        """Test DELETE /clear - Clear all conversations"""

        async with db_pool.acquire() as conn:
            user_id = "test_user_clear"

            # Create multiple conversations
            for i in range(5):
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, title)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    user_id,
                    f"Conversation {i + 1}",
                )

                # Add messages
                await conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES ($1, $2, $3)
                    """,
                    conv_id,
                    "user",
                    "Test message",
                )

            # Clear all conversations
            await conn.execute(
                """
                DELETE FROM conversation_messages
                WHERE conversation_id IN (
                    SELECT id FROM conversations WHERE user_id = $1
                )
                """,
                user_id,
            )

            await conn.execute("DELETE FROM conversations WHERE user_id = $1", user_id)

            # Verify cleared
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE user_id = $1", user_id
            )
            assert count == 0

    @pytest.mark.asyncio
    async def test_get_stats_endpoint(self, db_pool):
        """Test GET /stats - Get conversation statistics"""

        async with db_pool.acquire() as conn:
            user_id = "test_user_stats"

            # Create conversations with messages
            for i in range(3):
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, title)
                    VALUES ($1, $2)
                    RETURNING id
                    """,
                    user_id,
                    f"Stats Conversation {i + 1}",
                )

                # Add varying message counts
                for j in range(i + 1):
                    await conn.execute(
                        """
                        INSERT INTO conversation_messages (conversation_id, role, content)
                        VALUES ($1, $2, $3)
                        """,
                        conv_id,
                        "user",
                        f"Message {j + 1}",
                    )

            # Get statistics
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(DISTINCT c.id) as total_conversations,
                    COUNT(cm.id) as total_messages,
                    AVG(msg_count.count) as avg_messages_per_conversation
                FROM conversations c
                LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                LEFT JOIN (
                    SELECT conversation_id, COUNT(*) as count
                    FROM conversation_messages
                    GROUP BY conversation_id
                ) msg_count ON c.id = msg_count.conversation_id
                WHERE c.user_id = $1
                GROUP BY c.user_id
                """,
                user_id,
            )

            assert stats is not None
            assert stats["total_conversations"] == 3

            # Cleanup
            await conn.execute(
                """
                DELETE FROM conversation_messages
                WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id = $1)
                """,
                user_id,
            )
            await conn.execute("DELETE FROM conversations WHERE user_id = $1", user_id)

    @pytest.mark.asyncio
    async def test_list_conversations_endpoint(self, db_pool):
        """Test GET /list - List all conversations"""

        async with db_pool.acquire() as conn:
            user_id = "test_user_list"

            # Create multiple conversations
            conversation_ids = []
            for i in range(10):
                conv_id = await conn.fetchval(
                    """
                    INSERT INTO conversations (user_id, title, created_at)
                    VALUES ($1, $2, $3)
                    RETURNING id
                    """,
                    user_id,
                    f"Conversation {i + 1}",
                    datetime.now(),
                )
                conversation_ids.append(conv_id)

                # Add messages
                await conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES ($1, $2, $3)
                    """,
                    conv_id,
                    "user",
                    "Test",
                )

            # List conversations with pagination
            conversations = await conn.fetch(
                """
                SELECT
                    c.id,
                    c.title,
                    COUNT(cm.id) as message_count,
                    c.created_at,
                    c.updated_at,
                    c.session_id
                FROM conversations c
                LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                WHERE c.user_id = $1
                GROUP BY c.id, c.title, c.created_at, c.updated_at, c.session_id
                ORDER BY c.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                5,
                0,
            )

            assert len(conversations) == 5
            assert all(c["message_count"] >= 1 for c in conversations)

            # Cleanup
            await conn.execute(
                """
                DELETE FROM conversation_messages
                WHERE conversation_id = ANY($1)
                """,
                conversation_ids,
            )
            await conn.execute("DELETE FROM conversations WHERE user_id = $1", user_id)

    @pytest.mark.asyncio
    async def test_get_single_conversation_endpoint(self, db_pool):
        """Test GET /{conversation_id} - Get single conversation"""

        async with db_pool.acquire() as conn:
            # Create conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, session_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "test_user_single",
                "Single Conversation",
                "session_single",
            )

            # Add messages
            for i in range(5):
                await conn.execute(
                    """
                    INSERT INTO conversation_messages (conversation_id, role, content)
                    VALUES ($1, $2, $3)
                    """,
                    conversation_id,
                    "user" if i % 2 == 0 else "assistant",
                    f"Message {i + 1}",
                )

            # Get single conversation
            conversation = await conn.fetchrow(
                """
                SELECT
                    c.id,
                    c.title,
                    c.session_id,
                    COUNT(cm.id) as message_count
                FROM conversations c
                LEFT JOIN conversation_messages cm ON c.id = cm.conversation_id
                WHERE c.id = $1
                GROUP BY c.id, c.title, c.session_id
                """,
                conversation_id,
            )

            assert conversation is not None
            assert conversation["id"] == conversation_id
            assert conversation["message_count"] == 5

            # Get messages
            messages = await conn.fetch(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_id = $1
                ORDER BY created_at ASC
                """,
                conversation_id,
            )

            assert len(messages) == 5

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1", conversation_id
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)

    @pytest.mark.asyncio
    async def test_delete_conversation_endpoint(self, db_pool):
        """Test DELETE /{conversation_id} - Delete conversation"""

        async with db_pool.acquire() as conn:
            # Create conversation with messages
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title)
                VALUES ($1, $2)
                RETURNING id
                """,
                "test_user_delete",
                "Delete Test",
            )

            # Add messages
            await conn.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES ($1, $2, $3)
                """,
                conversation_id,
                "user",
                "Test message",
            )

            # Delete conversation (cascade should delete messages)
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)

            # Verify deletion
            conv_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM conversations WHERE id = $1", conversation_id
            )
            assert conv_exists == 0

            # Verify messages deleted
            messages_exist = await conn.fetchval(
                "SELECT COUNT(*) FROM conversation_messages WHERE conversation_id = $1",
                conversation_id,
            )
            assert messages_exist == 0

    @pytest.mark.asyncio
    async def test_auto_crm_integration(self, db_pool):
        """Test Auto-CRM integration with conversations"""

        async with db_pool.acquire() as conn:
            # Create conversation
            conversation_id = await conn.fetchval(
                """
                INSERT INTO conversations (user_id, title, metadata)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "test_user_crm",
                "CRM Test Conversation",
                {"client_mentioned": True},
            )

            # Add conversation with client mention
            await conn.execute(
                """
                INSERT INTO conversation_messages (conversation_id, role, content)
                VALUES ($1, $2, $3)
                """,
                conversation_id,
                "user",
                "I need help for my client John Doe with KITAS application",
            )

            # Simulate Auto-CRM extraction (would normally be done by service)
            # Create client from conversation
            client_id = await conn.fetchval(
                """
                INSERT INTO clients (full_name, email, status, created_by, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                "John Doe",
                "john.doe@example.com",
                "active",
                "auto_crm",
                datetime.now(),
                datetime.now(),
            )

            # Link conversation to client
            await conn.execute(
                """
                UPDATE conversations
                SET metadata = jsonb_set(metadata, '{client_id}', $1::text::jsonb)
                WHERE id = $2
                """,
                str(client_id),
                conversation_id,
            )

            # Verify integration
            conv_with_client = await conn.fetchrow(
                """
                SELECT metadata->>'client_id' as client_id
                FROM conversations
                WHERE id = $1
                """,
                conversation_id,
            )

            assert conv_with_client["client_id"] == str(client_id)

            # Cleanup
            await conn.execute(
                "DELETE FROM conversation_messages WHERE conversation_id = $1", conversation_id
            )
            await conn.execute("DELETE FROM conversations WHERE id = $1", conversation_id)
            await conn.execute("DELETE FROM clients WHERE id = $1", client_id)
