"""Test conversation persistence with mocked DB pool"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.retention_policy import ALLOW_CLOCK_DELETE_ENV, RETENTION_MIN_DAYS
from backend.db.repositories.conversation_repository import ConversationRepository


@pytest.fixture
def mock_db_pool() -> tuple:
    """Create mocked DB pool and connection."""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock transaction() as async context manager (not a coroutine)
    tx_cm = MagicMock()
    tx_cm.__aenter__ = AsyncMock(return_value=None)
    tx_cm.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=tx_cm)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn


@pytest.mark.asyncio
async def test_conversation_repository_save_and_retrieve(mock_db_pool: tuple) -> None:
    """Test saving and retrieving conversation messages with mocked DB."""
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    conn.fetchrow.side_effect = [None, {"id": 1}]
    result = await repo.save_messages(
        session_id="test-session",
        user_id="test@example.com",
        messages=[{"role": "user", "content": "Hello"}],
        metadata={"test": True},
    )
    assert result == 1


@pytest.mark.asyncio
async def test_conversation_repository_limit(mock_db_pool: tuple) -> None:
    """Test message retrieval with limit."""
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    msgs = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
    conn.fetchrow.return_value = {"messages": msgs}
    result = await repo.get_messages(session_id="test", limit=5)
    assert len(result) == 5


@pytest.mark.asyncio
async def test_conversation_cleanup(monkeypatch: pytest.MonkeyPatch, mock_db_pool: tuple) -> None:
    """Cleanup still deletes — at a policy-legal window, with the opt-in set.

    This test asked for `days=30` until 2026-08-08. That window is now refused;
    the deletion path itself is unchanged, which is what this asserts.
    """
    monkeypatch.setenv(ALLOW_CLOCK_DELETE_ENV, "1")
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    conn.execute.return_value = "DELETE 3"
    result = await repo.cleanup_old_conversations(days=RETENTION_MIN_DAYS)
    assert result == 3
