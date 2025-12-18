"""
Unit Tests for MemoryOrchestrator

Following TDD: These tests are written BEFORE the implementation.
The orchestrator should provide a unified interface for:
1. Getting user context (reading memory)
2. Processing conversations (extracting and saving facts)
3. Managing memory lifecycle (init, cleanup)

Tests cover:
- Context retrieval for known and unknown users
- Fact extraction from conversations
- Error handling and graceful degradation
- Statistics and monitoring
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Models are already implemented
from services.memory.models import (
    FactType,
    MemoryContext,
    MemoryFact,
    MemoryProcessResult,
    MemoryStats,
)


class TestMemoryModels:
    """Test the Pydantic models"""

    def test_memory_fact_creation(self):
        """Test creating a MemoryFact"""
        fact = MemoryFact(
            content="User's name is Roberto",
            fact_type=FactType.IDENTITY,
            confidence=0.95,
        )
        assert fact.content == "User's name is Roberto"
        assert fact.fact_type == "identity"
        assert fact.confidence == 0.95
        assert fact.source == "user"  # default

    def test_memory_fact_validation(self):
        """Test MemoryFact validation"""
        # Empty content should fail
        with pytest.raises(ValueError):
            MemoryFact(content="")

        # Confidence out of range should fail
        with pytest.raises(ValueError):
            MemoryFact(content="Test", confidence=1.5)

    def test_memory_context_empty(self):
        """Test empty MemoryContext"""
        ctx = MemoryContext(user_id="test@test.com")
        assert ctx.is_empty()
        assert ctx.to_system_prompt() == ""

    def test_memory_context_with_facts(self):
        """Test MemoryContext with facts"""
        ctx = MemoryContext(
            user_id="test@test.com",
            profile_facts=["Name: Roberto", "Age: 45"],
            has_data=True,
        )
        assert not ctx.is_empty()
        prompt = ctx.to_system_prompt()
        assert "Roberto" in prompt
        assert "45" in prompt
        assert "User Context" in prompt

    def test_memory_process_result_success(self):
        """Test successful processing result"""
        result = MemoryProcessResult(
            facts_extracted=3,
            facts_saved=3,
        )
        assert result.success
        assert result.facts_extracted == 3

    def test_memory_process_result_error(self):
        """Test error processing result"""
        result = MemoryProcessResult(error="Database connection failed")
        assert not result.success


class TestMemoryOrchestratorInit:
    """Test MemoryOrchestrator initialization"""

    @pytest.mark.asyncio
    async def test_initialize_with_pool(self):
        """Test initialization with existing connection pool"""
        from services.memory.orchestrator import MemoryOrchestrator

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        await orchestrator.initialize()

        assert orchestrator.is_initialized
        assert orchestrator.db_pool is mock_pool

    @pytest.mark.asyncio
    async def test_initialize_creates_pool_if_needed(self):
        """Test that initialize creates pool if not provided"""
        from services.memory.orchestrator import MemoryOrchestrator

        with patch("services.memory.orchestrator.asyncpg.create_pool") as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool

            orchestrator = MemoryOrchestrator()
            await orchestrator.initialize()

            # Should have created a pool
            assert orchestrator.is_initialized

    @pytest.mark.asyncio
    async def test_close_cleans_up_resources(self):
        """Test that close properly cleans up"""
        from services.memory.orchestrator import MemoryOrchestrator

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        await orchestrator.initialize()
        await orchestrator.close()

        # Pool.close may be called multiple times (memory service + orchestrator)
        assert mock_pool.close.called


class TestMemoryOrchestratorGetContext:
    """Test getting user context from memory"""

    @pytest.fixture
    def mock_memory_service(self):
        """Create a mock memory service"""
        service = AsyncMock()
        service.get_memory = AsyncMock()
        service.pool = True  # Simulate connected
        return service

    @pytest.fixture
    def orchestrator_with_mock(self, mock_memory_service):
        """Create orchestrator with mocked services"""
        from services.memory.orchestrator import MemoryOrchestrator

        orchestrator = MemoryOrchestrator()
        orchestrator._memory_service = mock_memory_service
        orchestrator._is_initialized = True
        return orchestrator

    @pytest.mark.asyncio
    async def test_get_context_for_new_user(self, orchestrator_with_mock, mock_memory_service):
        """Test getting context for a user with no memory"""
        from services.memory_service_postgres import UserMemory

        # Mock empty memory
        mock_memory_service.get_memory.return_value = UserMemory(
            user_id="new@test.com",
            profile_facts=[],
            summary="",
            counters={"conversations": 0, "searches": 0, "tasks": 0},
            updated_at=datetime.now(),
        )

        context = await orchestrator_with_mock.get_user_context("new@test.com")

        assert isinstance(context, MemoryContext)
        assert context.user_id == "new@test.com"
        assert context.is_empty() or not context.profile_facts

    @pytest.mark.asyncio
    async def test_get_context_for_known_user(self, orchestrator_with_mock, mock_memory_service):
        """Test getting context for a user with existing memory"""
        from services.memory_service_postgres import UserMemory

        # Mock user with facts
        mock_memory_service.get_memory.return_value = UserMemory(
            user_id="roberto@test.com",
            profile_facts=[
                "Name: Roberto",
                "Age: 45",
                "Location: Torino",
                "Profession: Lawyer",
            ],
            summary="User interested in opening law firm in Bali",
            counters={"conversations": 5, "searches": 3, "tasks": 1},
            updated_at=datetime.now(),
        )

        context = await orchestrator_with_mock.get_user_context("roberto@test.com")

        assert isinstance(context, MemoryContext)
        assert context.user_id == "roberto@test.com"
        assert not context.is_empty()
        assert len(context.profile_facts) == 4
        assert "Roberto" in context.profile_facts[0]
        assert context.counters["conversations"] == 5

    @pytest.mark.asyncio
    async def test_get_context_handles_db_error(self, orchestrator_with_mock, mock_memory_service):
        """Test graceful degradation when database fails"""
        mock_memory_service.get_memory.side_effect = Exception("Database error")

        context = await orchestrator_with_mock.get_user_context("error@test.com")

        # Should return empty context, not raise
        assert isinstance(context, MemoryContext)
        assert context.user_id == "error@test.com"
        assert context.is_empty()

    @pytest.mark.asyncio
    async def test_get_context_before_init_fails(self):
        """Test that getting context before init raises error"""
        from services.memory.orchestrator import MemoryOrchestrator

        orchestrator = MemoryOrchestrator()
        # Not initialized

        with pytest.raises(RuntimeError, match="not initialized"):
            await orchestrator.get_user_context("test@test.com")


class TestMemoryOrchestratorProcessConversation:
    """Test processing conversations for fact extraction"""

    @pytest.fixture
    def mock_services(self):
        """Create mock services"""
        memory_service = AsyncMock()
        memory_service.add_fact = AsyncMock(return_value=True)
        memory_service.pool = True

        fact_extractor = MagicMock()
        fact_extractor.extract_facts_from_conversation = MagicMock(return_value=[])

        return memory_service, fact_extractor

    @pytest.fixture
    def orchestrator_with_mocks(self, mock_services):
        """Create orchestrator with mocked services"""
        from services.memory.orchestrator import MemoryOrchestrator

        memory_service, fact_extractor = mock_services

        orchestrator = MemoryOrchestrator()
        orchestrator._memory_service = memory_service
        orchestrator._fact_extractor = fact_extractor
        orchestrator._is_initialized = True
        return orchestrator

    @pytest.mark.asyncio
    async def test_process_conversation_extracts_facts(
        self, orchestrator_with_mocks, mock_services
    ):
        """Test that conversation is processed and facts extracted"""
        memory_service, fact_extractor = mock_services

        # Mock fact extraction
        fact_extractor.extract_facts_from_conversation.return_value = [
            {"content": "Name: Roberto", "type": "identity", "confidence": 0.95},
            {"content": "Location: Torino", "type": "location", "confidence": 0.9},
        ]

        result = await orchestrator_with_mocks.process_conversation(
            user_email="roberto@test.com",
            user_message="Mi chiamo Roberto, sono di Torino",
            ai_response="Ciao Roberto! Piacere di conoscerti.",
        )

        assert isinstance(result, MemoryProcessResult)
        assert result.success
        assert result.facts_extracted == 2
        # Verify add_fact was called
        assert memory_service.add_fact.call_count == 2

    @pytest.mark.asyncio
    async def test_process_conversation_no_facts(self, orchestrator_with_mocks, mock_services):
        """Test processing when no facts are extracted"""
        memory_service, fact_extractor = mock_services

        # Mock no facts extracted
        fact_extractor.extract_facts_from_conversation.return_value = []

        result = await orchestrator_with_mocks.process_conversation(
            user_email="test@test.com",
            user_message="Ciao!",
            ai_response="Ciao! Come posso aiutarti?",
        )

        assert result.success
        assert result.facts_extracted == 0
        assert result.facts_saved == 0

    @pytest.mark.asyncio
    async def test_process_conversation_partial_save_failure(
        self, orchestrator_with_mocks, mock_services
    ):
        """Test when some facts fail to save"""
        memory_service, fact_extractor = mock_services

        # Mock 3 facts extracted
        fact_extractor.extract_facts_from_conversation.return_value = [
            {"content": "Fact 1", "type": "general", "confidence": 0.8},
            {"content": "Fact 2", "type": "general", "confidence": 0.8},
            {"content": "Fact 3", "type": "general", "confidence": 0.8},
        ]

        # Mock partial save failure (2 succeed, 1 fails)
        memory_service.add_fact.side_effect = [True, False, True]

        result = await orchestrator_with_mocks.process_conversation(
            user_email="test@test.com",
            user_message="Test message",
            ai_response="Test response",
        )

        assert result.success  # Overall still success
        assert result.facts_extracted == 3
        assert result.facts_saved == 2  # Only 2 saved

    @pytest.mark.asyncio
    async def test_process_conversation_skips_empty_email(self, orchestrator_with_mocks):
        """Test that empty email is handled gracefully"""
        result = await orchestrator_with_mocks.process_conversation(
            user_email="",
            user_message="Test",
            ai_response="Test",
        )

        assert result.success
        assert result.facts_extracted == 0
        assert result.facts_saved == 0

    @pytest.mark.asyncio
    async def test_process_conversation_handles_extractor_error(
        self, orchestrator_with_mocks, mock_services
    ):
        """Test graceful handling of extractor errors"""
        _, fact_extractor = mock_services

        fact_extractor.extract_facts_from_conversation.side_effect = Exception("Extraction failed")

        result = await orchestrator_with_mocks.process_conversation(
            user_email="test@test.com",
            user_message="Test",
            ai_response="Test",
        )

        assert not result.success
        assert "Extraction failed" in result.error


class TestMemoryOrchestratorStats:
    """Test memory statistics"""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting memory system stats"""
        from services.memory.orchestrator import MemoryOrchestrator

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)

        # Mock memory service stats
        orchestrator._memory_service = AsyncMock()
        orchestrator._memory_service.get_stats = AsyncMock(
            return_value={
                "cached_users": 10,
                "postgres_enabled": True,
                "total_users": 100,
                "total_facts": 500,
                "total_conversations": 1000,
            }
        )
        orchestrator._is_initialized = True

        stats = await orchestrator.get_stats()

        assert isinstance(stats, MemoryStats)
        assert stats.cached_users == 10
        assert stats.postgres_enabled is True
        assert stats.total_users == 100


class TestMemoryOrchestratorIntegration:
    """Integration-style tests (still using mocks but testing full flow)"""

    @pytest.mark.asyncio
    async def test_full_memory_lifecycle(self):
        """Test complete memory lifecycle: init -> save -> retrieve -> close"""
        from services.memory.orchestrator import MemoryOrchestrator
        from services.memory_service_postgres import UserMemory

        # Create orchestrator with mocked pool
        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)

        # Mock memory service
        mock_memory_service = AsyncMock()
        mock_memory_service.pool = mock_pool
        mock_memory_service.connect = AsyncMock()
        mock_memory_service.add_fact = AsyncMock(return_value=True)
        mock_memory_service.get_memory = AsyncMock(
            return_value=UserMemory(
                user_id="test@test.com",
                profile_facts=["Name: Test User"],
                summary="",
                counters={"conversations": 1, "searches": 0, "tasks": 0},
                updated_at=datetime.now(),
            )
        )

        # Mock fact extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_facts_from_conversation = MagicMock(
            return_value=[
                {"content": "Name: Test User", "type": "identity", "confidence": 0.9},
            ]
        )

        orchestrator._memory_service = mock_memory_service
        orchestrator._fact_extractor = mock_extractor

        # 1. Initialize
        await orchestrator.initialize()
        assert orchestrator.is_initialized

        # 2. Process conversation (save facts)
        result = await orchestrator.process_conversation(
            user_email="test@test.com",
            user_message="Mi chiamo Test User",
            ai_response="Ciao Test User!",
        )
        assert result.success
        assert result.facts_extracted >= 1

        # 3. Retrieve context
        context = await orchestrator.get_user_context("test@test.com")
        assert context.user_id == "test@test.com"

        # 4. Close
        await orchestrator.close()


class TestMemoryOrchestratorEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_unicode_handling(self):
        """Test handling of unicode characters in facts"""
        from services.memory.orchestrator import MemoryOrchestrator

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        orchestrator._memory_service = AsyncMock()
        orchestrator._memory_service.add_fact = AsyncMock(return_value=True)
        orchestrator._memory_service.pool = True
        orchestrator._fact_extractor = MagicMock()
        orchestrator._fact_extractor.extract_facts_from_conversation = MagicMock(
            return_value=[
                {"content": "Nome: 日本語テスト", "type": "identity", "confidence": 0.9},
            ]
        )
        orchestrator._is_initialized = True

        result = await orchestrator.process_conversation(
            user_email="test@test.com",
            user_message="私の名前は日本語テスト",
            ai_response="こんにちは!",
        )

        assert result.success

    @pytest.mark.asyncio
    async def test_very_long_message_handling(self):
        """Test handling of very long messages"""
        from services.memory.orchestrator import MemoryOrchestrator

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        orchestrator._memory_service = AsyncMock()
        orchestrator._memory_service.add_fact = AsyncMock(return_value=True)
        orchestrator._memory_service.pool = True
        orchestrator._fact_extractor = MagicMock()
        orchestrator._fact_extractor.extract_facts_from_conversation = MagicMock(return_value=[])
        orchestrator._is_initialized = True

        # Very long message
        long_message = "Test " * 10000

        result = await orchestrator.process_conversation(
            user_email="test@test.com",
            user_message=long_message,
            ai_response="OK",
        )

        # Should not crash
        assert result.success

    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test concurrent access to orchestrator"""
        import asyncio

        from services.memory.orchestrator import MemoryOrchestrator
        from services.memory_service_postgres import UserMemory

        mock_pool = AsyncMock()
        orchestrator = MemoryOrchestrator(db_pool=mock_pool)
        orchestrator._memory_service = AsyncMock()
        orchestrator._memory_service.pool = True
        orchestrator._memory_service.get_memory = AsyncMock(
            return_value=UserMemory(
                user_id="concurrent@test.com",
                profile_facts=[],
                summary="",
                counters={"conversations": 0, "searches": 0, "tasks": 0},
                updated_at=datetime.now(),
            )
        )
        orchestrator._is_initialized = True

        # Run multiple concurrent requests
        tasks = [orchestrator.get_user_context(f"user{i}@test.com") for i in range(10)]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        for result in results:
            assert isinstance(result, MemoryContext)
