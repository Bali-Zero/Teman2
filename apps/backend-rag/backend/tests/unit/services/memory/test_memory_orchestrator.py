"""
Unit tests for MemoryOrchestrator
Target: 100% coverage
Composer: 4
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.memory.orchestrator import MemoryOrchestrator


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()
    return pool


@pytest.fixture
def memory_orchestrator(mock_db_pool):
    """Create memory orchestrator instance"""
    return MemoryOrchestrator(db_pool=mock_db_pool)


class TestMemoryOrchestrator:
    """Tests for MemoryOrchestrator"""

    @pytest.mark.asyncio
    async def test_init(self, mock_db_pool):
        """Test initialization"""
        orchestrator = MemoryOrchestrator(db_pool=mock_db_pool)
        assert orchestrator.db_pool == mock_db_pool

    @pytest.mark.asyncio
    async def test_initialize(self, memory_orchestrator):
        """Test initialization"""
        # Mock MemoryServicePostgres properly
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(
                return_value=MagicMock()
            )  # Return a mock memory object
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True

    @pytest.mark.asyncio
    async def test_get_user_context(self, memory_orchestrator):
        """Test getting user context"""
        user_email = "test@example.com"

        # Mock initialization
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            # Create a mock UserMemory-like object
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context(user_email)
            assert context is not None

    @pytest.mark.asyncio
    async def test_process_conversation(self, memory_orchestrator):
        """Test processing conversation"""
        # Mock initialization
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.save_fact = AsyncMock(return_value=True)
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(return_value=[])
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_extract_facts(self, memory_orchestrator):
        """Test fact extraction"""
        # Mock initialization
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[
                    {"content": "User interested in KITAS", "type": "general", "confidence": 0.8}
                ]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            # Use process_conversation which internally calls extract_facts
            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com",
                user_message="I am interested in KITAS",
                ai_response="KITAS is a work permit",
            )
            assert result is not None
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_initialize_with_database_url(self):
        """Test initialization with database_url"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = None
            mock_service.connect = AsyncMock()
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            orchestrator = MemoryOrchestrator(database_url="postgresql://test")
            await orchestrator.initialize()
            assert orchestrator.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_critical_failure(self, memory_orchestrator):
        """Test initialization with critical failure"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service_class.side_effect = Exception("Critical error")

            with pytest.raises(RuntimeError):
                await memory_orchestrator.initialize()

    @pytest.mark.asyncio
    async def test_initialize_degraded_mode(self, memory_orchestrator):
        """Test initialization in degraded mode"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
            patch(
                "backend.services.memory.orchestrator.CollectiveMemoryService",
                side_effect=Exception("Non-critical"),
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True
            assert memory_orchestrator._status.value == "degraded"

    @pytest.mark.asyncio
    async def test_get_user_context_empty_email(self, memory_orchestrator):
        """Test getting context with empty email"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_get_user_context_with_query(self, memory_orchestrator):
        """Test getting context with query for collective memory"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = ["fact1"]
            mock_memory.summary = "summary"
            mock_memory.counters = {"conversations": 5}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            mock_collective = MagicMock()
            # NOTE 2026-01-10: get_relevant_context() removed, using get_collective_context() instead
            mock_collective.get_collective_context = AsyncMock(return_value=["collective fact"])
            mock_collective_class.return_value = mock_collective

            mock_episodic = MagicMock()
            mock_episodic.get_context_summary = AsyncMock(return_value="timeline")
            mock_episodic_class.return_value = mock_episodic

            mock_kg = MagicMock()
            mock_kg.get_entity_context_for_query = AsyncMock(return_value=[{"id": "entity1"}])
            mock_kg_class.return_value = mock_kg

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context(
                "test@example.com", query="test query"
            )
            assert context.has_data is True

    @pytest.mark.asyncio
    async def test_get_user_context_degraded_mode(self, memory_orchestrator):
        """Test getting context in degraded mode"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context is not None

    @pytest.mark.asyncio
    async def test_get_user_context_error_handling(self, memory_orchestrator):
        """Test error handling in get_user_context"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            # First call succeeds (for initialization), second fails
            mock_service.get_memory = AsyncMock(side_effect=[MagicMock(), Exception("Error")])
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_process_conversation_with_facts(self, memory_orchestrator):
        """Test processing conversation with extracted facts"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            mock_episodic = MagicMock()
            mock_episodic.extract_and_save_event = AsyncMock(
                return_value={"status": "created", "title": "Event"}
            )
            mock_episodic_class.return_value = mock_episodic

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_empty_email(self, memory_orchestrator):
        """Test processing conversation with empty email"""
        result = await memory_orchestrator.process_conversation(
            user_email="", user_message="test", ai_response="response"
        )
        assert result.facts_extracted == 0

    @pytest.mark.asyncio
    async def test_process_conversation_no_extractor(self, memory_orchestrator):
        """Test processing conversation without extractor"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("No extractor"),
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted == 0

    @pytest.mark.asyncio
    async def test_process_conversation_lock_timeout(self, memory_orchestrator):
        """Test processing conversation with lock timeout"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            # Create a lock that's already acquired
            lock = memory_orchestrator._write_locks["test@example.com"]
            await lock.acquire()

            try:
                result = await memory_orchestrator.process_conversation(
                    user_email="test@example.com", user_message="test", ai_response="response"
                )
                # Should handle timeout gracefully
                assert result is not None
            finally:
                lock.release()

    @pytest.mark.asyncio
    async def test_process_conversation_error(self, memory_orchestrator):
        """Test error handling in process_conversation"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                side_effect=Exception("Error")
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_get_stats(self, memory_orchestrator):
        """Test getting stats"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_stats = AsyncMock(
                return_value={"total_users": 10, "total_facts": 100, "total_conversations": 50}
            )
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            stats = await memory_orchestrator.get_stats()
            assert stats.total_users == 10

    @pytest.mark.asyncio
    async def test_search_facts(self, memory_orchestrator):
        """Test searching facts"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.search = AsyncMock(return_value=[{"content": "fact1"}])
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            results = await memory_orchestrator.search_facts("test query")
            assert len(results) > 0

    @pytest.mark.asyncio
    async def test_get_relevant_facts_for_query(self, memory_orchestrator):
        """Test getting relevant facts for query"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_relevant_facts = AsyncMock(return_value=["fact1", "fact2"])
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            facts = await memory_orchestrator.get_relevant_facts_for_query(
                "test@example.com", "query"
            )
            assert len(facts) > 0

    @pytest.mark.asyncio
    async def test_close(self, memory_orchestrator):
        """Test closing orchestrator"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            await memory_orchestrator.close()

            assert memory_orchestrator.is_initialized is False

    @pytest.mark.asyncio
    async def test_close_error(self, memory_orchestrator):
        """Test closing with error"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.close = AsyncMock(side_effect=Exception("Error"))
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            await memory_orchestrator.close()
            # Should handle error gracefully

    def test_ensure_initialized_not_initialized(self, memory_orchestrator):
        """Test ensure_initialized when not initialized"""
        with pytest.raises(RuntimeError):
            memory_orchestrator._ensure_initialized()

    def test_properties(self, memory_orchestrator):
        """Test properties"""
        assert memory_orchestrator.is_initialized is False
        assert memory_orchestrator.db_pool is not None

    @pytest.mark.asyncio
    async def test_initialize_idempotency(self, memory_orchestrator):
        """Test that initialize can be called multiple times safely"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True

            # Call again - should be idempotent
            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_test_memory_none(self, memory_orchestrator):
        """Test initialization when test_memory is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=None)  # Returns None
            mock_service_class.return_value = mock_service

            with pytest.raises(RuntimeError, match="Memory service connection test failed"):
                await memory_orchestrator.initialize()

    @pytest.mark.asyncio
    async def test_initialize_all_services_healthy(self, memory_orchestrator):
        """Test initialization with all services working (HEALTHY status)"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            mock_extractor_class.return_value = MagicMock()
            mock_collective_class.return_value = MagicMock()
            mock_episodic_class.return_value = MagicMock()
            mock_kg_class.return_value = MagicMock()

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True
            assert memory_orchestrator._status.value == "healthy"

    @pytest.mark.asyncio
    async def test_initialize_episodic_memory_failure(self, memory_orchestrator):
        """Test initialization when episodic memory fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.EpisodicMemoryService",
                side_effect=Exception("Episodic error"),
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True
            assert memory_orchestrator._status.value == "degraded"

    @pytest.mark.asyncio
    async def test_initialize_kg_repository_failure(self, memory_orchestrator):
        """Test initialization when KG repository fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.KnowledgeGraphRepository",
                side_effect=Exception("KG error"),
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator.is_initialized is True
            assert memory_orchestrator._status.value == "degraded"

    @pytest.mark.asyncio
    async def test_get_user_context_memory_service_none(self, memory_orchestrator):
        """Test get_user_context when memory_service is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            # Set memory_service to None
            memory_orchestrator._memory_service = None

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_get_user_context_pool_none(self, memory_orchestrator):
        """Test get_user_context when pool is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = None  # Pool is None
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False

    @pytest.mark.asyncio
    async def test_get_user_context_collective_context_no_query(self, memory_orchestrator):
        """Test get_user_context calls get_collective_context when no query"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class,
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            mock_collective = MagicMock()
            mock_collective.get_collective_context = AsyncMock(return_value=["collective fact"])
            mock_collective_class.return_value = mock_collective

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")  # No query
            assert mock_collective.get_collective_context.called
            assert not mock_collective.get_relevant_context.called

    @pytest.mark.asyncio
    async def test_get_user_context_episodic_memory_failure(self, memory_orchestrator):
        """Test get_user_context when episodic memory fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            mock_episodic = MagicMock()
            mock_episodic.get_context_summary = AsyncMock(side_effect=Exception("Episodic error"))
            mock_episodic_class.return_value = mock_episodic

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context is not None

    @pytest.mark.asyncio
    async def test_get_user_context_kg_failure(self, memory_orchestrator):
        """Test get_user_context when KG repository fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            mock_kg = MagicMock()
            mock_kg.get_entity_context_for_query = AsyncMock(side_effect=Exception("KG error"))
            mock_kg_class.return_value = mock_kg

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com", query="test")
            assert context is not None

    @pytest.mark.asyncio
    async def test_get_user_context_updated_at_datetime(self, memory_orchestrator):
        """Test get_user_context when updated_at is a datetime"""
        from datetime import datetime

        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = datetime.now()  # Is a datetime

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.last_activity is not None

    @pytest.mark.asyncio
    async def test_get_user_context_updated_at_not_datetime(self, memory_orchestrator):
        """Test get_user_context when updated_at is not a datetime"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = "2024-01-01"  # Not a datetime

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.last_activity is None

    @pytest.mark.asyncio
    async def test_get_user_context_kg_no_query(self, memory_orchestrator):
        """Test get_user_context when KG repository exists but no query"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            mock_kg = MagicMock()
            mock_kg.get_entity_context_for_query = AsyncMock(return_value=[])
            mock_kg_class.return_value = mock_kg

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")  # No query
            assert not mock_kg.get_entity_context_for_query.called

    @pytest.mark.asyncio
    async def test_process_conversation_add_fact_failure(self, memory_orchestrator):
        """Test process_conversation when add_fact fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(side_effect=Exception("Add fact error"))
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0
            assert result.facts_saved == 0

    @pytest.mark.asyncio
    async def test_process_conversation_add_fact_returns_false(self, memory_orchestrator):
        """Test process_conversation when add_fact returns False"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=False)  # Returns False
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0
            assert result.facts_saved == 0

    @pytest.mark.asyncio
    async def test_process_conversation_increment_counter_failure(self, memory_orchestrator):
        """Test process_conversation when increment_counter fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock(side_effect=Exception("Counter error"))
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_episodic_memory_none(self, memory_orchestrator):
        """Test process_conversation when episodic memory is None"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()
            memory_orchestrator._episodic_memory = None  # Set to None

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_episodic_memory_failure(self, memory_orchestrator):
        """Test process_conversation when episodic memory fails"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            mock_episodic = MagicMock()
            mock_episodic.extract_and_save_event = AsyncMock(
                side_effect=Exception("Episodic error")
            )
            mock_episodic_class.return_value = mock_episodic

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_episodic_event_not_created(self, memory_orchestrator):
        """Test process_conversation when episodic event status is not 'created'"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            mock_episodic = MagicMock()
            mock_episodic.extract_and_save_event = AsyncMock(
                return_value={"status": "skipped"}
            )  # Not "created"
            mock_episodic_class.return_value = mock_episodic

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_process_conversation_fact_type_value_error(self, memory_orchestrator):
        """Test process_conversation when fact_type raises ValueError"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.add_fact = AsyncMock(return_value=True)
            mock_service.increment_counter = AsyncMock()
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[
                    {"content": "Fact 1", "type": "invalid_type", "confidence": 0.9}  # Invalid type
                ]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0

    @pytest.mark.asyncio
    async def test_get_stats_error(self, memory_orchestrator):
        """Test get_stats when it fails"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_stats = AsyncMock(side_effect=Exception("Stats error"))
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            stats = await memory_orchestrator.get_stats()
            assert stats.total_users == 0  # Returns empty MemoryStats

    @pytest.mark.asyncio
    async def test_get_stats_memory_service_none(self, memory_orchestrator):
        """Test get_stats when memory_service is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            memory_orchestrator._memory_service = None

            stats = await memory_orchestrator.get_stats()
            assert stats.total_users == 0

    @pytest.mark.asyncio
    async def test_search_facts_error(self, memory_orchestrator):
        """Test search_facts when it fails"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.search = AsyncMock(side_effect=Exception("Search error"))
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            results = await memory_orchestrator.search_facts("test query")
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_facts_memory_service_none(self, memory_orchestrator):
        """Test search_facts when memory_service is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            memory_orchestrator._memory_service = None

            results = await memory_orchestrator.search_facts("test query")
            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_relevant_facts_for_query_error(self, memory_orchestrator):
        """Test get_relevant_facts_for_query when it fails"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.get_relevant_facts = AsyncMock(side_effect=Exception("Error"))
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            facts = await memory_orchestrator.get_relevant_facts_for_query(
                "test@example.com", "query"
            )
            assert len(facts) == 0

    @pytest.mark.asyncio
    async def test_get_relevant_facts_for_query_memory_service_none(self, memory_orchestrator):
        """Test get_relevant_facts_for_query when memory_service is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            memory_orchestrator._memory_service = None

            facts = await memory_orchestrator.get_relevant_facts_for_query(
                "test@example.com", "query"
            )
            assert len(facts) == 0

    @pytest.mark.asyncio
    async def test_close_db_pool_none(self, memory_orchestrator):
        """Test close when db_pool is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = None
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service.close = AsyncMock()
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            memory_orchestrator._db_pool = None

            await memory_orchestrator.close()
            assert memory_orchestrator.is_initialized is False

    @pytest.mark.asyncio
    async def test_close_memory_service_none(self, memory_orchestrator):
        """Test close when memory_service is None"""
        with patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class:
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            memory_orchestrator._memory_service = None

            await memory_orchestrator.close()
            assert memory_orchestrator.is_initialized is False

    def test_ensure_initialized_unavailable(self, memory_orchestrator):
        """Test ensure_initialized when status is UNAVAILABLE"""
        from backend.services.memory.orchestrator import MemoryServiceStatus

        memory_orchestrator._is_initialized = True
        memory_orchestrator._status = MemoryServiceStatus.UNAVAILABLE

        with pytest.raises(RuntimeError, match="MemoryOrchestrator is unavailable"):
            memory_orchestrator._ensure_initialized()

    @pytest.mark.asyncio
    async def test_alert_critical_failure(self, memory_orchestrator):
        """Test _alert_critical_failure method"""
        failures = [("memory_service", "Connection failed")]

        await memory_orchestrator._alert_critical_failure(failures)
        # Should not raise, just log

    @pytest.mark.asyncio
    async def test_alert_degraded_mode(self, memory_orchestrator):
        """Test _alert_degraded_mode method"""
        failures = [("fact_extractor", "Init failed")]

        await memory_orchestrator._alert_degraded_mode(failures)
        # Should not raise, just log

    @pytest.mark.asyncio
    async def test_process_conversation_no_memory_service_pool(self, memory_orchestrator):
        """Test process_conversation when memory_service.pool is None"""
        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
        ):
            mock_service = MagicMock()
            mock_service.pool = None  # Pool is None
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            mock_extractor = MagicMock()
            mock_extractor.extract_facts_from_conversation = MagicMock(
                return_value=[{"content": "Fact 1", "type": "general", "confidence": 0.9}]
            )
            mock_extractor_class.return_value = mock_extractor

            await memory_orchestrator.initialize()

            result = await memory_orchestrator.process_conversation(
                user_email="test@example.com", user_message="test", ai_response="response"
            )
            assert result.facts_extracted > 0
            assert result.facts_saved == 0  # Should not save when pool is None

    @pytest.mark.asyncio
    async def test_initialize_metrics_unavailable(self, memory_orchestrator):
        """Test initialization metrics when unavailable"""
        # Mock the metrics module to be importable
        mock_metric = MagicMock()
        mock_metric.inc = MagicMock()

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch.dict(
                "sys.modules",
                {"backend.app.metrics": MagicMock(memory_orchestrator_unavailable_total=mock_metric)},
            ),
        ):
            mock_service_class.side_effect = Exception("Critical error")

            with pytest.raises(RuntimeError):
                await memory_orchestrator.initialize()

    @pytest.mark.asyncio
    async def test_initialize_metrics_degraded(self, memory_orchestrator):
        """Test initialization metrics when degraded"""
        # Mock the metrics module to be importable
        mock_metric = MagicMock()
        mock_metric.inc = MagicMock()

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
            patch.dict(
                "sys.modules",
                {"backend.app.metrics": MagicMock(memory_orchestrator_degraded_total=mock_metric)},
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator._status.value == "degraded"
            mock_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_metrics_healthy(self, memory_orchestrator):
        """Test initialization metrics when healthy"""
        # Mock the metrics module to be importable
        mock_metric = MagicMock()
        mock_metric.inc = MagicMock()

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
            patch.dict(
                "sys.modules",
                {"backend.app.metrics": MagicMock(memory_orchestrator_healthy_total=mock_metric)},
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            mock_extractor_class.return_value = MagicMock()
            mock_collective_class.return_value = MagicMock()
            mock_episodic_class.return_value = MagicMock()
            mock_kg_class.return_value = MagicMock()

            await memory_orchestrator.initialize()
            assert memory_orchestrator._status.value == "healthy"
            mock_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_context_metrics_degraded(self, memory_orchestrator):
        """Test get_user_context metrics when in degraded mode"""
        # Mock the metrics module to be importable
        mock_metric = MagicMock()
        mock_metric.inc = MagicMock()

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
            patch.dict(
                "sys.modules", {"backend.app.metrics": MagicMock(memory_context_degraded_total=mock_metric)}
            ),
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context is not None
            mock_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_context_metrics_failed(self, memory_orchestrator):
        """Test get_user_context metrics when it fails"""
        # Mock the metrics module to be importable
        mock_metric = MagicMock()
        mock_metric.inc = MagicMock()

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch.dict(
                "sys.modules", {"backend.app.metrics": MagicMock(memory_context_failed_total=mock_metric)}
            ),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            # First call succeeds (for initialization), second fails
            mock_service.get_memory = AsyncMock(side_effect=[MagicMock(), Exception("Error")])
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False
            mock_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_metrics_unavailable_import_error(self, memory_orchestrator):
        """Test initialization when metrics import fails (unavailable)"""
        # Make the import fail to cover the except ImportError block
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "backend.app.metrics":
                raise ImportError("Metrics module not available")
            return original_import(name, *args, **kwargs)

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("builtins.__import__", side_effect=mock_import),
        ):
            mock_service_class.side_effect = Exception("Critical error")

            with pytest.raises(RuntimeError):
                await memory_orchestrator.initialize()

    @pytest.mark.asyncio
    async def test_initialize_metrics_degraded_import_error(self, memory_orchestrator):
        """Test initialization when metrics import fails (degraded)"""
        # Make the import fail to cover the except ImportError block
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "backend.app.metrics":
                raise ImportError("Metrics module not available")
            return original_import(name, *args, **kwargs)

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()
            assert memory_orchestrator._status.value == "degraded"

    @pytest.mark.asyncio
    async def test_initialize_metrics_healthy_import_error(self, memory_orchestrator):
        """Test initialization when metrics import fails (healthy)"""
        # Make the import fail to cover the except ImportError block
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "backend.app.metrics":
                raise ImportError("Metrics module not available")
            return original_import(name, *args, **kwargs)

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("backend.services.memory.orchestrator.MemoryFactExtractor") as mock_extractor_class,
            patch("backend.services.memory.orchestrator.CollectiveMemoryService") as mock_collective_class,
            patch("backend.services.memory.orchestrator.EpisodicMemoryService") as mock_episodic_class,
            patch("backend.services.memory.orchestrator.KnowledgeGraphRepository") as mock_kg_class,
            patch("builtins.__import__", side_effect=mock_import),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=MagicMock())
            mock_service_class.return_value = mock_service

            mock_extractor_class.return_value = MagicMock()
            mock_collective_class.return_value = MagicMock()
            mock_episodic_class.return_value = MagicMock()
            mock_kg_class.return_value = MagicMock()

            await memory_orchestrator.initialize()
            assert memory_orchestrator._status.value == "healthy"

    @pytest.mark.asyncio
    async def test_get_user_context_metrics_degraded_import_error(self, memory_orchestrator):
        """Test get_user_context when metrics import fails (degraded mode)"""
        # Make the import fail to cover the except ImportError block
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "backend.app.metrics":
                raise ImportError("Metrics module not available")
            return original_import(name, *args, **kwargs)

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch(
                "backend.services.memory.orchestrator.MemoryFactExtractor",
                side_effect=Exception("Non-critical"),
            ),
            patch("builtins.__import__", side_effect=mock_import),
        ):
            mock_memory = MagicMock()
            mock_memory.profile_facts = []
            mock_memory.summary = ""
            mock_memory.counters = {}
            mock_memory.updated_at = None

            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            mock_service.get_memory = AsyncMock(return_value=mock_memory)
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context is not None

    @pytest.mark.asyncio
    async def test_get_user_context_metrics_failed_import_error(self, memory_orchestrator):
        """Test get_user_context when metrics import fails (failed context)"""
        # Make the import fail to cover the except ImportError block
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "backend.app.metrics":
                raise ImportError("Metrics module not available")
            return original_import(name, *args, **kwargs)

        with (
            patch("backend.services.memory.orchestrator.MemoryServicePostgres") as mock_service_class,
            patch("builtins.__import__", side_effect=mock_import),
        ):
            mock_service = MagicMock()
            mock_service.pool = memory_orchestrator._db_pool
            # First call succeeds (for initialization), second fails
            mock_service.get_memory = AsyncMock(side_effect=[MagicMock(), Exception("Error")])
            mock_service_class.return_value = mock_service

            await memory_orchestrator.initialize()

            context = await memory_orchestrator.get_user_context("test@example.com")
            assert context.has_data is False
