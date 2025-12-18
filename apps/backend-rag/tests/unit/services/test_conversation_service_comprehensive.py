"""
Comprehensive tests for services/conversation_service.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.conversation_service import ConversationService


class TestConversationService:
    """Comprehensive test suite for ConversationService"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        pool.acquire.return_value.__aexit__.return_value = None
        return pool, conn

    @pytest.fixture
    def conversation_service(self, mock_db_pool):
        """Create ConversationService instance"""
        pool, _ = mock_db_pool
        return ConversationService(db_pool=pool)

    def test_init(self, mock_db_pool):
        """Test ConversationService initialization"""
        pool, _ = mock_db_pool
        service = ConversationService(db_pool=pool)
        assert service.db_pool == pool
        assert service._auto_crm_service is None

    def test_get_auto_crm_available(self, conversation_service):
        """Test _get_auto_crm when available"""
        with patch("services.auto_crm_service.get_auto_crm_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service
            result = conversation_service._get_auto_crm()
            assert result == mock_service

    def test_get_auto_crm_not_available(self, conversation_service):
        """Test _get_auto_crm when not available"""
        with patch("services.auto_crm_service.get_auto_crm_service", side_effect=ImportError()):
            result = conversation_service._get_auto_crm()
            assert result is None

    def test_get_auto_crm_error(self, conversation_service):
        """Test _get_auto_crm with error"""
        with patch(
            "services.auto_crm_service.get_auto_crm_service", side_effect=Exception("Error")
        ):
            result = conversation_service._get_auto_crm()
            assert result is None

    @pytest.mark.asyncio
    async def test_save_conversation_with_session_id(self, conversation_service, mock_db_pool):
        """Test save_conversation with session_id"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 123})

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_cache.return_value = mock_mem_cache

            messages = [{"role": "user", "content": "Hello"}]
            result = await conversation_service.save_conversation(
                "user@example.com", messages, session_id="session123"
            )

            assert result["success"] is True
            assert result["conversation_id"] == 123

    @pytest.mark.asyncio
    async def test_save_conversation_without_session_id(self, conversation_service, mock_db_pool):
        """Test save_conversation without session_id"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 123})

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_cache.return_value = mock_mem_cache

            messages = [{"role": "user", "content": "Hello"}]
            result = await conversation_service.save_conversation("user@example.com", messages)

            assert result["success"] is True
            assert result["session_id"].startswith("session-")

    @pytest.mark.asyncio
    async def test_save_conversation_memory_cache_error(self, conversation_service, mock_db_pool):
        """Test save_conversation with memory cache error"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 123})

        with patch(
            "services.conversation_service.get_memory_cache", side_effect=Exception("Error")
        ):
            messages = [{"role": "user", "content": "Hello"}]
            result = await conversation_service.save_conversation("user@example.com", messages)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_conversation_db_error(self, conversation_service, mock_db_pool):
        """Test save_conversation with database error"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("DB Error"))

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_cache.return_value = mock_mem_cache

            messages = [{"role": "user", "content": "Hello"}]
            result = await conversation_service.save_conversation("user@example.com", messages)

            assert result["success"] is True
            assert result["persistence_mode"] == "memory_fallback"

    @pytest.mark.asyncio
    async def test_save_conversation_no_db_pool(self):
        """Test save_conversation without db_pool"""
        service = ConversationService(db_pool=None)

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_cache.return_value = mock_mem_cache

            messages = [{"role": "user", "content": "Hello"}]
            result = await service.save_conversation("user@example.com", messages)

            assert result["success"] is True
            assert result["persistence_mode"] == "memory_fallback"

    @pytest.mark.asyncio
    async def test_save_conversation_with_auto_crm(self, conversation_service, mock_db_pool):
        """Test save_conversation with Auto-CRM"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"id": 123})

        mock_auto_crm = MagicMock()
        mock_auto_crm.process_conversation = AsyncMock(return_value={"success": True})
        conversation_service._auto_crm_service = mock_auto_crm

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_cache.return_value = mock_mem_cache

            messages = [{"role": "user", "content": "Hello"}]
            result = await conversation_service.save_conversation("user@example.com", messages)

            assert result["success"] is True
            assert "crm" in result

    @pytest.mark.asyncio
    async def test_get_history_with_session_id(self, conversation_service, mock_db_pool):
        """Test get_history with session_id"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"messages": [{"role": "user", "content": "Hello"}]})

        result = await conversation_service.get_history(
            "user@example.com", limit=20, session_id="session123"
        )

        assert "messages" in result
        assert result["source"] == "db"

    @pytest.mark.asyncio
    async def test_get_history_without_session_id(self, conversation_service, mock_db_pool):
        """Test get_history without session_id"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value={"messages": [{"role": "user", "content": "Hello"}]})

        result = await conversation_service.get_history("user@example.com", limit=20)

        assert "messages" in result
        assert result["source"] == "db"

    @pytest.mark.asyncio
    async def test_get_history_db_error(self, conversation_service, mock_db_pool):
        """Test get_history with database error"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(side_effect=Exception("DB Error"))

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_mem_cache.get_conversation = MagicMock(return_value=None)
            mock_cache.return_value = mock_mem_cache

            result = await conversation_service.get_history(
                "user@example.com", limit=20, session_id="session123"
            )

            assert "messages" in result
            assert result["source"] == "fallback_failed"

    @pytest.mark.asyncio
    async def test_get_history_fallback_to_cache(self, conversation_service, mock_db_pool):
        """Test get_history fallback to memory cache"""
        pool, conn = mock_db_pool
        conn.fetchrow = AsyncMock(return_value=None)

        with patch("services.conversation_service.get_memory_cache") as mock_cache:
            mock_mem_cache = MagicMock()
            mock_mem_cache.get_conversation = MagicMock(
                return_value=[{"role": "user", "content": "Hello"}]
            )
            mock_cache.return_value = mock_mem_cache

            result = await conversation_service.get_history(
                "user@example.com", limit=20, session_id="session123"
            )

            assert "messages" in result
            assert result["source"] == "memory_cache"

    @pytest.mark.asyncio
    async def test_get_history_json_string_messages(self, conversation_service, mock_db_pool):
        """Test get_history with JSON string messages"""
        import json

        pool, conn = mock_db_pool
        messages = [{"role": "user", "content": "Hello"}]
        conn.fetchrow = AsyncMock(return_value={"messages": json.dumps(messages)})

        result = await conversation_service.get_history("user@example.com", limit=20)

        assert "messages" in result
        assert isinstance(result["messages"], list)
