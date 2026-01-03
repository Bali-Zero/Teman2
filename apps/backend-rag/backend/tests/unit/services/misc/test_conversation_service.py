"""
Comprehensive tests for ConversationService
Target: >95% coverage
"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.conversation_service import ConversationService


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    conn = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


@pytest.fixture
def conversation_service(mock_db_pool):
    """Create ConversationService instance"""
    pool, conn = mock_db_pool
    return ConversationService(db_pool=pool)


class TestConversationService:
    """Tests for ConversationService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        pool, conn = mock_db_pool
        service = ConversationService(db_pool=pool)

        assert service.db_pool == pool
        assert service._auto_crm_service is None

    @pytest.mark.asyncio
    async def test_save_conversation_success(self, conversation_service, mock_db_pool):
        """Test successful conversation save"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 123}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=messages,
                session_id="test-session",
            )

            assert result["success"] is True
            assert result["conversation_id"] == 123
            assert mock_cache_instance.add_message.call_count == 2

    @pytest.mark.asyncio
    async def test_save_conversation_without_session_id(self, conversation_service, mock_db_pool):
        """Test saving conversation without session_id"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 456}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        messages = [{"role": "user", "content": "Test"}]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=messages,
            )

            assert result["success"] is True
            assert "session-" in result.get("session_id", "")

    @pytest.mark.asyncio
    async def test_save_conversation_with_metadata(self, conversation_service, mock_db_pool):
        """Test saving conversation with metadata"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 789}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        messages = [{"role": "user", "content": "Test"}]
        metadata = {"source": "web", "ip": "127.0.0.1"}

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=messages,
                metadata=metadata,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_conversation_memory_cache_error(self, conversation_service, mock_db_pool):
        """Test handling memory cache errors"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 999}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        messages = [{"role": "user", "content": "Test"}]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache.side_effect = Exception("Cache error")

            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=messages,
            )

            # Should still succeed with DB save
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_save_conversation_db_error(self, conversation_service, mock_db_pool):
        """Test handling database errors"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        messages = [{"role": "user", "content": "Test"}]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.save_conversation(
                user_email="test@example.com",
                messages=messages,
            )

            # Should still succeed with memory cache
            assert result["success"] is True
            assert result["conversation_id"] == 0

    @pytest.mark.asyncio
    async def test_save_conversation_no_db_pool(self):
        """Test saving conversation without database pool"""
        service = ConversationService(db_pool=None)

        messages = [{"role": "user", "content": "Test"}]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            result = await service.save_conversation(
                user_email="test@example.com",
                messages=messages,
            )

            # Should succeed with memory cache only
            assert result["success"] is True
            assert result["conversation_id"] == 0

    @pytest.mark.asyncio
    async def test_save_conversation_triggers_auto_crm(self, conversation_service, mock_db_pool):
        """Test that saving conversation triggers Auto-CRM"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 111}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        # Mock transaction context manager
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=None)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        conn.transaction = MagicMock(return_value=mock_transaction)

        messages = [{"role": "user", "content": "I need a KITAS"}]

        mock_auto_crm = AsyncMock()
        mock_auto_crm.process_conversation = AsyncMock(return_value={
            "success": True,
            "client_id": 1,
            "client_created": True,
        })

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            with patch.object(conversation_service, "_get_auto_crm", return_value=mock_auto_crm):
                result = await conversation_service.save_conversation(
                    user_email="test@example.com",
                    messages=messages,
                )

                assert result["success"] is True
                # Auto-CRM should be called
                mock_auto_crm.process_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_conversation_auto_crm_not_available(self, conversation_service, mock_db_pool):
        """Test handling when Auto-CRM is not available"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {"id": 222}[key]
        conn.fetchrow = AsyncMock(return_value=mock_row)

        messages = [{"role": "user", "content": "Test"}]

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache.return_value = mock_cache_instance

            with patch.object(conversation_service, "_get_auto_crm", return_value=None):
                result = await conversation_service.save_conversation(
                    user_email="test@example.com",
                    messages=messages,
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_history_success(self, conversation_service, mock_db_pool):
        """Test getting conversation history"""
        pool, conn = mock_db_pool

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "messages": [{"role": "user", "content": "Hello"}],
        }[key]

        conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await conversation_service.get_history(
            user_email="test@example.com",
            limit=10,
        )

        assert result is not None
        assert "messages" in result

    @pytest.mark.asyncio
    async def test_get_history_not_found(self, conversation_service, mock_db_pool):
        """Test getting conversation history when not found"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(return_value=None)

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_conversation = MagicMock(return_value=None)
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.get_history(
                user_email="test@example.com",
                limit=10,
            )

            assert result is not None
            assert len(result.get("messages", [])) == 0

    @pytest.mark.asyncio
    async def test_get_history_error(self, conversation_service, mock_db_pool):
        """Test handling errors when getting conversation history"""
        pool, conn = mock_db_pool

        conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))

        with patch("services.misc.conversation_service.get_memory_cache") as mock_cache:
            mock_cache_instance = MagicMock()
            mock_cache_instance.get_conversation = MagicMock(return_value=None)
            mock_cache.return_value = mock_cache_instance

            result = await conversation_service.get_history(
                user_email="test@example.com",
                limit=10,
            )

            assert result is not None
            assert result["source"] in ["memory_cache", "fallback_failed"]

    def test_get_auto_crm_lazy_load(self, conversation_service):
        """Test lazy loading of Auto-CRM service"""
        assert conversation_service._auto_crm_service is None

        with patch("services.crm.auto_crm_service.get_auto_crm_service") as mock_get:
            mock_service = MagicMock()
            mock_get.return_value = mock_service

            result = conversation_service._get_auto_crm()

            assert result == mock_service
            assert conversation_service._auto_crm_service == mock_service

    def test_get_auto_crm_import_error(self, conversation_service):
        """Test handling import error for Auto-CRM"""
        with patch("builtins.__import__", side_effect=ImportError("No module")):
            result = conversation_service._get_auto_crm()

            assert result is None
            assert conversation_service._auto_crm_service is False

    def test_get_auto_crm_general_error(self, conversation_service):
        """Test handling general error for Auto-CRM"""
        with patch("services.crm.auto_crm_service.get_auto_crm_service", side_effect=Exception("Error")):
            result = conversation_service._get_auto_crm()

            assert result is None
            assert conversation_service._auto_crm_service is False

    def test_get_auto_crm_cached(self, conversation_service):
        """Test that Auto-CRM service is cached"""
        mock_service = MagicMock()
        conversation_service._auto_crm_service = mock_service

        result = conversation_service._get_auto_crm()

        assert result == mock_service
