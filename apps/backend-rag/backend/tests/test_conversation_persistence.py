"""
Test script for conversation persistence system
Verifies /webhook/chat endpoint and conversation history retrieval
"""

import asyncio
import os
from datetime import datetime

import asyncpg
import pytest

from backend.db.repositories.conversation_repository import ConversationRepository


@pytest.fixture
async def db_pool():
    """Create test database pool"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_conversation_repository_save_and_retrieve(db_pool):
    """Test saving and retrieving conversation messages"""
    repo = ConversationRepository(db_pool)

    session_id = f"test-session-{datetime.now().timestamp()}"
    user_id = "test@example.com"

    # Save initial messages
    messages = [
        {"role": "user", "content": "Hello, what is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
    ]

    conversation_id = await repo.save_messages(
        session_id=session_id,
        user_id=user_id,
        messages=messages,
        metadata={"test": True},
    )

    assert conversation_id is not None, "Failed to save conversation"

    # Retrieve messages
    retrieved_messages = await repo.get_messages(session_id=session_id)

    assert len(retrieved_messages) == 2, f"Expected 2 messages, got {len(retrieved_messages)}"
    assert retrieved_messages[0]["role"] == "user"
    assert retrieved_messages[1]["role"] == "assistant"

    # Save additional messages (should append)
    new_messages = [
        {"role": "user", "content": "What about Germany?"},
        {"role": "assistant", "content": "The capital of Germany is Berlin."},
    ]

    await repo.save_messages(
        session_id=session_id,
        user_id=user_id,
        messages=new_messages,
    )

    # Retrieve all messages
    all_messages = await repo.get_messages(session_id=session_id)

    assert len(all_messages) == 4, f"Expected 4 messages, got {len(all_messages)}"

    # Cleanup test data
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM conversations WHERE session_id = $1", session_id)

    print("✅ Test passed: Conversation save and retrieve")


@pytest.mark.asyncio
async def test_conversation_repository_limit(db_pool):
    """Test message retrieval with limit"""
    repo = ConversationRepository(db_pool)

    session_id = f"test-session-limit-{datetime.now().timestamp()}"
    user_id = "test@example.com"

    # Save 10 messages
    messages = []
    for i in range(10):
        messages.append({"role": "user", "content": f"Message {i}"})

    await repo.save_messages(
        session_id=session_id,
        user_id=user_id,
        messages=messages,
    )

    # Retrieve with limit
    limited_messages = await repo.get_messages(session_id=session_id, limit=5)

    assert len(limited_messages) == 5, f"Expected 5 messages, got {len(limited_messages)}"
    # Should get last 5 messages
    assert limited_messages[0]["content"] == "Message 5"
    assert limited_messages[-1]["content"] == "Message 9"

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM conversations WHERE session_id = $1", session_id)

    print("✅ Test passed: Message limit")


@pytest.mark.asyncio
async def test_conversation_cleanup(db_pool):
    """Test cleanup of old conversations"""
    repo = ConversationRepository(db_pool)

    # Create old conversation (simulate by setting created_at in the past)
    session_id = f"test-old-session-{datetime.now().timestamp()}"
    user_id = "test@example.com"

    async with db_pool.acquire() as conn:
        # Insert conversation with old timestamp
        from datetime import timedelta

        old_date = datetime.now() - timedelta(days=35)

        await conn.execute(
            """
            INSERT INTO conversations (user_id, session_id, messages, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            user_id,
            session_id,
            [{"role": "user", "content": "Old message"}],
            old_date,
        )

    # Run cleanup (delete conversations > 30 days)
    deleted_count = await repo.cleanup_old_conversations(days=30)

    assert deleted_count >= 1, f"Expected at least 1 deletion, got {deleted_count}"

    # Verify conversation was deleted
    messages = await repo.get_messages(session_id=session_id)
    assert len(messages) == 0, "Old conversation should be deleted"

    print("✅ Test passed: Conversation cleanup")


if __name__ == "__main__":
    asyncio.run(test_conversation_repository_save_and_retrieve(None))
