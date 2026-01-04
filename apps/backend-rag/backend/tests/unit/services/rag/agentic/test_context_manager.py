"""
Comprehensive test coverage for context_manager.py
Target: Maximum coverage for all code paths
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from services.memory import MemoryContext
from services.rag.agentic.context_manager import get_user_context


@pytest.fixture
def mock_connection():
    """Mock database connection"""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock()
    return conn


@pytest.fixture
def mock_db_pool(mock_connection):
    """Mock database connection pool"""
    pool = AsyncMock()
    # Setup acquire as async context manager
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_acquire.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=mock_acquire)
    return pool


@pytest.fixture
def mock_memory_orchestrator():
    """Mock MemoryOrchestrator"""
    orchestrator = MagicMock()
    orchestrator.get_user_context = AsyncMock(
        return_value=MemoryContext(
            user_id="test@example.com",
            profile_facts=["Fact 1", "Fact 2"],
            collective_facts=["Collective fact 1"],
            timeline_summary="Timeline summary",
            kg_entities=[{"type": "person", "name": "John"}],
            summary="Conversation summary",
            counters={"conversations": 5, "searches": 10, "tasks": 2},
            has_data=True,
        )
    )
    return orchestrator


@pytest.fixture
def mock_memory_cache():
    """Mock memory cache"""
    cache = MagicMock()
    cache.get_entities = MagicMock(return_value={"name": "John", "city": "Bali"})
    return cache


class TestGetUserContext:
    """Test suite for get_user_context function"""

    @pytest.mark.asyncio
    async def test_anonymous_user_early_exit(self):
        """Test early exit for anonymous user"""
        result = await get_user_context(db_pool=None, user_id="anonymous", memory_orchestrator=None)
        assert result == {
            "profile": None,
            "history": [],
            "facts": [],
            "collective_facts": [],
            "entities": {},
        }

    @pytest.mark.asyncio
    async def test_none_db_pool_early_exit(self):
        """Test early exit when db_pool is None"""
        result = await get_user_context(
            db_pool=None, user_id="test@example.com", memory_orchestrator=None
        )
        assert result == {
            "profile": None,
            "history": [],
            "facts": [],
            "collective_facts": [],
            "entities": {},
        }

    @pytest.mark.asyncio
    async def test_none_user_id_early_exit(self):
        """Test early exit when user_id is None"""
        result = await get_user_context(db_pool=MagicMock(), user_id=None, memory_orchestrator=None)
        assert result == {
            "profile": None,
            "history": [],
            "facts": [],
            "collective_facts": [],
            "entities": {},
        }

    @pytest.mark.asyncio
    async def test_empty_user_id_early_exit(self):
        """Test early exit when user_id is empty string"""
        result = await get_user_context(db_pool=MagicMock(), user_id="", memory_orchestrator=None)
        assert result == {
            "profile": None,
            "history": [],
            "facts": [],
            "collective_facts": [],
            "entities": {},
        }

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_cache_lookup_keyerror(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test memory cache lookup with KeyError"""
        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(side_effect=KeyError("not found"))
        mock_get_cache.return_value = mock_cache

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )
        assert result["entities"] == {}

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_cache_lookup_valueerror(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test memory cache lookup with ValueError"""
        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(side_effect=ValueError("invalid"))
        mock_get_cache.return_value = mock_cache

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )
        assert result["entities"] == {}

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_cache_lookup_runtimeerror(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test memory cache lookup with RuntimeError"""
        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(side_effect=RuntimeError("runtime error"))
        mock_get_cache.return_value = mock_cache

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )
        assert result["entities"] == {}

    @pytest.mark.asyncio
    async def test_user_not_found_no_session_id(self, mock_db_pool, mock_connection):
        """Test when user is not found in database (no session_id)"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="notfound@example.com", memory_orchestrator=None
        )
        assert result["profile"] is None
        assert result["history"] == []

    @pytest.mark.asyncio
    async def test_user_not_found_with_session_id(self, mock_db_pool, mock_connection):
        """Test when user is not found in database (with session_id)"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="notfound@example.com",
            memory_orchestrator=None,
            session_id="session123",
        )
        assert result["profile"] is None
        assert result["history"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_user_found_with_profile_no_history(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test user found with profile but no conversation history"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": "Sales",
            "preferred_language": "it",
            "notes": "Test notes",
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["profile"]["id"] == "user123"
        assert result["profile"]["name"] == "Test User"
        assert result["profile"]["role"] == "Entrepreneur"
        assert result["profile"]["department"] == "Sales"
        assert result["profile"]["preferred_language"] == "it"
        assert result["profile"]["notes"] == "Test notes"
        assert result["profile"]["email"] == "test@example.com"
        assert result["history"] == []
        assert result["entities"] == {}

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_user_found_with_profile_and_history_json_string(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test user found with profile and history (JSON string format)"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        conversation_json = json.dumps({"id": "conv123", "messages": json.dumps(messages)})

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": conversation_json,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={"name": "John"})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["profile"]["id"] == "user123"
        assert len(result["history"]) == 2
        assert result["history"][0]["role"] == "user"
        assert result["entities"] == {"name": "John"}

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_user_found_with_profile_and_history_dict_format(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test user found with profile and history (dict format)"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        conversation_dict = {"id": "conv123", "messages": messages}

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": conversation_dict,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["profile"]["id"] == "user123"
        assert len(result["history"]) == 2
        assert result["history"][0]["role"] == "user"

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_history_last_20_messages_limit(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test that only last 20 messages are returned"""
        # Create 25 messages
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(25)]

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": {"id": "conv123", "messages": messages},
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert len(result["history"]) == 20
        assert result["history"][0]["content"] == "Message 5"  # Last 20 messages

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_history_empty_messages_list(self, mock_get_cache, mock_db_pool, mock_connection):
        """Test with empty messages list"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": {"id": "conv123", "messages": []},
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["history"] == []

    @pytest.mark.asyncio
    async def test_with_session_id_query(self, mock_db_pool, mock_connection):
        """Test query with session_id parameter"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=None,
            session_id="session123",
        )

        # Verify session_id was passed to fetchrow
        mock_connection.fetchrow.assert_called_once()
        call_args = mock_connection.fetchrow.call_args[0]
        assert "session123" in call_args

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_with_memory_orchestrator_success(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test with memory orchestrator - successful retrieval"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
            query="Test query",
        )

        assert len(result["facts"]) == 2
        assert result["facts"][0] == "Fact 1"
        assert len(result["collective_facts"]) == 1
        assert result["timeline_summary"] == "Timeline summary"
        assert len(result["kg_entities"]) == 1
        assert result["summary"] == "Conversation summary"
        assert result["counters"]["conversations"] == 5
        assert "memory_context" in result
        mock_memory_orchestrator.get_user_context.assert_called_once_with(
            "test@example.com", query="Test query"
        )

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_with_memory_orchestrator_no_query(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test with memory orchestrator but no query parameter"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        assert len(result["facts"]) == 2
        mock_memory_orchestrator.get_user_context.assert_called_once_with(
            "test@example.com", query=None
        )

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_without_memory_orchestrator(self, mock_get_cache, mock_db_pool, mock_connection):
        """Test without memory orchestrator - should return empty facts"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["facts"] == []
        assert result["collective_facts"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_orchestrator_postgres_error(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test memory orchestrator raises PostgresError"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        mock_memory_orchestrator.get_user_context.side_effect = asyncpg.PostgresError("DB error")

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        # Should gracefully degrade to empty facts
        assert result["facts"] == []
        assert result["collective_facts"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_orchestrator_value_error(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test memory orchestrator raises ValueError"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        mock_memory_orchestrator.get_user_context.side_effect = ValueError("Invalid value")

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        assert result["facts"] == []
        assert result["collective_facts"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_orchestrator_runtime_error(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test memory orchestrator raises RuntimeError"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        mock_memory_orchestrator.get_user_context.side_effect = RuntimeError("Runtime error")

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        assert result["facts"] == []
        assert result["collective_facts"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_memory_orchestrator_key_error(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test memory orchestrator raises KeyError"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        mock_memory_orchestrator.get_user_context.side_effect = KeyError("missing key")

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        assert result["facts"] == []
        assert result["collective_facts"] == []

    @pytest.mark.asyncio
    async def test_database_postgres_error(self, mock_db_pool, mock_connection):
        """Test database PostgresError handling"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.side_effect = asyncpg.PostgresError("Database error")

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        # Should return empty context on error
        assert result["profile"] is None
        assert result["history"] == []

    @pytest.mark.asyncio
    async def test_database_interface_error(self, mock_db_pool, mock_connection):
        """Test database InterfaceError handling"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.side_effect = asyncpg.InterfaceError("Interface error")

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["profile"] is None
        assert result["history"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_json_decode_error_in_conversation(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test JSONDecodeError when parsing conversation"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": "invalid json{",
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        # Should handle error gracefully
        assert result["profile"] is not None
        # History should be empty due to JSON error
        assert result["history"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_key_error_in_conversation_parsing(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test KeyError when accessing conversation fields"""
        # Create a conversation dict without 'messages' key
        conversation_dict = {"id": "conv123"}  # Missing 'messages'

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": conversation_dict,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["profile"] is not None
        assert result["history"] == []

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_user_id_updated_from_profile(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test that user_id is updated from profile.id for memory orchestrator"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "uuid-123-456",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        # Call with email, but should use original_user_id for memory
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
        )

        # Memory orchestrator should be called with original email, not UUID
        mock_memory_orchestrator.get_user_context.assert_called_once_with(
            "test@example.com", query=None
        )

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_deep_think_mode_parameter(self, mock_get_cache, mock_db_pool, mock_connection):
        """Test deep_think_mode parameter (should be accepted but not used directly)"""
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": None,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=None,
            deep_think_mode=True,
        )

        # deep_think_mode is accepted but not used in current implementation
        assert result["profile"] is not None

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_messages_as_json_string(self, mock_get_cache, mock_db_pool, mock_connection):
        """Test messages field as JSON string (nested JSON)"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        conversation_dict = {"id": "conv123", "messages": json.dumps(messages)}

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": conversation_dict,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert len(result["history"]) == 2
        assert result["history"][0]["role"] == "user"

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_entities_from_cache_with_conversation_id(
        self, mock_get_cache, mock_db_pool, mock_connection
    ):
        """Test entities extraction from cache using conversation_id"""
        messages = [{"role": "user", "content": "Hello"}]
        conversation_dict = {"id": "conv123", "messages": messages}

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": None,
            "preferred_language": None,
            "notes": None,
            "email": "test@example.com",
            "latest_conversation": conversation_dict,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={"name": "John", "city": "Bali"})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool, user_id="test@example.com", memory_orchestrator=None
        )

        assert result["entities"] == {"name": "John", "city": "Bali"}
        mock_cache.get_entities.assert_called_once_with("conv123")

    @pytest.mark.asyncio
    @patch("services.rag.agentic.context_manager.get_memory_cache")
    async def test_full_integration_all_features(
        self, mock_get_cache, mock_db_pool, mock_connection, mock_memory_orchestrator
    ):
        """Test full integration with all features enabled"""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        conversation_dict = {"id": "conv123", "messages": messages}

        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {
            "id": "user123",
            "name": "Test User",
            "role": "Entrepreneur",
            "department": "Sales",
            "preferred_language": "it",
            "notes": "Important client",
            "email": "test@example.com",
            "latest_conversation": conversation_dict,
        }

        mock_cache = MagicMock()
        mock_cache.get_entities = MagicMock(return_value={"name": "John"})
        mock_get_cache.return_value = mock_cache

        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="test@example.com",
            memory_orchestrator=mock_memory_orchestrator,
            query="What is PT PMA?",
            session_id="session123",
            deep_think_mode=True,
        )

        # Verify all components
        assert result["profile"]["name"] == "Test User"
        assert len(result["history"]) == 2
        assert len(result["facts"]) == 2
        assert len(result["collective_facts"]) == 1
        assert result["entities"] == {"name": "John"}
        assert "memory_context" in result
        assert result["timeline_summary"] == "Timeline summary"
        assert len(result["kg_entities"]) == 1
