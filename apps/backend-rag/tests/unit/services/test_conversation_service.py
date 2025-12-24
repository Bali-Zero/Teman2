"""
Comprehensive unit tests for ConversationService

Tests cover:
- Initialization and lazy loading of Auto-CRM
- Conversation saving to DB and memory cache
- Conversation history retrieval from DB and memory cache
- Fallback behavior when DB is unavailable
- Error handling and edge cases
- Auto-CRM integration

Target coverage: 90%+
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.conversation_service import ConversationService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg database pool"""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock pool.acquire() context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = acquire_cm

    # Mock async methods
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()

    return pool, conn


@pytest.fixture
def mock_memory_cache():
    """Mock InMemoryConversationCache"""
    cache = MagicMock()
    cache.add_message = MagicMock()
    cache.get_conversation = MagicMock(return_value=None)
    return cache


@pytest.fixture
def mock_auto_crm_service():
    """Mock AutoCRMService"""
    service = MagicMock()
    service.process_conversation = AsyncMock(
        return_value={
            "processed": True,
            "client_id": 123,
            "client_created": True,
        }
    )
    return service


@pytest.fixture
def conversation_service(mock_db_pool):
    """Create ConversationService instance with mocked DB pool"""
    pool, _ = mock_db_pool
    return ConversationService(db_pool=pool)


@pytest.fixture
def conversation_service_no_pool():
    """Create ConversationService instance without DB pool"""
    return ConversationService(db_pool=None)


@pytest.fixture
def sample_messages():
    """Sample conversation messages"""
    return [
        {"role": "user", "content": "Hello, I need help with my business"},
        {"role": "assistant", "content": "I'd be happy to help! What can I assist you with?"},
        {"role": "user", "content": "I want to register a company in Bali"},
    ]


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_pool(mock_db_pool):
    """Test initialization with database pool"""
    pool, _ = mock_db_pool
    service = ConversationService(db_pool=pool)

    assert service.db_pool == pool
    assert service._auto_crm_service is None


def test_init_without_pool():
    """Test initialization without database pool"""
    service = ConversationService(db_pool=None)

    assert service.db_pool is None
    assert service._auto_crm_service is None


# ============================================================================
# Tests for _get_auto_crm
# ============================================================================


def test_get_auto_crm_success(conversation_service, mock_auto_crm_service):
    """Test lazy loading of Auto-CRM service successfully"""
    # Mock the import at the module level
    with patch("services.auto_crm_service.get_auto_crm_service", return_value=mock_auto_crm_service):
        result = conversation_service._get_auto_crm()

        assert result == mock_auto_crm_service
        assert conversation_service._auto_crm_service == mock_auto_crm_service


def test_get_auto_crm_cached(conversation_service, mock_auto_crm_service):
    """Test that Auto-CRM service is cached after first load"""
    # Mock the import at the module level
    with patch("services.auto_crm_service.get_auto_crm_service", return_value=mock_auto_crm_service) as mock_get_service:
        # First call
        result1 = conversation_service._get_auto_crm()
        # Second call
        result2 = conversation_service._get_auto_crm()

        assert result1 == result2 == mock_auto_crm_service
        # get_auto_crm_service should only be called once
        assert mock_get_service.call_count == 1


def test_get_auto_crm_import_error(conversation_service):
    """Test handling of ImportError when loading Auto-CRM"""
    # Patch builtins to make the import fail
    with patch("builtins.__import__", side_effect=ImportError("Module not found")):
        result = conversation_service._get_auto_crm()

        assert result is None
        assert conversation_service._auto_crm_service is False


def test_get_auto_crm_general_exception(conversation_service):
    """Test handling of general exception when loading Auto-CRM"""
    # Mock the import to raise an exception
    with patch("services.auto_crm_service.get_auto_crm_service", side_effect=Exception("Unexpected error")):
        result = conversation_service._get_auto_crm()

        assert result is None
        assert conversation_service._auto_crm_service is False


def test_get_auto_crm_returns_none_when_cached_false(conversation_service):
    """Test that _get_auto_crm returns None when cached value is False"""
    conversation_service._auto_crm_service = False

    result = conversation_service._get_auto_crm()

    assert result is None


# ============================================================================
# Tests for save_conversation - Success Cases
# ============================================================================


@pytest.mark.asyncio
async def test_save_conversation_success_db_and_cache(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test successful save to both DB and memory cache"""
    pool, conn = mock_db_pool
    user_email = "test@example.com"
    session_id = "test-session-123"

    # Mock DB insert returning conversation_id
    conn.fetchrow.return_value = {"id": 42}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.save_conversation(
            user_email=user_email,
            messages=sample_messages,
            session_id=session_id,
        )

    # Verify result
    assert result["success"] is True
    assert result["conversation_id"] == 42
    assert result["messages_saved"] == 3
    assert result["user_email"] == user_email
    assert result["session_id"] == session_id
    assert result["persistence_mode"] == "db"

    # Verify memory cache was called
    assert mock_memory_cache.add_message.call_count == 3
    mock_memory_cache.add_message.assert_any_call(
        session_id, "user", "Hello, I need help with my business"
    )

    # Verify DB was called
    conn.fetchrow.assert_called_once()
    call_args = conn.fetchrow.call_args[0]
    assert "INSERT INTO conversations" in call_args[0]
    assert call_args[1] == user_email
    assert call_args[2] == session_id
    assert call_args[3] == sample_messages


@pytest.mark.asyncio
async def test_save_conversation_auto_generated_session_id(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test that session_id is auto-generated if not provided"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 10}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Verify session_id was generated
    assert result["session_id"].startswith("session-")
    assert len(result["session_id"]) > 10


@pytest.mark.asyncio
async def test_save_conversation_with_metadata(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test saving conversation with metadata"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 15}

    metadata = {
        "team_member": "john@example.com",
        "channel": "web",
        "language": "en",
    }

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
            metadata=metadata,
        )

    # Verify metadata was passed to DB
    call_args = conn.fetchrow.call_args[0]
    assert call_args[4] == metadata


@pytest.mark.asyncio
async def test_save_conversation_with_auto_crm(
    conversation_service,
    mock_db_pool,
    mock_memory_cache,
    mock_auto_crm_service,
    sample_messages,
):
    """Test that Auto-CRM is triggered on successful DB save"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 50}

    crm_result = {
        "processed": True,
        "client_id": 999,
        "client_created": True,
    }
    mock_auto_crm_service.process_conversation.return_value = crm_result

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        with patch.object(
            conversation_service, "_get_auto_crm", return_value=mock_auto_crm_service
        ):
            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=sample_messages,
                session_id="session-123",
            )

    # Verify Auto-CRM was called
    mock_auto_crm_service.process_conversation.assert_called_once()
    call_kwargs = mock_auto_crm_service.process_conversation.call_args[1]
    assert call_kwargs["conversation_id"] == 50
    assert call_kwargs["messages"] == sample_messages
    assert call_kwargs["user_email"] == "test@example.com"
    assert call_kwargs["team_member"] == "system"
    assert call_kwargs["db_pool"] == pool

    # Verify CRM result in response
    assert result["crm"] == crm_result


@pytest.mark.asyncio
async def test_save_conversation_with_auto_crm_team_member(
    conversation_service,
    mock_db_pool,
    mock_memory_cache,
    mock_auto_crm_service,
    sample_messages,
):
    """Test that team_member from metadata is passed to Auto-CRM"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 60}

    metadata = {"team_member": "jane@example.com"}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        with patch.object(
            conversation_service, "_get_auto_crm", return_value=mock_auto_crm_service
        ):
            await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=sample_messages,
                metadata=metadata,
            )

    # Verify team_member was passed
    call_kwargs = mock_auto_crm_service.process_conversation.call_args[1]
    assert call_kwargs["team_member"] == "jane@example.com"


# ============================================================================
# Tests for save_conversation - Failure Cases
# ============================================================================


@pytest.mark.asyncio
async def test_save_conversation_db_error_falls_back_to_memory(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test that DB error falls back to memory-only persistence"""
    pool, conn = mock_db_pool
    conn.fetchrow.side_effect = Exception("Database connection failed")

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Verify fallback behavior
    assert result["success"] is True
    assert result["conversation_id"] == 0
    assert result["persistence_mode"] == "memory_fallback"

    # Verify memory cache was still called
    assert mock_memory_cache.add_message.call_count == 3

    # Verify Auto-CRM was not called
    assert result["crm"] == {}


@pytest.mark.asyncio
async def test_save_conversation_no_db_pool(
    conversation_service_no_pool, mock_memory_cache, sample_messages
):
    """Test save when no DB pool is available"""
    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service_no_pool.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Verify memory-only mode
    assert result["success"] is True
    assert result["conversation_id"] == 0
    assert result["persistence_mode"] == "memory_fallback"
    assert result["crm"] == {}

    # Memory cache should still work
    assert mock_memory_cache.add_message.call_count == 3


@pytest.mark.asyncio
async def test_save_conversation_memory_cache_error(
    conversation_service, mock_db_pool, sample_messages
):
    """Test that memory cache errors are handled gracefully"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 25}

    mock_cache = MagicMock()
    mock_cache.add_message.side_effect = Exception("Cache error")

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_cache
    ):
        result = await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Should still succeed with DB save
    assert result["success"] is True
    assert result["conversation_id"] == 25
    assert result["persistence_mode"] == "db"


@pytest.mark.asyncio
async def test_save_conversation_auto_crm_error(
    conversation_service,
    mock_db_pool,
    mock_memory_cache,
    sample_messages,
):
    """Test that Auto-CRM errors don't break the save operation"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 30}

    mock_crm = MagicMock()
    mock_crm.process_conversation = AsyncMock(side_effect=Exception("CRM error"))

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        with patch.object(conversation_service, "_get_auto_crm", return_value=mock_crm):
            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=sample_messages,
            )

    # Conversation should still be saved
    assert result["success"] is True
    assert result["conversation_id"] == 30

    # CRM result should indicate error
    assert result["crm"]["processed"] is False
    assert "error" in result["crm"]


@pytest.mark.asyncio
async def test_save_conversation_no_auto_crm_available(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test behavior when Auto-CRM is not available"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 35}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        with patch.object(conversation_service, "_get_auto_crm", return_value=None):
            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=sample_messages,
            )

    # Should save successfully without CRM
    assert result["success"] is True
    assert result["crm"]["processed"] is False
    assert result["crm"]["reason"] == "auto-crm not available"


@pytest.mark.asyncio
async def test_save_conversation_empty_messages(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test saving conversation with empty messages list"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 40}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        with patch.object(conversation_service, "_get_auto_crm", return_value=None):
            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=[],
            )

    # Should save but not trigger CRM (no messages)
    assert result["success"] is True
    assert result["messages_saved"] == 0
    assert result["crm"]["processed"] is False


# ============================================================================
# Tests for get_history - DB retrieval
# ============================================================================


@pytest.mark.asyncio
async def test_get_history_from_db_with_session_id(conversation_service, mock_db_pool):
    """Test retrieving history from DB with session_id"""
    pool, conn = mock_db_pool

    stored_messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    conn.fetchrow.return_value = {"messages": stored_messages}

    result = await conversation_service.get_history(
        user_email="test@example.com",
        session_id="session-123",
    )

    # Verify result
    assert result["messages"] == stored_messages
    assert result["source"] == "db"
    assert result["total"] == 2

    # Verify DB query
    conn.fetchrow.assert_called_once()
    call_args = conn.fetchrow.call_args[0]
    assert "WHERE user_id = $1 AND session_id = $2" in call_args[0]
    assert call_args[1] == "test@example.com"
    assert call_args[2] == "session-123"


@pytest.mark.asyncio
async def test_get_history_from_db_without_session_id(
    conversation_service, mock_db_pool
):
    """Test retrieving history from DB without session_id"""
    pool, conn = mock_db_pool

    stored_messages = [
        {"role": "user", "content": "Previous message"},
    ]

    conn.fetchrow.return_value = {"messages": stored_messages}

    result = await conversation_service.get_history(
        user_email="test@example.com",
    )

    # Verify query without session_id filter
    call_args = conn.fetchrow.call_args[0]
    assert "WHERE user_id = $1" in call_args[0]
    assert "session_id" not in call_args[0]
    assert call_args[1] == "test@example.com"


@pytest.mark.asyncio
async def test_get_history_from_db_with_limit(conversation_service, mock_db_pool):
    """Test that limit parameter is applied to messages"""
    pool, conn = mock_db_pool

    # Create 30 messages
    stored_messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
        for i in range(30)
    ]

    conn.fetchrow.return_value = {"messages": stored_messages}

    result = await conversation_service.get_history(
        user_email="test@example.com",
        limit=10,
    )

    # Should return last 10 messages
    assert len(result["messages"]) == 10
    assert result["messages"][0]["content"] == "Message 20"
    assert result["total"] == 30


@pytest.mark.asyncio
async def test_get_history_from_db_no_limit(conversation_service, mock_db_pool):
    """Test retrieving all messages when limit is 0"""
    pool, conn = mock_db_pool

    stored_messages = [{"role": "user", "content": f"Msg {i}"} for i in range(5)]
    conn.fetchrow.return_value = {"messages": stored_messages}

    result = await conversation_service.get_history(
        user_email="test@example.com",
        limit=0,
    )

    # Should return all messages
    assert len(result["messages"]) == 5


@pytest.mark.asyncio
async def test_get_history_from_db_json_string(conversation_service, mock_db_pool):
    """Test parsing messages when stored as JSON string"""
    pool, conn = mock_db_pool

    messages_list = [{"role": "user", "content": "Test"}]
    messages_json = json.dumps(messages_list)

    conn.fetchrow.return_value = {"messages": messages_json}

    result = await conversation_service.get_history(
        user_email="test@example.com",
    )

    # Should parse JSON and return list
    assert result["messages"] == messages_list
    assert isinstance(result["messages"], list)


# ============================================================================
# Tests for get_history - Memory cache fallback
# ============================================================================


@pytest.mark.asyncio
async def test_get_history_fallback_to_cache(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test falling back to memory cache when DB returns no results"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None

    cached_messages = [
        {"role": "user", "content": "Cached message"},
    ]
    mock_memory_cache.get_conversation.return_value = cached_messages

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.get_history(
            user_email="test@example.com",
            session_id="session-123",
        )

    # Should return cached messages
    assert result["messages"] == cached_messages
    assert result["source"] == "memory_cache"
    assert result["total"] == 1

    # Verify cache was queried
    mock_memory_cache.get_conversation.assert_called_once_with("session-123")


@pytest.mark.asyncio
async def test_get_history_cache_no_session_id(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test that cache is not queried when no session_id provided"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.get_history(
            user_email="test@example.com",
        )

    # Cache should not be queried without session_id
    mock_memory_cache.get_conversation.assert_not_called()

    # Should return empty messages with source=db (since DB was queried but returned empty)
    assert result["messages"] == []
    assert result["source"] == "db"


@pytest.mark.asyncio
async def test_get_history_db_error_fallback_to_cache(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test that DB errors trigger fallback to cache"""
    pool, conn = mock_db_pool
    conn.fetchrow.side_effect = Exception("DB error")

    cached_messages = [{"role": "user", "content": "From cache"}]
    mock_memory_cache.get_conversation.return_value = cached_messages

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.get_history(
            user_email="test@example.com",
            session_id="session-456",
        )

    # Should fall back to cache
    assert result["messages"] == cached_messages
    assert result["source"] == "memory_cache"


@pytest.mark.asyncio
async def test_get_history_cache_error(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test handling of cache errors"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None

    mock_memory_cache.get_conversation.side_effect = Exception("Cache error")

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.get_history(
            user_email="test@example.com",
            session_id="session-789",
        )

    # Should return empty messages with source=db (cache error is logged but doesn't change source)
    assert result["messages"] == []
    assert result["source"] == "db"


@pytest.mark.asyncio
async def test_get_history_no_db_pool(conversation_service_no_pool, mock_memory_cache):
    """Test get_history when no DB pool is available"""
    cached_messages = [{"role": "user", "content": "Only cache"}]
    mock_memory_cache.get_conversation.return_value = cached_messages

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service_no_pool.get_history(
            user_email="test@example.com",
            session_id="session-999",
        )

    # Should get from cache
    assert result["messages"] == cached_messages
    assert result["source"] == "memory_cache"


@pytest.mark.asyncio
async def test_get_history_empty_db_result(conversation_service, mock_db_pool):
    """Test handling when DB returns row with empty messages"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"messages": None}

    result = await conversation_service.get_history(
        user_email="test@example.com",
    )

    # Should return empty with source=db (row exists but messages is None, so if check fails)
    assert result["messages"] == []
    assert result["source"] == "db"


@pytest.mark.asyncio
async def test_get_history_cache_limit_applied(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test that limit is applied to cached messages"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = None

    cached_messages = [
        {"role": "user", "content": f"Msg {i}"} for i in range(25)
    ]
    mock_memory_cache.get_conversation.return_value = cached_messages

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.get_history(
            user_email="test@example.com",
            session_id="session-limit",
            limit=5,
        )

    # Should return last 5 messages
    assert len(result["messages"]) == 5
    assert result["messages"][0]["content"] == "Msg 20"
    assert result["total"] == 25


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_save_and_get_conversation_flow(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test complete flow of saving and retrieving conversation"""
    pool, conn = mock_db_pool

    # Mock save operation
    conn.fetchrow.return_value = {"id": 100}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        # Save conversation
        save_result = await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
            session_id="session-flow",
        )

        # Mock get operation
        conn.fetchrow.return_value = {"messages": sample_messages}

        # Get conversation
        get_result = await conversation_service.get_history(
            user_email="test@example.com",
            session_id="session-flow",
        )

    # Verify flow
    assert save_result["success"] is True
    assert save_result["conversation_id"] == 100
    assert get_result["messages"] == sample_messages
    assert get_result["source"] == "db"


@pytest.mark.asyncio
async def test_save_conversation_special_characters(
    conversation_service, mock_db_pool, mock_memory_cache
):
    """Test saving messages with special characters"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 200}

    special_messages = [
        {"role": "user", "content": "Test with émojis 🎉 and spëcial chars"},
        {"role": "assistant", "content": "Response with\nnewlines\tand\ttabs"},
    ]

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        result = await conversation_service.save_conversation(
            user_email="tëst@example.com",
            messages=special_messages,
        )

    assert result["success"] is True
    assert result["messages_saved"] == 2


@pytest.mark.asyncio
async def test_get_history_default_limit(conversation_service, mock_db_pool):
    """Test that default limit is 20 messages"""
    pool, conn = mock_db_pool

    # Create 100 messages
    many_messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"Msg {i}"}
        for i in range(100)
    ]
    conn.fetchrow.return_value = {"messages": many_messages}

    result = await conversation_service.get_history(
        user_email="test@example.com",
    )

    # Should return last 20 by default
    assert len(result["messages"]) == 20
    assert result["total"] == 100
    assert result["messages"][0]["content"] == "Msg 80"


@pytest.mark.asyncio
async def test_save_conversation_metadata_defaults_to_empty_dict(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test that metadata defaults to empty dict when not provided"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 300}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Verify empty dict was passed
    call_args = conn.fetchrow.call_args[0]
    assert call_args[4] == {}


@pytest.mark.asyncio
async def test_save_conversation_timestamp_generated(
    conversation_service, mock_db_pool, mock_memory_cache, sample_messages
):
    """Test that timestamp is generated for DB save"""
    pool, conn = mock_db_pool
    conn.fetchrow.return_value = {"id": 400}

    with patch(
        "services.conversation_service.get_memory_cache", return_value=mock_memory_cache
    ):
        await conversation_service.save_conversation(
            user_email="test@example.com",
            messages=sample_messages,
        )

    # Verify timestamp argument
    call_args = conn.fetchrow.call_args[0]
    timestamp = call_args[5]
    assert isinstance(timestamp, datetime)
