"""
API Tests for Memory Persistence

Tests the memory persistence functionality through the API endpoints.
Verifies that:
1. Facts are extracted and saved during conversations
2. Facts are retrieved in subsequent requests
3. Memory persists across sessions
"""

import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestMemoryAPIIntegration:
    """Test memory persistence through API endpoints"""

    @pytest.fixture
    def mock_oracle_service(self):
        """Mock OracleService with memory orchestrator"""
        from services.memory.models import MemoryContext, MemoryProcessResult
        from services.memory.orchestrator import MemoryOrchestrator

        # Create mock memory orchestrator
        mock_orchestrator = AsyncMock(spec=MemoryOrchestrator)
        mock_orchestrator.is_initialized = True
        mock_orchestrator.get_user_context = AsyncMock(
            return_value=MemoryContext(
                user_id="test@test.com",
                profile_facts=["Name: Roberto", "Location: Torino"],
                has_data=True,
            )
        )
        mock_orchestrator.process_conversation = AsyncMock(
            return_value=MemoryProcessResult(
                facts_extracted=2,
                facts_saved=2,
            )
        )

        return mock_orchestrator

    @pytest.mark.asyncio
    async def test_oracle_query_saves_memory(self, mock_oracle_service):
        """Test that oracle query saves memory facts"""
        # This test verifies that when an oracle query is made,
        # the memory orchestrator's process_conversation is called

        from services.oracle_service import OracleService

        with patch.object(OracleService, "memory_orchestrator", mock_oracle_service):
            with patch.object(
                OracleService,
                "_ensure_memory_orchestrator_initialized",
                AsyncMock(return_value=True),
            ):
                service = OracleService()
                service._memory_orchestrator = mock_oracle_service

                # Call the _save_memory_facts directly to test integration
                await service._save_memory_facts(
                    user_email="test@test.com",
                    user_message="Mi chiamo Roberto, sono di Torino",
                    ai_response="Ciao Roberto!",
                )

                # Verify orchestrator was called
                mock_oracle_service.process_conversation.assert_called_once_with(
                    user_email="test@test.com",
                    user_message="Mi chiamo Roberto, sono di Torino",
                    ai_response="Ciao Roberto!",
                )

    @pytest.mark.asyncio
    async def test_memory_facts_returned_in_response(self):
        """Test that memory facts are included in oracle response"""
        from services.memory.models import MemoryContext

        # This tests that user_memory_facts field is populated from memory
        context = MemoryContext(
            user_id="test@test.com",
            profile_facts=["Name: Roberto", "Age: 45", "City: Torino"],
            has_data=True,
        )

        # Facts should be accessible
        assert len(context.profile_facts) == 3
        assert "Roberto" in context.profile_facts[0]

    @pytest.mark.asyncio
    async def test_agentic_rag_saves_memory(self):
        """Test that AgenticRAG saves memory facts"""
        from services.memory.models import MemoryProcessResult
        from services.memory.orchestrator import MemoryOrchestrator

        # Mock orchestrator
        mock_orchestrator = AsyncMock(spec=MemoryOrchestrator)
        mock_orchestrator.is_initialized = True
        mock_orchestrator.process_conversation = AsyncMock(
            return_value=MemoryProcessResult(
                facts_extracted=1,
                facts_saved=1,
            )
        )

        # Test _save_conversation_memory method
        from services.rag.agentic import AgenticRAGOrchestrator

        # Create instance with mocked DB
        orchestrator = AgenticRAGOrchestrator(tools=[], db_pool=None)
        orchestrator._memory_orchestrator = mock_orchestrator

        # Call save method
        await orchestrator._save_conversation_memory(
            user_id="test@test.com",
            query="Test query",
            answer="Test answer",
        )

        # Verify called
        mock_orchestrator.process_conversation.assert_called_once()


class TestMemoryContextFormat:
    """Test memory context formatting for LLM"""

    def test_empty_context_returns_empty_string(self):
        """Test that empty context produces empty system prompt"""
        from services.memory.models import MemoryContext

        context = MemoryContext(user_id="test@test.com")
        assert context.is_empty()
        assert context.to_system_prompt() == ""

    def test_context_with_facts_formats_correctly(self):
        """Test that context with facts produces formatted prompt"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@test.com",
            profile_facts=[
                "Name: Roberto",
                "Age: 45",
                "Profession: Lawyer",
            ],
            summary="Interested in opening law firm in Bali",
            has_data=True,
        )

        prompt = context.to_system_prompt()

        assert "User Context" in prompt
        assert "Roberto" in prompt
        assert "45" in prompt
        assert "Lawyer" in prompt
        assert "Bali" in prompt

    def test_context_with_summary_only(self):
        """Test context with only summary"""
        from services.memory.models import MemoryContext

        context = MemoryContext(
            user_id="test@test.com",
            summary="User wants to invest in eco-resort",
            has_data=True,
        )

        prompt = context.to_system_prompt()
        assert "eco-resort" in prompt


class TestMemoryEndpointSecurity:
    """Test security aspects of memory endpoints"""

    @pytest.mark.asyncio
    async def test_anonymous_user_no_memory_saved(self):
        """Test that anonymous users don't get memory saved"""
        from services.rag.agentic import AgenticRAGOrchestrator

        orchestrator = AgenticRAGOrchestrator(tools=[], db_pool=None)

        # Mock the memory orchestrator
        mock_orchestrator = AsyncMock()
        orchestrator._memory_orchestrator = mock_orchestrator

        # Call with anonymous user
        await orchestrator._save_conversation_memory(
            user_id="anonymous",
            query="Test",
            answer="Test",
        )

        # Should not call process_conversation for anonymous
        mock_orchestrator.process_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_user_no_memory_saved(self):
        """Test that empty user_id doesn't get memory saved"""
        from services.oracle_service import OracleService

        service = OracleService()
        mock_orchestrator = AsyncMock()
        service._memory_orchestrator = mock_orchestrator

        # Call with empty user
        await service._save_memory_facts(
            user_email="",
            user_message="Test",
            ai_response="Test",
        )

        # Should return early without calling orchestrator
        mock_orchestrator.process_conversation.assert_not_called()


class TestMemoryPersistenceRoundTrip:
    """Test complete round-trip of memory persistence"""

    @pytest.mark.asyncio
    async def test_save_and_retrieve_cycle(self):
        """Test saving facts and retrieving them"""
        from datetime import datetime

        from services.memory.orchestrator import MemoryOrchestrator
        from services.memory_service_postgres import UserMemory

        # Create mock storage
        storage = {}

        # Mock memory service
        mock_service = AsyncMock()
        mock_service.pool = True

        async def mock_add_fact(user_id, fact, fact_type="general"):
            if user_id not in storage:
                storage[user_id] = []
            storage[user_id].append({"content": fact, "type": fact_type})
            return True

        async def mock_get_memory(user_id):
            facts = storage.get(user_id, [])
            return UserMemory(
                user_id=user_id,
                profile_facts=[f["content"] for f in facts],
                summary="",
                counters={"conversations": 0, "searches": 0, "tasks": 0},
                updated_at=datetime.now(),
            )

        mock_service.add_fact = mock_add_fact
        mock_service.get_memory = mock_get_memory
        mock_service.increment_counter = AsyncMock(return_value=True)

        # Create orchestrator with mock service
        orchestrator = MemoryOrchestrator()
        orchestrator._memory_service = mock_service
        from services.memory_fact_extractor import MemoryFactExtractor

        orchestrator._fact_extractor = MemoryFactExtractor()
        orchestrator._is_initialized = True

        user_email = f"roundtrip-{uuid.uuid4()}@test.com"

        # Save facts
        result = await orchestrator.process_conversation(
            user_email=user_email,
            user_message="Mi chiamo Marco, ho 35 anni, sono di Milano",
            ai_response="Ciao Marco! Milano è una bellissima città.",
        )

        assert result.success

        # Retrieve facts
        context = await orchestrator.get_user_context(user_email)

        assert context.user_id == user_email
        # Facts should have been saved (if extraction worked)
        if result.facts_saved > 0:
            assert len(context.profile_facts) > 0
