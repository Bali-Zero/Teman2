"""
Extended unit tests for services.misc.conversation_service module
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.misc.conversation_service import ConversationService


@pytest.fixture
def mock_db_pool():
    """Create mock database connection pool"""
    pool = MagicMock()
    conn = MagicMock()

    # Mock connection context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)

    return pool, conn


@pytest.fixture
def conversation_service(mock_db_pool):
    """Create ConversationService instance"""
    pool, _ = mock_db_pool
    return ConversationService(db_pool=pool)


class TestConversationServiceInit:
    """Tests for ConversationService initialization"""

    def test_init_with_db_pool(self, mock_db_pool):
        """Test initialization with database pool"""
        pool, _ = mock_db_pool
        service = ConversationService(db_pool=pool)
        assert service.db_pool == pool
        assert service._auto_crm_service is None

    def test_init_without_db_pool(self):
        """Test initialization without database pool"""
        service = ConversationService(db_pool=None)
        assert service.db_pool is None


class TestGetAutoCrm:
    """Tests for _get_auto_crm method"""

    def test_get_auto_crm_lazy_load(self, conversation_service):
        """Test that auto CRM is lazy loaded"""
        # First call should load the service
        with patch("backend.services.crm.auto_crm_service.get_auto_crm_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            result = conversation_service._get_auto_crm()
            assert result == mock_service
            mock_get.assert_called_once()

    def test_get_auto_crm_import_error(self, conversation_service):
        """Test _get_auto_crm handles ImportError"""
        # Patch the import inside the method
        with patch("builtins.__import__", side_effect=ImportError("Module not found")):
            result = conversation_service._get_auto_crm()
            assert result is None

    def test_get_auto_crm_general_exception(self, conversation_service):
        """Test _get_auto_crm handles general exceptions"""
        with patch(
            "backend.services.crm.auto_crm_service.get_auto_crm_service", side_effect=Exception("Error")
        ):
            result = conversation_service._get_auto_crm()
            assert result is None

    def test_get_auto_crm_caches_result(self, conversation_service):
        """Test that _get_auto_crm caches the result"""
        with patch("backend.services.crm.auto_crm_service.get_auto_crm_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            # First call
            result1 = conversation_service._get_auto_crm()
            # Second call should use cached result
            result2 = conversation_service._get_auto_crm()

            assert result1 == result2 == mock_service
            # Should only be called once
            assert mock_get.call_count == 1


class TestSaveConversation:
    """Tests for save_conversation method"""

    @pytest.mark.asyncio
    async def test_save_conversation_success(self, conversation_service, mock_db_pool):
        """Test successful conversation save"""
        pool, conn = mock_db_pool

        # Mock database insert
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        # Mock memory cache
        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.save_conversation(
                user_email="test@test.com",
                messages=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                ],
                session_id="test-session",
            )

            assert result["success"] is True
            assert result["conversation_id"] == 123
            assert result["messages_saved"] == 2
            assert result["persistence_mode"] == "db"
            assert result["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_save_conversation_generates_session_id(self, conversation_service, mock_db_pool):
        """Test that session_id is generated if not provided"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.save_conversation(
                user_email="test@test.com",
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result["session_id"] is not None
            assert result["session_id"].startswith("session-")

    @pytest.mark.asyncio
    async def test_save_conversation_with_metadata(self, conversation_service, mock_db_pool):
        """Test save_conversation with metadata"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.save_conversation(
                user_email="test@test.com",
                messages=[{"role": "user", "content": "Hello"}],
                metadata={"team_member": "Alice", "source": "web"},
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_conversation_memory_cache_error(self, conversation_service, mock_db_pool):
        """Test save_conversation handles memory cache errors"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        # Mock memory cache to raise error
        with patch(
            "backend.services.misc.conversation_service.get_memory_cache",
            side_effect=Exception("Cache error"),
        ):
            result = await conversation_service.save_conversation(
                user_email="test@test.com",
                messages=[{"role": "user", "content": "Hello"}],
            )

            # Should still succeed with DB save
            assert result["success"] is True
            assert result["persistence_mode"] == "db"

    @pytest.mark.asyncio
    async def test_save_conversation_db_error(self, conversation_service, mock_db_pool):
        """Test save_conversation handles database errors"""
        pool, conn = mock_db_pool

        # Mock database error
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.save_conversation(
                user_email="test@test.com",
                messages=[{"role": "user", "content": "Hello"}],
            )

            # Should fallback to memory-only
            assert result["success"] is True
            assert result["persistence_mode"] == "memory_fallback"
            assert result["conversation_id"] == 0

    @pytest.mark.asyncio
    async def test_save_conversation_no_db_pool(self):
        """Test save_conversation without database pool"""
        service = ConversationService(db_pool=None)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await service.save_conversation(
                user_email="test@test.com",
                messages=[{"role": "user", "content": "Hello"}],
            )

            assert result["success"] is True
            assert result["persistence_mode"] == "memory_fallback"
            assert result["conversation_id"] == 0

    @pytest.mark.asyncio
    async def test_save_conversation_triggers_auto_crm(self, conversation_service, mock_db_pool):
        """Test save_conversation triggers auto CRM processing"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        mock_auto_crm = MagicMock()
        mock_auto_crm.process_conversation = AsyncMock(
            return_value={"processed": True, "extracted": {}}
        )

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            with patch.object(conversation_service, "_get_auto_crm", return_value=mock_auto_crm):
                result = await conversation_service.save_conversation(
                    user_email="test@test.com",
                    messages=[{"role": "user", "content": "Hello"}],
                    metadata={"team_member": "Alice"},
                )

                assert result["crm"]["processed"] is True
                mock_auto_crm.process_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_conversation_auto_crm_error(self, conversation_service, mock_db_pool):
        """Test save_conversation handles auto CRM errors"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        mock_auto_crm = MagicMock()
        mock_auto_crm.process_conversation = AsyncMock(side_effect=Exception("CRM error"))

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            with patch.object(conversation_service, "_get_auto_crm", return_value=mock_auto_crm):
                result = await conversation_service.save_conversation(
                    user_email="test@test.com",
                    messages=[{"role": "user", "content": "Hello"}],
                )

                assert result["crm"]["processed"] is False
                assert "error" in result["crm"]

    @pytest.mark.asyncio
    async def test_save_conversation_empty_messages_no_crm(
        self, conversation_service, mock_db_pool
    ):
        """Test save_conversation doesn't trigger CRM for empty messages"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        mock_cache = MagicMock()
        mock_cache.add_message = MagicMock()

        mock_auto_crm = MagicMock()

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            with patch.object(conversation_service, "_get_auto_crm", return_value=mock_auto_crm):
                result = await conversation_service.save_conversation(
                    user_email="test@test.com",
                    messages=[],
                )

                assert result["crm"]["processed"] is False
                assert result["crm"]["reason"] == "auto-crm not available"
                mock_auto_crm.process_conversation.assert_not_called()


class TestGetHistory:
    """Tests for get_history method"""

    @pytest.mark.asyncio
    async def test_get_history_with_session_id(self, conversation_service, mock_db_pool):
        """Test get_history with session_id"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "messages": [{"role": "user", "content": "Hello"}]
        }.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await conversation_service.get_history(
            user_email="test@test.com",
            session_id="test-session",
            limit=20,
        )

        assert result["source"] == "db"
        assert len(result["messages"]) == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_history_without_session_id(self, conversation_service, mock_db_pool):
        """Test get_history without session_id"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "messages": [{"role": "user", "content": "Hello"}]
        }.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await conversation_service.get_history(
            user_email="test@test.com",
            limit=20,
        )

        assert result["source"] == "db"
        assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_get_history_db_error_fallback_to_cache(self, conversation_service, mock_db_pool):
        """Test get_history falls back to memory cache on DB error"""
        pool, conn = mock_db_pool

        # Mock DB error
        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        mock_cache = MagicMock()
        mock_cache.get_conversation = MagicMock(
            return_value=[{"role": "user", "content": "Cached"}]
        )

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await conversation_service.get_history(
                user_email="test@test.com",
                session_id="test-session",
            )

            assert result["source"] == "memory_cache"
            assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_get_history_no_db_pool(self):
        """Test get_history without database pool"""
        service = ConversationService(db_pool=None)

        mock_cache = MagicMock()
        mock_cache.get_conversation = MagicMock(
            return_value=[{"role": "user", "content": "Cached"}]
        )

        with patch("backend.services.misc.conversation_service.get_memory_cache", return_value=mock_cache):
            result = await service.get_history(
                user_email="test@test.com",
                session_id="test-session",
            )

            assert result["source"] == "memory_cache"

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(self, conversation_service, mock_db_pool):
        """Test get_history respects limit parameter"""
        pool, conn = mock_db_pool

        # Mock many messages
        many_messages = [{"role": "user", "content": f"Message {i}"} for i in range(50)]
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"messages": many_messages}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await conversation_service.get_history(
            user_email="test@test.com",
            limit=10,
        )

        assert len(result["messages"]) == 10
        assert result["total"] == 50

    @pytest.mark.asyncio
    async def test_get_history_json_string_messages(self, conversation_service, mock_db_pool):
        """Test get_history handles JSON string messages"""
        pool, conn = mock_db_pool

        import json

        messages_json = json.dumps([{"role": "user", "content": "Hello"}])
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"messages": messages_json}.get(key, None)
        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await conversation_service.get_history(
            user_email="test@test.com",
        )

        assert isinstance(result["messages"], list)
        assert result["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_history_no_messages(self, conversation_service, mock_db_pool):
        """Test get_history when no messages found"""
        pool, conn = mock_db_pool

        # Mock no results
        conn.fetchrow = AsyncMock(return_value=None)

        result = await conversation_service.get_history(
            user_email="test@test.com",
        )

        assert result["messages"] == []
        assert result["total"] == 0
        # When DB returns None, source is "db" (not "fallback_failed" unless there's an exception)
        assert result["source"] == "db"
