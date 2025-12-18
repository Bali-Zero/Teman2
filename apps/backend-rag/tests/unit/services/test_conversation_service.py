"""
Tests for conversation_service
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.conversation_service import ConversationService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    # pool.acquire() returns a context manager (mock_context)
    # mock_context.__aenter__() returns conn (via awaitable)
    mock_context = MagicMock()
    mock_context.__aenter__ = AsyncMock(return_value=conn)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = mock_context
    return pool


@pytest.fixture
def conversation_service(mock_db_pool):
    """Create ConversationService instance"""
    return ConversationService(db_pool=mock_db_pool)


class TestConversationService:
    """Test suite for ConversationService"""

    def test_init(self, mock_db_pool):
        """Test ConversationService initialization"""
        service = ConversationService(db_pool=mock_db_pool)
        assert service.db_pool == mock_db_pool
        assert service._auto_crm_service is None

    def test_get_auto_crm_success(self, conversation_service):
        """Test _get_auto_crm when service is available"""
        mock_crm = MagicMock()
        with patch("services.auto_crm_service.get_auto_crm_service", return_value=mock_crm):
            result = conversation_service._get_auto_crm()
            assert result == mock_crm
            assert conversation_service._auto_crm_service == mock_crm

    def test_get_auto_crm_import_error(self, conversation_service):
        """Test _get_auto_crm when import fails"""
        with patch(
            "services.auto_crm_service.get_auto_crm_service", side_effect=ImportError("No module")
        ):
            result = conversation_service._get_auto_crm()
            assert result is None
            assert conversation_service._auto_crm_service is False

    def test_get_auto_crm_exception(self, conversation_service):
        """Test _get_auto_crm when exception occurs"""
        with patch(
            "services.auto_crm_service.get_auto_crm_service", side_effect=Exception("Error")
        ):
            result = conversation_service._get_auto_crm()
            assert result is None
            assert conversation_service._auto_crm_service is False

    @pytest.mark.asyncio
    async def test_save_conversation_with_db_pool(self, conversation_service, mock_db_pool):
        """Test save_conversation with database pool"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        user_email = "test@example.com"

        # Setup mock db response
        mock_row = {"id": 123}

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        # Override fixture return
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock memory cache
        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        # Patch where it is defined, OR match how it is imported.
        # Since it is imported inside the method, we must patch the definition.
        with patch("services.conversation_service.get_memory_cache", return_value=mock_cache):
            with patch("services.auto_crm_service.get_auto_crm_service", return_value=None):
                result = await conversation_service.save_conversation(
                    user_email=user_email, messages=messages, session_id="test-session"
                )

        assert result["success"] is True
        assert result["conversation_id"] == 123
        assert result["messages_saved"] == 2
        assert result["user_email"] == user_email
        assert result["persistence_mode"] == "db"
        assert result["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_save_conversation_without_db_pool(self):
        """Test save_conversation without database pool"""
        service = ConversationService(db_pool=None)
        messages = [{"role": "user", "content": "Hello"}]

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("services.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await service.save_conversation(
                user_email="test@example.com", messages=messages
            )

        assert result["success"] is True
        assert result["persistence_mode"] == "memory_fallback"
        assert "session-" in result["session_id"]

    @pytest.mark.asyncio
    async def test_save_conversation_auto_generates_session_id(self, conversation_service):
        """Test that session_id is auto-generated if not provided"""
        messages = [{"role": "user", "content": "Hello"}]
        mock_cache = MagicMock()

        with patch("services.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.save_conversation(
                user_email="test@example.com", messages=messages
            )

        assert "session-" in result["session_id"]
        assert len(result["session_id"]) > 10

    @pytest.mark.asyncio
    async def test_get_history_with_db(self, conversation_service, mock_db_pool):
        """Test get_history retrieves from database"""
        user_email = "test@example.com"
        messages = [{"role": "user", "content": "Hello"}]

        mock_row = {"messages": messages}

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        # Override fixture return
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await conversation_service.get_history(user_email=user_email, limit=20)

        assert result["messages"] == messages
        assert result["source"] == "db"
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_history_with_session_id(self, conversation_service, mock_db_pool):
        """Test get_history with specific session_id"""
        user_email = "test@example.com"
        session_id = "test-session"
        messages = [{"role": "user", "content": "Hello"}]

        mock_row = {"messages": messages}

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row

        # Override the fixture's return value for specific conn
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await conversation_service.get_history(
            user_email=user_email, session_id=session_id, limit=20
        )

        assert result["messages"] == messages
        assert result["source"] == "db"

    @pytest.mark.asyncio
    async def test_get_history_fallback_to_memory_cache(self, conversation_service):
        """Test get_history falls back to memory cache when DB fails"""
        service = ConversationService(db_pool=None)
        user_email = "test@example.com"
        session_id = "test-session"
        cached_messages = [{"role": "user", "content": "Cached"}]

        mock_cache = MagicMock()
        mock_cache.get_conversation = MagicMock(return_value=cached_messages)

        with patch("services.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await service.get_history(
                user_email=user_email, session_id=session_id, limit=20
            )

        assert result["messages"] == cached_messages
        assert result["source"] == "memory_cache"

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, conversation_service, mock_db_pool):
        """Test get_history respects limit parameter"""
        user_email = "test@example.com"
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(30)]
        # Setup mock db response
        mock_row = {"messages": messages}

        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = mock_row
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await conversation_service.get_history(user_email=user_email, limit=10)

        assert len(result["messages"]) == 10
        assert result["total"] == 30
