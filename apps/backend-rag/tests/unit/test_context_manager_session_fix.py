"""
Tests for context_manager session_id filtering fix

Tests that conversation history is correctly filtered by session_id
to prevent cross-session contamination.
"""

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from services.rag.agentic.context_manager import get_user_context


class TestContextManagerSessionFiltering:
    """Test session_id filtering in get_user_context"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def mock_memory_orchestrator(self):
        """Mock memory orchestrator"""
        orchestrator = MagicMock()
        orchestrator.get_user_context = AsyncMock(
            return_value=MagicMock(
                profile_facts=[],
                collective_facts=[],
                timeline_summary="",
                kg_entities=[],
                summary="",
                counters={},
            )
        )
        return orchestrator

    @pytest.mark.asyncio
    async def test_session_id_filtering_used_in_query(self, mock_db_pool, mock_memory_orchestrator):
        """Test: When session_id is provided, query filters by session_id"""
        session_id = str(uuid4())
        user_id = "test@example.com"

        # Mock database response
        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "email": user_id,
            "latest_conversation": json.dumps(
                {
                    "id": 123,
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                    ],
                }
            ),
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Call get_user_context with session_id
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orchestrator,
            session_id=session_id,
        )

        # Verify fetchrow was called with session_id parameter
        assert mock_conn.fetchrow.called
        call_args = mock_conn.fetchrow.call_args[0]
        # First arg is SQL query, then user_id, then session_id
        assert len(call_args) == 3  # SQL query, user_id, session_id
        assert call_args[1] == user_id
        assert call_args[2] == session_id
        # Verify SQL contains session_id filter
        assert "$2" in call_args[0]  # Session_id placeholder

        # Verify history was extracted
        assert len(result["history"]) == 2

    @pytest.mark.asyncio
    async def test_no_session_id_uses_latest_conversation(
        self, mock_db_pool, mock_memory_orchestrator
    ):
        """Test: When session_id is None, uses latest conversation"""
        user_id = "test@example.com"

        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "email": user_id,
            "latest_conversation": json.dumps(
                {
                    "id": 456,
                    "messages": [
                        {"role": "user", "content": "Test"},
                        {"role": "assistant", "content": "Response"},
                    ],
                }
            ),
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Call without session_id
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orchestrator,
            session_id=None,
        )

        # Verify fetchrow was called with only user_id (no session_id)
        assert mock_conn.fetchrow.called
        call_args = mock_conn.fetchrow.call_args[0]
        # First arg is SQL query, then user_id
        assert len(call_args) == 2  # SQL query, user_id
        assert call_args[1] == user_id
        # Verify SQL does NOT contain session_id filter
        assert "$2" not in call_args[0]  # No session_id placeholder

        assert len(result["history"]) == 2

    @pytest.mark.asyncio
    async def test_empty_history_still_loads_memory_facts(self, mock_db_pool, mock_memory_orchestrator):
        """Test: Memory facts are ALWAYS loaded, even on first query (for user recognition)

        FIX USER RECOGNITION BUG: The previous logic skipped facts on first query
        to "avoid hallucination", but this prevented user recognition completely.
        Now we ALWAYS load memory facts.
        """
        session_id = str(uuid4())
        user_id = "test@example.com"

        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "email": user_id,
            "latest_conversation": None,  # No conversation history
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Call get_user_context
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orchestrator,
            session_id=session_id,
        )

        # Verify memory orchestrator WAS called (always load for user recognition)
        assert mock_memory_orchestrator.get_user_context.called

        # History should be empty (no conversation), but facts loaded from orchestrator
        assert result["history"] == []

    @pytest.mark.asyncio
    async def test_non_empty_history_loads_memory_facts(
        self, mock_db_pool, mock_memory_orchestrator
    ):
        """Test: Non-empty history loads memory facts"""
        session_id = str(uuid4())
        user_id = "test@example.com"

        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "email": user_id,
            "latest_conversation": json.dumps(
                {
                    "id": 789,
                    "messages": [
                        {"role": "user", "content": "Previous message"},
                        {"role": "assistant", "content": "Previous response"},
                    ],
                }
            ),
        }

        # Mock memory orchestrator to return facts
        mock_memory_context = MagicMock()
        mock_memory_context.profile_facts = ["User likes blue", "User is from Milan"]
        mock_memory_context.collective_facts = []
        mock_memory_context.timeline_summary = ""
        mock_memory_context.kg_entities = []
        mock_memory_context.summary = ""
        mock_memory_context.counters = {}
        mock_memory_orchestrator.get_user_context = AsyncMock(return_value=mock_memory_context)

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Call get_user_context
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orchestrator,
            session_id=session_id,
        )

        # Verify memory orchestrator WAS called (not first query)
        assert mock_memory_orchestrator.get_user_context.called

        # Verify facts were loaded
        assert len(result["facts"]) == 2
        assert "User likes blue" in result["facts"]
        assert result["history"] == [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ]

    @pytest.mark.asyncio
    async def test_anonymous_user_returns_empty_context(
        self, mock_db_pool, mock_memory_orchestrator
    ):
        """Test: Anonymous user returns empty context"""
        result = await get_user_context(
            db_pool=mock_db_pool,
            user_id="anonymous",
            memory_orchestrator=mock_memory_orchestrator,
            session_id=None,
        )

        assert result["profile"] is None
        assert result["history"] == []
        assert result["facts"] == []

        # Verify DB was not queried
        assert not mock_db_pool.acquire.called
