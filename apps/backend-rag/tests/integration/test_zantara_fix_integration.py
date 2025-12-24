"""
Integration tests for Zantara context confusion fixes

Tests end-to-end behavior:
1. Session isolation (no cross-contamination)
2. Greetings skip RAG
3. Memory hallucination prevention
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from services.rag.agentic import AgenticRAGOrchestrator
from services.rag.agentic.context_manager import get_user_context


class TestZantaraFixIntegration:
    """Integration tests for all fixes"""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool"""
        pool = MagicMock()
        conn = AsyncMock()
        pool.acquire.return_value.__aenter__.return_value = conn
        return pool

    @pytest.fixture
    def mock_search_service(self):
        """Mock search service"""
        service = MagicMock()
        service.search = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_tools(self):
        """Mock tools list"""
        return []

    @pytest.fixture
    def orchestrator(self, mock_tools, mock_db_pool, mock_search_service):
        """Create orchestrator with mocks"""
        return AgenticRAGOrchestrator(tools=mock_tools, db_pool=mock_db_pool, semantic_cache=None)

    @pytest.mark.asyncio
    async def test_greeting_skips_rag(self, orchestrator, mock_db_pool):
        """Test: Greeting query skips RAG and returns direct response"""
        # Mock prompt builder
        with patch.object(orchestrator.prompt_builder, "check_greetings") as mock_check:
            mock_check.return_value = "Ciao! Come posso aiutarti oggi?"

            result = await orchestrator.process_query(
                query="ciao", user_id="test@example.com", session_id=str(uuid4())
            )

            # Verify greeting was detected
            assert mock_check.called

            # Verify response is direct (no RAG)
            assert result["answer"] == "Ciao! Come posso aiutarti oggi?"
            assert result["route_used"] == "greeting-pattern"
            assert result["tools_called"] == 0
            assert len(result["sources"]) == 0

    @pytest.mark.asyncio
    async def test_session_isolation(self, mock_db_pool):
        """Test: Different sessions get different conversation histories"""
        session_1 = str(uuid4())
        session_2 = str(uuid4())
        user_id = "test@example.com"

        # Mock different conversations for different sessions
        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value

        def mock_fetchrow(*args):
            session_id = args[1] if len(args) > 1 else None

            if session_id == session_1:
                return {
                    "id": uuid4(),
                    "name": "Test User",
                    "role": "user",
                    "department": None,
                    "preferred_language": "en",
                    "notes": None,
                    "latest_conversation": json.dumps(
                        {
                            "id": 1,
                            "messages": [
                                {"role": "user", "content": "Session 1 message"},
                                {"role": "assistant", "content": "Session 1 response"},
                            ],
                        }
                    ),
                }
            elif session_id == session_2:
                return {
                    "id": uuid4(),
                    "name": "Test User",
                    "role": "user",
                    "department": None,
                    "preferred_language": "en",
                    "notes": None,
                    "latest_conversation": json.dumps(
                        {
                            "id": 2,
                            "messages": [
                                {"role": "user", "content": "Session 2 message"},
                                {"role": "assistant", "content": "Session 2 response"},
                            ],
                        }
                    ),
                }
            return None

        mock_conn.fetchrow = AsyncMock(side_effect=mock_fetchrow)

        # Get context for session 1
        context_1 = await get_user_context(
            db_pool=mock_db_pool, user_id=user_id, memory_orchestrator=None, session_id=session_1
        )

        # Get context for session 2
        context_2 = await get_user_context(
            db_pool=mock_db_pool, user_id=user_id, memory_orchestrator=None, session_id=session_2
        )

        # Verify sessions are isolated
        assert len(context_1["history"]) == 2
        assert len(context_2["history"]) == 2
        assert context_1["history"][0]["content"] == "Session 1 message"
        assert context_2["history"][0]["content"] == "Session 2 message"
        assert context_1["history"] != context_2["history"]

    @pytest.mark.asyncio
    async def test_first_query_no_memory_facts(self, mock_db_pool):
        """Test: First query in session doesn't load memory facts"""
        session_id = str(uuid4())
        user_id = "test@example.com"

        mock_memory_orch = MagicMock()
        mock_memory_orch.get_user_context = AsyncMock()

        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "latest_conversation": None,  # First query - no history
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Get context for first query
        context = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orch,
            session_id=session_id,
        )

        # Verify memory orchestrator was NOT called
        assert not mock_memory_orch.get_user_context.called

        # Verify facts are empty
        assert context["facts"] == []
        assert context["history"] == []

    @pytest.mark.asyncio
    async def test_second_query_loads_memory_facts(self, mock_db_pool):
        """Test: Second query in session loads memory facts"""
        session_id = str(uuid4())
        user_id = "test@example.com"

        mock_memory_context = MagicMock()
        mock_memory_context.profile_facts = ["User prefers Italian", "User is entrepreneur"]
        mock_memory_context.collective_facts = []
        mock_memory_context.timeline_summary = ""
        mock_memory_context.kg_entities = []
        mock_memory_context.summary = ""
        mock_memory_context.counters = {}

        mock_memory_orch = MagicMock()
        mock_memory_orch.get_user_context = AsyncMock(return_value=mock_memory_context)

        mock_row = {
            "id": uuid4(),
            "name": "Test User",
            "role": "user",
            "department": None,
            "preferred_language": "en",
            "notes": None,
            "latest_conversation": json.dumps(
                {
                    "id": 123,
                    "messages": [
                        {"role": "user", "content": "Previous message"},
                        {"role": "assistant", "content": "Previous response"},
                    ],
                }
            ),
        }

        mock_conn = mock_db_pool.acquire.return_value.__aenter__.return_value
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)

        # Get context for second query
        context = await get_user_context(
            db_pool=mock_db_pool,
            user_id=user_id,
            memory_orchestrator=mock_memory_orch,
            session_id=session_id,
        )

        # Verify memory orchestrator WAS called
        assert mock_memory_orch.get_user_context.called

        # Verify facts were loaded
        assert len(context["facts"]) == 2
        assert "User prefers Italian" in context["facts"]

    @pytest.mark.asyncio
    async def test_greeting_in_stream(self, orchestrator, mock_db_pool):
        """Test: Greeting in stream mode also skips RAG"""
        with patch.object(orchestrator.prompt_builder, "check_greetings") as mock_check:
            mock_check.return_value = "Hello! How can I help you today?"

            events = []
            async for event in orchestrator.stream_query(
                query="hello", user_id="test@example.com", session_id=str(uuid4())
            ):
                events.append(event)

            # Verify greeting was detected
            assert mock_check.called

            # Verify we got greeting response
            token_events = [e for e in events if e.get("type") == "token"]
            assert len(token_events) > 0

            # Verify no tool calls
            tool_events = [e for e in events if e.get("type") == "tool_start"]
            assert len(tool_events) == 0
